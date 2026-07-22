"""
core/tool_executor.py
---------------------
Tool çalıştırma merkezi.

Akış:
    1. `permissions.py` → izin kontrolü
    2. `approval.py`    → onay gerekiyorsa bekle
    3. Tool fonksiyonunu çağır
    4. `logger.py`      → sonucu logla

Bu modül hiçbir tool'u doğrudan implement etmez;
doğru server/modüle yönlendirme yapar.

Kullanım:
    from core.tool_executor import tool_executor, ExecutionResult

    result = await tool_executor.execute(
        tool_name="file_read",
        parameters={"path": "README.md"},
        user_id=1,
        user_role="employee",
        session_id="abc",
        db=db,
    )
"""

from __future__ import annotations

import inspect
import traceback
from dataclasses import dataclass
from typing import Any, Callable

from core.approval import ApprovalStatus, approval_manager
from core.logger import Timer, get_logger, log_tool_call
from core.permissions import PermissionResult, permission_manager

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Onay gerektiren tool'lar
# ─────────────────────────────────────────────────────────────────────────────

REQUIRES_APPROVAL = {
    "db_delete",
    "db_update",
    "file_delete",
    "file_move",
    "github_create_pull_request",
    "git_commit_and_push",
    "approve_leave",
    "mail_send",
    "calendar_add_event",
    "calendar_delete_event",
}


@dataclass
class ExecutionResult:
    """
    Tool çalıştırma sonucu.

    Attributes:
        success      : İşlem başarılı mı?
        data         : Tool'un döndürdüğü veri
        error        : Hata mesajı (success=False ise)
        status       : "success" | "error" | "permission_denied" | "pending_approval" | "rejected" | "expired"
        approval_id  : Onay bekleme durumunda atanan ID
        log_id       : DB log kaydı ID'si
        duration_ms  : İşlem süresi (ms)
    """

    success: bool
    data: Any
    error: str | None
    status: str
    approval_id: str | None = None
    log_id: int | None = None
    duration_ms: int = 0


