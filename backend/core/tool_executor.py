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

import traceback
from dataclasses import dataclass
from typing import Any

from core.approval import ApprovalStatus, approval_manager
from core.logger import Timer, get_logger, log_tool_call
from core.permissions import PermissionResult, permission_manager

logger = get_logger(__name__)


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

    def _get_tool_callable(self, tool_name: str):
        """
        Tool adından çalıştırılabilir fonksiyonu döner.

        Yeni tool eklenmek istendiğinde sadece bu metodun genişletilmesi gerekir.
        """
        # Dosya sistemi
        from mcp_servers.filesystem_server import filesystem_server as fs
        filesystem_tools = {
            "file_read":   fs.file_read,
            "file_write":  fs.file_write,
            "file_delete": fs.file_delete,
            "file_list":   fs.file_list,
            "file_move":   fs.file_move,
        }
        if tool_name in filesystem_tools:
            return filesystem_tools[tool_name]

        # Veritabanı — generic tool'lar (Faz 2)
        # NOT: RESTRICTED_TABLES (employees, leave_requests vb.) bu tool'larla
        #      erişilemez; bu tablolara yalnızca hr_server üzerinden erişilir.
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
            return database_tools[tool_name]

        # HR tool'ları — kendi rol ve durum kontrolüne sahip (Faz 2)
        # Bu fonksiyonlar hassas tablolara (RESTRICTED_TABLES) özel rol
        # kontrolü üzerinden erişir — generic db_ tool'larından ayrıdır.
        from mcp_servers.hr_server import hr_server
        hr_tools = {
            "get_employee_leave_balance": hr_server.get_employee_leave_balance,
            "get_employees_on_leave":     hr_server.get_employees_on_leave,
            "request_leave":              hr_server.request_leave,
            "approve_leave":              hr_server.approve_leave,
        }
        if tool_name in hr_tools:
            return hr_tools[tool_name]

        # Kod / Git (Faz 3'te doldurulacak)
        from mcp_servers.code_server import code_server as code_srv
        code_tools = {
            "code_run":                   code_srv.code_run,
            "code_lint":                  code_srv.code_lint,
            "git_status":                 code_srv.git_status,
            "git_diff_preview":           code_srv.git_diff_preview,
            "git_create_branch":          code_srv.git_create_branch,
            "git_commit_and_push":        code_srv.git_commit_and_push,
            "github_create_pull_request": code_srv.github_create_pull_request,
        }
        if tool_name in code_tools:
            return code_tools[tool_name]

        # Uygulama (Faz 5'te doldurulacak)
        from mcp_servers.app_server import app_server
        app_tools = {
            "app_open":         app_server.app_open,
            "app_close":        app_server.app_close,
            "app_list_running": app_server.app_list_running,
        }
        if tool_name in app_tools:
            return app_tools[tool_name]

        # Multimodal (Faz 6'da doldurulacak)
        from multimodal.stt import stt_transcribe
        from multimodal.tts import tts_speak
        from multimodal.vision import vision_describe
        from multimodal.image_gen import image_generate
        multimodal_tools = {
            "stt_transcribe":  stt_transcribe,
            "tts_speak":       tts_speak,
            "vision_describe": vision_describe,
            "image_generate":  image_generate,
        }
        if tool_name in multimodal_tools:
            return multimodal_tools[tool_name]

        return None

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
            f"Tool yürütme başlıyor",
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
        if perm.requires_approval:
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
        fn = self._get_tool_callable(tool_name)
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
                # Tool'u parametrelerle çağır
                result = fn(**parameters)
                # Async tool desteği (ileride gerekirse)
                import inspect
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
