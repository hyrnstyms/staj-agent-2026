"""
mcp_servers/mcp_adapters.py
---------------------------
Tüm MCP server adapter'ları — her server'ı MCP protokolüne bağlar.

Bu dosya import edildiğinde tüm server'lar mcp_registry'ye kaydolur.
FastAPI startup'ta bir kez import edilmesi yeterli.

Kayıt edilen server'lar:
    - filesystem   (dosya işlemleri)
    - database     (DB sorgulama/yazma)
    - hr           (personel, izin)
    - code_git     (kod çalıştırma, git)
    - mail_calendar (mail/takvim — n8n üzerinden)
    - app          (uygulama aç/kapat)
"""

from __future__ import annotations

from typing import Any

from core.mcp_protocol import (
    McpInputProperty,
    McpInputSchema,
    McpServer,
    McpTool,
    McpToolResult,
    mcp_registry,
)
from core.logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Database MCP Adapter
# ─────────────────────────────────────────────────────────────────────────────

class DatabaseMcpServer(McpServer):
    @property
    def server_name(self) -> str:
        return "database"

    @property
    def server_description(self) -> str:
        return "SQLite veritabanı işlemleri: tablo listeleme, şema görme, veri sorgulama/ekleme/güncelleme/silme"

    def list_tools(self) -> list[McpTool]:
        return [
            McpTool(
                name="db_list_tables",
                description="Veritabanındaki tüm tabloları listeler.",
                input_schema=McpInputSchema(),
            ),
            McpTool(
                name="db_get_schema",
                description="Belirtilen tablonun sütun şemasını döner.",
                input_schema=McpInputSchema(
                    properties={"table": McpInputProperty(type="string", description="Tablo adı")},
                    required=["table"],
                ),
            ),
            McpTool(
                name="db_query",
                description="Tabloda filtreyle veri sorgular (serbest SQL değil).",
                input_schema=McpInputSchema(
                    properties={
                        "table":   McpInputProperty(type="string", description="Tablo adı"),
                        "filters": McpInputProperty(type="string", description="Filtreler JSON string olarak, örn: {\"role\": \"admin\"}"),
                        "limit":   McpInputProperty(type="integer", description="Maksimum kayıt sayısı", default=20),
                    },
                    required=["table"],
                ),
            ),
            McpTool(
                name="db_insert",
                description="Tabloya yeni kayıt ekler. Onay gerektirir.",
                input_schema=McpInputSchema(
                    properties={
                        "table":  McpInputProperty(type="string", description="Tablo adı"),
                        "values": McpInputProperty(type="string", description="Eklenecek değerler JSON string"),
                    },
                    required=["table", "values"],
                ),
            ),
            McpTool(
                name="db_update",
                description="Tabloda ID'ye göre kayıt günceller. Onay gerektirir.",
                input_schema=McpInputSchema(
                    properties={
                        "table":  McpInputProperty(type="string", description="Tablo adı"),
                        "id":     McpInputProperty(type="integer", description="Güncellenecek kayıt ID'si"),
                        "values": McpInputProperty(type="string", description="Yeni değerler JSON string"),
                    },
                    required=["table", "id", "values"],
                ),
            ),
            McpTool(
                name="db_delete",
                description="Tabloda ID'ye göre kayıt siler. Onay gerektirir.",
                input_schema=McpInputSchema(
                    properties={
                        "table": McpInputProperty(type="string", description="Tablo adı"),
                        "id":    McpInputProperty(type="integer", description="Silinecek kayıt ID'si"),
                    },
                    required=["table", "id"],
                ),
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> McpToolResult:
        import json
        from mcp_servers.database_server import database_server as db_srv
        try:
            if name == "db_list_tables":
                return McpToolResult.success(db_srv.db_list_tables())
            elif name == "db_get_schema":
                return McpToolResult.success(db_srv.db_get_schema(arguments["table"]))
            elif name == "db_query":
                filters = json.loads(arguments.get("filters") or "{}") if isinstance(arguments.get("filters"), str) else {}
                return McpToolResult.success(db_srv.db_query(arguments["table"], filters, arguments.get("limit", 20)))
            elif name == "db_insert":
                values = json.loads(arguments["values"]) if isinstance(arguments["values"], str) else arguments["values"]
                return McpToolResult.success(db_srv.db_insert(arguments["table"], values))
            elif name == "db_update":
                values = json.loads(arguments["values"]) if isinstance(arguments["values"], str) else arguments["values"]
                return McpToolResult.success(db_srv.db_update(arguments["table"], arguments["id"], values))
            elif name == "db_delete":
                return McpToolResult.success(db_srv.db_delete(arguments["table"], arguments["id"]))
            else:
                return McpToolResult.error(f"Bilinmeyen tool: {name}")
        except Exception as exc:
            return McpToolResult.error(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# HR MCP Adapter
# ─────────────────────────────────────────────────────────────────────────────

class HrMcpServer(McpServer):
    @property
    def server_name(self) -> str:
        return "hr"

    @property
    def server_description(self) -> str:
        return "Personel ve izin yönetimi: izin bakiyesi sorgulama, izin talebi oluşturma ve onaylama"

    def list_tools(self) -> list[McpTool]:
        return [
            McpTool(
                name="get_employee_leave_balance",
                description="Bir çalışanın izin bakiyesini sorgular.",
                input_schema=McpInputSchema(
                    properties={
                        "name":      McpInputProperty(type="string", description="Çalışan adı"),
                        "requester": McpInputProperty(type="string", description="Sorguyu yapan kişinin adı (rol kontrolü için)"),
                    },
                    required=["name", "requester"],
                ),
            ),
            McpTool(
                name="get_employees_on_leave",
                description="Belirli bir tarihte izinli olan çalışanları listeler.",
                input_schema=McpInputSchema(
                    properties={"date": McpInputProperty(type="string", description="Tarih (YYYY-MM-DD formatı, 'bugün' de kabul edilir)")},
                    required=["date"],
                ),
            ),
            McpTool(
                name="request_leave",
                description="Çalışan adına izin talebi oluşturur. Onay gerektirir.",
                input_schema=McpInputSchema(
                    properties={
                        "employee_name": McpInputProperty(type="string", description="Çalışan adı"),
                        "start_date":    McpInputProperty(type="string", description="Başlangıç tarihi (YYYY-MM-DD)"),
                        "end_date":      McpInputProperty(type="string", description="Bitiş tarihi (YYYY-MM-DD)"),
                        "leave_type":    McpInputProperty(type="string", description="İzin türü", enum=["annual", "sick", "unpaid", "other"]),
                    },
                    required=["employee_name", "start_date", "end_date", "leave_type"],
                ),
            ),
            McpTool(
                name="approve_leave",
                description="Bekleyen izin talebini onaylar. Onay + HR rolü gerektirir.",
                input_schema=McpInputSchema(
                    properties={
                        "request_id":    McpInputProperty(type="integer", description="İzin talebi ID'si"),
                        "approver_role": McpInputProperty(type="string", description="Onaylayan rolü"),
                    },
                    required=["request_id", "approver_role"],
                ),
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> McpToolResult:
        from mcp_servers.hr_server import hr_server
        try:
            if name == "get_employee_leave_balance":
                return McpToolResult.success(hr_server.get_employee_leave_balance(arguments["name"], arguments["requester"]))
            elif name == "get_employees_on_leave":
                return McpToolResult.success(hr_server.get_employees_on_leave(arguments["date"]))
            elif name == "request_leave":
                return McpToolResult.success(hr_server.request_leave(
                    arguments["employee_name"], arguments["start_date"],
                    arguments["end_date"], arguments["leave_type"],
                ))
            elif name == "approve_leave":
                return McpToolResult.success(hr_server.approve_leave(arguments["request_id"], arguments["approver_role"]))
            else:
                return McpToolResult.error(f"Bilinmeyen tool: {name}")
        except Exception as exc:
            return McpToolResult.error(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Code + Git MCP Adapter
# ─────────────────────────────────────────────────────────────────────────────

class CodeGitMcpServer(McpServer):
    @property
    def server_name(self) -> str:
        return "code_git"

    @property
    def server_description(self) -> str:
        return "Kod çalıştırma (Docker sandbox), kod lint, git/GitHub işlemleri"

    def list_tools(self) -> list[McpTool]:
        return [
            McpTool(
                name="code_run",
                description="Docker sandbox içinde kod çalıştırır.",
                input_schema=McpInputSchema(
                    properties={
                        "path":     McpInputProperty(type="string", description="Çalıştırılacak dosya yolu"),
                        "language": McpInputProperty(type="string", description="Dil", enum=["python", "javascript", "bash"]),
                    },
                    required=["path"],
                ),
            ),
            McpTool(
                name="code_lint",
                description="Kod dosyasında sözdizimi ve hata kontrolü yapar.",
                input_schema=McpInputSchema(
                    properties={"path": McpInputProperty(type="string", description="Lint yapılacak dosya yolu")},
                    required=["path"],
                ),
            ),
            McpTool(
                name="git_status",
                description="Git reposunun değişiklik durumunu gösterir.",
                input_schema=McpInputSchema(
                    properties={"repo_path": McpInputProperty(type="string", description="Repo dizin yolu")},
                    required=["repo_path"],
                ),
            ),
            McpTool(
                name="git_diff_preview",
                description="Yapılan değişikliklerin özetini gösterir.",
                input_schema=McpInputSchema(
                    properties={"repo_path": McpInputProperty(type="string", description="Repo dizin yolu")},
                    required=["repo_path"],
                ),
            ),
            McpTool(
                name="git_create_branch",
                description="Yeni git branch'i oluşturur.",
                input_schema=McpInputSchema(
                    properties={
                        "repo_path":   McpInputProperty(type="string", description="Repo dizin yolu"),
                        "branch_name": McpInputProperty(type="string", description="Branch adı"),
                    },
                    required=["repo_path", "branch_name"],
                ),
            ),
            McpTool(
                name="git_commit_and_push",
                description="Commit oluşturur ve uzak sunucuya push eder. Onay gerektirir.",
                input_schema=McpInputSchema(
                    properties={
                        "repo_path": McpInputProperty(type="string", description="Repo dizin yolu"),
                        "message":   McpInputProperty(type="string", description="Commit mesajı"),
                        "branch":    McpInputProperty(type="string", description="Hedef branch"),
                    },
                    required=["repo_path", "message", "branch"],
                ),
            ),
            McpTool(
                name="github_create_pull_request",
                description="GitHub'da pull request açar. Onay gerektirir.",
                input_schema=McpInputSchema(
                    properties={
                        "repo":   McpInputProperty(type="string", description="GitHub repo (owner/repo)"),
                        "branch": McpInputProperty(type="string", description="Kaynak branch"),
                        "title":  McpInputProperty(type="string", description="PR başlığı"),
                    },
                    required=["repo", "branch", "title"],
                ),
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> McpToolResult:
        from mcp_servers.code_server import code_server
        try:
            if name == "code_run":
                return McpToolResult.success(code_server.code_run(arguments["path"], arguments.get("language", "python")))
            elif name == "code_lint":
                return McpToolResult.success(code_server.code_lint(arguments["path"]))
            elif name == "git_status":
                return McpToolResult.success(code_server.git_status(arguments["repo_path"]))
            elif name == "git_diff_preview":
                return McpToolResult.success(code_server.git_diff_preview(arguments["repo_path"]))
            elif name == "git_create_branch":
                return McpToolResult.success(code_server.git_create_branch(arguments["repo_path"], arguments["branch_name"]))
            elif name == "git_commit_and_push":
                return McpToolResult.success(code_server.git_commit_and_push(
                    arguments["repo_path"], arguments["message"], arguments["branch"],
                ))
            elif name == "github_create_pull_request":
                return McpToolResult.success(code_server.github_create_pull_request(
                    arguments["repo"], arguments["branch"], arguments["title"],
                ))
            else:
                return McpToolResult.error(f"Bilinmeyen tool: {name}")
        except Exception as exc:
            return McpToolResult.error(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Mail & Calendar MCP Adapter (n8n üzerinden)
# ─────────────────────────────────────────────────────────────────────────────

class MailCalendarMcpServer(McpServer):
    @property
    def server_name(self) -> str:
        return "mail_calendar"

    @property
    def server_description(self) -> str:
        return "Gmail e-posta okuma/gönderme ve Google Calendar etkinlik yönetimi (n8n webhook üzerinden)"

    def list_tools(self) -> list[McpTool]:
        return [
            McpTool(
                name="mail_read_inbox",
                description="Gmail gelen kutusundaki son N e-postayı okur.",
                input_schema=McpInputSchema(
                    properties={"count": McpInputProperty(type="integer", description="Okunacak mail sayısı", default=5)},
                    required=[],
                ),
            ),
            McpTool(
                name="mail_send",
                description="Gmail üzerinden e-posta gönderir. Onay gerektirir.",
                input_schema=McpInputSchema(
                    properties={
                        "to":      McpInputProperty(type="string", description="Alıcı e-posta adresi"),
                        "subject": McpInputProperty(type="string", description="Konu"),
                        "body":    McpInputProperty(type="string", description="Mail içeriği"),
                    },
                    required=["to", "subject", "body"],
                ),
            ),
            McpTool(
                name="mail_extract_meeting",
                description="E-postadan toplantı linki ve tarih/saati çıkarır.",
                input_schema=McpInputSchema(
                    properties={"mail_id": McpInputProperty(type="string", description="Mail ID'si")},
                    required=["mail_id"],
                ),
            ),
            McpTool(
                name="calendar_list_events",
                description="Google Calendar'daki etkinlikleri listeler.",
                input_schema=McpInputSchema(
                    properties={"date": McpInputProperty(type="string", description="Tarih ('bugün', 'yarın' veya YYYY-MM-DD)")},
                    required=["date"],
                ),
            ),
            McpTool(
                name="calendar_add_event",
                description="Google Calendar'a etkinlik ekler. Onay gerektirir.",
                input_schema=McpInputSchema(
                    properties={
                        "title":            McpInputProperty(type="string", description="Etkinlik başlığı"),
                        "date":             McpInputProperty(type="string", description="Tarih (YYYY-MM-DD)"),
                        "time":             McpInputProperty(type="string", description="Saat (HH:MM)"),
                        "duration_minutes": McpInputProperty(type="integer", description="Süre (dakika)", default=60),
                    },
                    required=["title", "date", "time"],
                ),
            ),
            McpTool(
                name="calendar_delete_event",
                description="Google Calendar'dan etkinlik siler. Onay gerektirir.",
                input_schema=McpInputSchema(
                    properties={"event_id": McpInputProperty(type="string", description="Etkinlik ID'si")},
                    required=["event_id"],
                ),
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> McpToolResult:
        from mcp_servers.mail_calendar_server import mail_calendar_server
        try:
            if name == "mail_read_inbox":
                return McpToolResult.success(await mail_calendar_server.mail_read_inbox(arguments.get("count", 5)))
            elif name == "mail_send":
                return McpToolResult.success(await mail_calendar_server.mail_send(
                    arguments["to"], arguments["subject"], arguments["body"],
                ))
            elif name == "mail_extract_meeting":
                return McpToolResult.success(await mail_calendar_server.mail_extract_meeting(arguments["mail_id"]))
            elif name == "calendar_list_events":
                return McpToolResult.success(await mail_calendar_server.calendar_list_events(arguments["date"]))
            elif name == "calendar_add_event":
                return McpToolResult.success(await mail_calendar_server.calendar_add_event(
                    arguments["title"], arguments["date"],
                    arguments["time"], arguments.get("duration_minutes", 60),
                ))
            elif name == "calendar_delete_event":
                return McpToolResult.success(await mail_calendar_server.calendar_delete_event(arguments["event_id"]))
            else:
                return McpToolResult.error(f"Bilinmeyen tool: {name}")
        except Exception as exc:
            return McpToolResult.error(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# App MCP Adapter
# ─────────────────────────────────────────────────────────────────────────────

class AppMcpServer(McpServer):
    @property
    def server_name(self) -> str:
        return "app"

    @property
    def server_description(self) -> str:
        return "Masaüstü uygulama kontrolü: açma, kapatma, çalışan uygulamaları listeleme"

    def list_tools(self) -> list[McpTool]:
        return [
            McpTool(
                name="app_open",
                description="Bir masaüstü uygulamasını açar.",
                input_schema=McpInputSchema(
                    properties={"name": McpInputProperty(type="string", description="Uygulama adı (örn: 'notepad', 'chrome')")},
                    required=["name"],
                ),
            ),
            McpTool(
                name="app_close",
                description="Çalışan bir uygulamayı kapatır.",
                input_schema=McpInputSchema(
                    properties={"name": McpInputProperty(type="string", description="Uygulama adı")},
                    required=["name"],
                ),
            ),
            McpTool(
                name="app_list_running",
                description="Şu anda çalışan uygulamaları listeler.",
                input_schema=McpInputSchema(),
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> McpToolResult:
        from mcp_servers.app_server import app_server
        try:
            if name == "app_open":
                return McpToolResult.success(app_server.app_open(arguments["name"]))
            elif name == "app_close":
                return McpToolResult.success(app_server.app_close(arguments["name"]))
            elif name == "app_list_running":
                return McpToolResult.success(app_server.app_list_running())
            else:
                return McpToolResult.error(f"Bilinmeyen tool: {name}")
        except Exception as exc:
            return McpToolResult.error(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Multimodal MCP Adapter (Faz 6)
# ─────────────────────────────────────────────────────────────────────────────

class MultimodalMcpServer(McpServer):
    @property
    def server_name(self) -> str:
        return "multimodal"

    @property
    def server_description(self) -> str:
        return "Ses tanıma (STT), metin-ses (TTS), görsel açıklama (Vision) ve görsel üretimi (Image Gen)"

    def list_tools(self) -> list[McpTool]:
        return [
            McpTool(
                name="stt_transcribe",
                description="Ses dosyasını metne çevirir (Whisper STT).",
                input_schema=McpInputSchema(
                    properties={
                        "audio_path": McpInputProperty(
                            type="string",
                            description="Ses dosyasının yolu (.wav, .mp3, .ogg)",
                        ),
                    },
                    required=["audio_path"],
                ),
            ),
            McpTool(
                name="tts_speak",
                description="Metni sese çevirir ve WAV dosyası olarak kaydeder.",
                input_schema=McpInputSchema(
                    properties={
                        "text": McpInputProperty(
                            type="string",
                            description="Sese çevrilecek metin",
                        ),
                        "output_path": McpInputProperty(
                            type="string",
                            description="Çıktı dosya yolu (opsiyonel, boş ise geçici dosya)",
                        ),
                    },
                    required=["text"],
                ),
            ),
            McpTool(
                name="vision_describe",
                description="Görsel dosyasını doğal dil açıklamasına çevirir (Ollama Vision).",
                input_schema=McpInputSchema(
                    properties={
                        "image_path": McpInputProperty(
                            type="string",
                            description="Görsel dosyasının yolu (sandbox içinde, .jpg/.png/.webp)",
                        ),
                    },
                    required=["image_path"],
                ),
            ),
            McpTool(
                name="image_generate",
                description="Metin açıklamasından görsel üretir (Stable Diffusion).",
                input_schema=McpInputSchema(
                    properties={
                        "prompt": McpInputProperty(
                            type="string",
                            description="Görsel açıklaması (İngilizce önerilir)",
                        ),
                        "output_path": McpInputProperty(
                            type="string",
                            description="Çıktı dosya yolu (opsiyonel)",
                        ),
                    },
                    required=["prompt"],
                ),
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> McpToolResult:
        try:
            if name == "stt_transcribe":
                from multimodal.stt import stt_transcribe
                return McpToolResult.success(stt_transcribe(arguments["audio_path"]))
            elif name == "tts_speak":
                from multimodal.tts import tts_speak
                return McpToolResult.success(tts_speak(
                    arguments["text"],
                    arguments.get("output_path"),
                ))
            elif name == "vision_describe":
                from multimodal.vision import vision_describe
                return McpToolResult.success(vision_describe(arguments["image_path"]))
            elif name == "image_generate":
                from multimodal.image_gen import image_generate
                return McpToolResult.success(image_generate(
                    arguments["prompt"],
                    arguments.get("output_path"),
                ))
            else:
                return McpToolResult.error(f"Bilinmeyen tool: {name}")
        except Exception as exc:
            return McpToolResult.error(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Tüm adapter'ları kaydet
# ─────────────────────────────────────────────────────────────────────────────

def register_all_servers() -> None:
    """
    Tüm MCP adapter'larını mcp_registry'ye kaydeder.
    FastAPI lifespan'da bir kez çağrılır.
    """
    from mcp_servers.filesystem_server import FilesystemMcpServer
    mcp_registry.register(FilesystemMcpServer())
    mcp_registry.register(DatabaseMcpServer())
    mcp_registry.register(HrMcpServer())
    mcp_registry.register(CodeGitMcpServer())
    mcp_registry.register(MailCalendarMcpServer())
    mcp_registry.register(AppMcpServer())
    mcp_registry.register(MultimodalMcpServer())
    logger.info(
        "MCP registry hazır",
        extra={"servers": [s.server_name for s in mcp_registry.all_servers()]},
    )