class ToolExecutor:
    """
    Tool çalıştırma koordinatörü.

    Tüm tool çağrıları bu sınıf üzerinden geçer.
    İzin, onay ve loglama burada yönetilir.
    """

    # ── Tool → Callable Haritası ─────────────────────────────────────────────

    def _get_tool_entry(self, tool_name: str) -> tuple[Callable | None, bool]:
        """
        Tool adından (callable, is_lambda) çiftini döner.

        is_lambda=True  → fn(parameters_dict) şeklinde çağrılır
        is_lambda=False → fn(**parameters) şeklinde çağrılır

        Returns:
            (callable_or_None, is_lambda)
        """
        # ── Dosya sistemi ─────────────────────────────────────────────────────
        from mcp_servers.filesystem_server import filesystem_server as fs
        filesystem_tools = {
            "file_read":   fs.file_read,
            "file_write":  fs.file_write,
            "file_delete": fs.file_delete,
            "file_list":   fs.file_list,
            "file_move":   fs.file_move,
        }
        if tool_name in filesystem_tools:
            return filesystem_tools[tool_name], False

        # ── Veritabanı ────────────────────────────────────────────────────────
        from mcp_servers.database_server import database_server as db_srv
        database_tools = {
            "db_list_tables": db_srv.db_list_tables,
            "db_get_schema":  db_srv.db_get_schema,
            "db_query":       db_srv.db_query,
            "db_insert":      db_srv.db_insert,
            "db_update":      db_srv.db_update,
            "db_delete":      db_srv.db_delete,
        }
        if tool_name in database_tools:
            return database_tools[tool_name], False

        # ── HR ────────────────────────────────────────────────────────────────
        from mcp_servers.hr_server import hr_server
        hr_tools = {
            "get_employee_leave_balance": hr_server.get_employee_leave_balance,
            "get_employees_on_leave":     hr_server.get_employees_on_leave,
            "request_leave":              hr_server.request_leave,
            "approve_leave":              hr_server.approve_leave,
        }
        if tool_name in hr_tools:
            return hr_tools[tool_name], False

        # ── Kod / Git (Faz 3) ─────────────────────────────────────────────────
        from mcp_servers.code_server import code_server
        code_tools: dict[str, Callable] = {
            "code_run":  lambda p: code_server.code_run(
                path=p.get("path", ""),
                language=p.get("language", "python"),
            ),
            "code_lint": lambda p: code_server.code_lint(
                path=p.get("path", ""),
            ),
            "git_status": lambda p: code_server.git_status(
                repo_path=p.get("repo_path", ""),
            ),
            "git_diff_preview": lambda p: code_server.git_diff_preview(
                repo_path=p.get("repo_path", ""),
            ),
            "git_create_branch": lambda p: code_server.git_create_branch(
                repo_path=p.get("repo_path", ""),
                branch_name=p.get("branch_name", ""),
            ),
            "git_commit_and_push": lambda p: code_server.git_commit_and_push(
                repo_path=p.get("repo_path", ""),
                message=p.get("message", p.get("commit_message", "")),
                branch=p.get("branch", ""),
            ),
            "github_create_pull_request": lambda p: code_server.github_create_pull_request(
                repo=p.get("repo", p.get("repo_path", "")),
                branch=p.get("branch", ""),
                title=p.get("title", ""),
            ),
        }
        if tool_name in code_tools:
            return code_tools[tool_name], True

        # ── Mail & Takvim (Faz 4) ─────────────────────────────────────────────
        from mcp_servers.mail_calendar_server import mail_calendar_server
        mail_calendar_tools: dict[str, Callable] = {
            "mail_read_inbox": lambda p: mail_calendar_server.mail_read_inbox(
                count=p.get("count", 5),
            ),
            "mail_send": lambda p: mail_calendar_server.mail_send(
                to=p.get("to", ""),
                subject=p.get("subject", ""),
                body=p.get("body", ""),
            ),
            "mail_extract_meeting": lambda p: mail_calendar_server.mail_extract_meeting(
                mail_id=p.get("mail_id", ""),
            ),
            "calendar_list_events": lambda p: mail_calendar_server.calendar_list_events(
                date=p.get("date", "bugün"),
            ),
            "calendar_add_event": lambda p: mail_calendar_server.calendar_add_event(
                title=p.get("title", ""),
                date=p.get("date", ""),
                time=p.get("time", ""),
                duration_minutes=p.get("duration_minutes", 60),
            ),
            "calendar_delete_event": lambda p: mail_calendar_server.calendar_delete_event(
                event_id=p.get("event_id", ""),
            ),
        }
        if tool_name in mail_calendar_tools:
            return mail_calendar_tools[tool_name], True

        # ── Uygulama (Faz 5) ─────────────────────────────────────────────────
        from mcp_servers.app_server import app_server
        app_tools: dict[str, Callable] = {
            "app_open": lambda p: app_server.app_open(
                name=p.get("name", ""),
            ),
            "app_close": lambda p: app_server.app_close(
                name=p.get("name", ""),
            ),
            "app_list_running": lambda p: app_server.app_list_running(),
        }
        if tool_name in app_tools:
            return app_tools[tool_name], True

        # ── Multimodal (Faz 6) ────────────────────────────────────────────────
        from multimodal.stt import stt_transcribe
        from multimodal.tts import tts_speak
        from multimodal.vision import vision_describe
        from multimodal.image_gen import image_generate
        multimodal_tools: dict[str, Callable] = {
            "stt_transcribe":  lambda p: stt_transcribe(audio_path=p.get("audio_path", "")),
            "tts_speak":       lambda p: tts_speak(text=p.get("text", "")),
            "vision_describe": lambda p: vision_describe(image_path=p.get("image_path", "")),
            "image_generate":  lambda p: image_generate(prompt=p.get("prompt", "")),
        }
        if tool_name in multimodal_tools:
            return multimodal_tools[tool_name], True

        return None, False

    # ── Ana Execute Metodu ────────────────────────────────────────────────────

    async def execute(
        self,
        *,
        tool_name: str,
        parameters: dict[str, Any],
        user_id: int | None,
        user_role: str,
        session_id: str | None,
        db: Any,  # SQLAlchemy Session
        category: str | None = None,
        approval_id: str | None = None,
    ) -> ExecutionResult:
        """
        Tool'u güvenli şekilde çalıştırır.

        Args:
            tool_name  : Çalıştırılacak tool adı
            parameters : Tool parametreleri
            user_id    : Çağıran kullanıcı ID'si
            user_role  : Kullanıcının rolü
            session_id : Konuşma oturum ID'si
            db         : SQLAlchemy DB session'ı
            category   : Router kategorisi (loglama için)
            approval_id: Önceki onay isteği ID'si (kullanıcı onay verdiyse)

        Returns:
            ExecutionResult
        """
        logger.info(
            "Tool yürütme başlıyor",
            extra={
                "tool": tool_name,
                "user_id": user_id,
                "role": user_role,
                "session": session_id,
                "has_approval": approval_id is not None,
            },
        )

        # ── 1. İzin Kontrolü ──────────────────────────────────────────────────
        perm: PermissionResult = permission_manager.check(
            user_role=user_role,
            tool_name=tool_name,
            db=db,
        )

        if not perm.allowed:
            log_tool_call(
                tool_name=tool_name,
                parameters=parameters,
                status="permission_denied",
                db=db,
                category=category,
                user_id=user_id,
                session_id=session_id,
                error_message=perm.reason,
            )
            return ExecutionResult(
                success=False,
                data=None,
                error=perm.reason,
                status="permission_denied",
            )

        # ── 2. Onay Kontrolü ──────────────────────────────────────────────────
        # REQUIRES_APPROVAL setini perm.requires_approval ile birleştir
        needs_approval = perm.requires_approval or (tool_name in REQUIRES_APPROVAL)

        if needs_approval:
            if approval_id is None:
                # Onay henüz alınmamış — yeni istek oluştur
                new_approval_id = approval_manager.request(
                    tool_name=tool_name,
                    parameters=parameters,
                    user_id=user_id,
                    session_id=session_id,
                )
                log_tool_call(
                    tool_name=tool_name,
                    parameters=parameters,
                    status="pending",
                    db=db,
                    category=category,
                    user_id=user_id,
                    session_id=session_id,
                )
                return ExecutionResult(
                    success=False,
                    data=None,
                    error=None,
                    status="pending_approval",
                    approval_id=new_approval_id,
                )

            # Approval ID verilmiş — durumunu kontrol et
            approval_status = approval_manager.get_status(approval_id)

            if approval_status == ApprovalStatus.PENDING:
                return ExecutionResult(
                    success=False,
                    data=None,
                    error="Onay henüz bekleniyor",
                    status="pending_approval",
                    approval_id=approval_id,
                )

            if approval_status == ApprovalStatus.REJECTED:
                log_tool_call(
                    tool_name=tool_name,
                    parameters=parameters,
                    status="rejected",
                    db=db,
                    category=category,
                    user_id=user_id,
                    session_id=session_id,
                )
                return ExecutionResult(
                    success=False,
                    data=None,
                    error="İşlem kullanıcı tarafından reddedildi",
                    status="rejected",
                    approval_id=approval_id,
                )

            if approval_status == ApprovalStatus.EXPIRED:
                return ExecutionResult(
                    success=False,
                    data=None,
                    error="Onay isteğinin süresi doldu. Lütfen işlemi tekrar başlatın.",
                    status="expired",
                    approval_id=approval_id,
                )

            # APPROVED — devam et

        # ── 3. Tool Callable'ını Bul ──────────────────────────────────────────
        fn, is_lambda = self._get_tool_entry(tool_name)
        if fn is None:
            error_msg = f"Bilinmeyen tool: '{tool_name}'"
            log_tool_call(
                tool_name=tool_name,
                parameters=parameters,
                status="error",
                db=db,
                category=category,
                user_id=user_id,
                session_id=session_id,
                error_message=error_msg,
            )
            return ExecutionResult(
                success=False,
                data=None,
                error=error_msg,
                status="error",
            )

        # ── 4. Tool'u Çalıştır ────────────────────────────────────────────────
        approved_by: str | None = None
        if approval_id:
            req = approval_manager.get_request(approval_id)
            if req:
                approved_by = req.resolved_by

        with Timer() as timer:
            try:
                # Lambda tool'lar parameters dict alır; direkt fonksiyonlar **kwargs alır
                if is_lambda:
                    result = fn(parameters)
                else:
                    result = fn(**parameters)

                # Async desteği
                if inspect.isawaitable(result):
                    result = await result

                log_id = log_tool_call(
                    tool_name=tool_name,
                    parameters=parameters,
                    status="success",
                    db=db,
                    category=category,
                    result=result,
                    user_id=user_id,
                    session_id=session_id,
                    approved_by=approved_by,
                    duration_ms=timer.elapsed_ms,
                )

                return ExecutionResult(
                    success=True,
                    data=result,
                    error=None,
                    status="success",
                    approval_id=approval_id,
                    log_id=log_id,
                    duration_ms=timer.elapsed_ms,
                )

            except PermissionError as exc:
                # Sandbox ihlali veya izin hatası
                error_msg = str(exc)
                log_tool_call(
                    tool_name=tool_name,
                    parameters=parameters,
                    status="error",
                    db=db,
                    category=category,
                    user_id=user_id,
                    session_id=session_id,
                    error_message=error_msg,
                    duration_ms=timer.elapsed_ms,
                )
                logger.error(
                    f"Güvenlik ihlali: {tool_name}",
                    extra={"error": error_msg, "user_id": user_id},
                )
                return ExecutionResult(
                    success=False,
                    data=None,
                    error=error_msg,
                    status="error",
                    duration_ms=timer.elapsed_ms,
                )

            except Exception as exc:
                error_msg = f"{type(exc).__name__}: {exc}"
                tb = traceback.format_exc()
                logger.error(
                    f"Tool hatası: {tool_name} — {error_msg}\n{tb}",
                    extra={"user_id": user_id, "session": session_id},
                )
                log_tool_call(
                    tool_name=tool_name,
                    parameters=parameters,
                    status="error",
                    db=db,
                    category=category,
                    user_id=user_id,
                    session_id=session_id,
                    error_message=error_msg,
                    duration_ms=timer.elapsed_ms,
                )
                return ExecutionResult(
                    success=False,
                    data=None,
                    error=error_msg,
                    status="error",
                    duration_ms=timer.elapsed_ms,
                )


# Modül genelinde kullanılan tekil executor örneği
tool_executor = ToolExecutor()
