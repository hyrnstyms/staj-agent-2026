"""
mcp_servers/mcp_adapters.py
---------------------------
Tüm MCP server adapter'ları — resmi mcp SDK tipleriyle.

Her adapter sınıfı McpServerBase'i extend eder ve:
    - _define_tools()  → mcp.types.Tool listesi (static)
    - call_tool()      → mcp.types.CallToolResult (async)

Bu dosya import edildiğinde server'lar hazır olur;
register_all_servers() ile mcp_registry'ye kaydedilirler.
FastAPI startup'ta (api/main.py lifespan) bir kez çağrılır.

Kayıtlı server'lar:
    filesystem      — dosya okuma/yazma/silme/listeleme/taşıma
    database        — DB sorgulama/yazma (kısıtlı tablolar)
    hr              — personel, izin yönetimi
    code_git        — kod çalıştırma (Docker sandbox), git/GitHub
    mail_calendar   — e-posta ve takvim (n8n üzerinden)
    app             — masaüstü uygulama kontrolü
    multimodal      — STT, TTS, vision, görsel üretimi (Faz 6)
"""

from __future__ import annotations

from typing import Any

from mcp.types import (
    CallToolResult,
    Tool,
)

from core.mcp_protocol import McpServerBase, mcp_registry
from core.logger import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Filesystem MCP Adapter
# ─────────────────────────────────────────────────────────────────────────────


class FilesystemMcpServer(McpServerBase):
    """Dosya sistemi işlemleri — sandbox korumalı."""

    @property
    def server_name(self) -> str:
        return "filesystem"

    @property
    def server_description(self) -> str:
        return "Sandbox korumalı dosya işlemleri: okuma, yazma, silme, listeleme, taşıma"

    def _define_tools(self) -> list[Tool]:
        return [
            Tool(
                name="file_read",
                description="Belirtilen dosyanın içeriğini okur ve döner.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Okunacak dosyanın yolu (sandbox içinde)",
                        }
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="file_write",
                description="Dosya oluşturur veya üzerine yazar. Onay gerektirir.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Yazılacak dosyanın yolu (sandbox içinde)",
                        },
                        "content": {
                            "type": "string",
                            "description": "Dosyaya yazılacak içerik",
                        },
                    },
                    "required": ["path", "content"],
                },
            ),
            Tool(
                name="file_delete",
                description="Belirtilen dosyayı siler. ⚠️ Geri alınamaz — onay gerektirir.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Silinecek dosyanın yolu (sandbox içinde)",
                        }
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="file_list",
                description="Belirtilen dizindeki dosya ve klasörleri listeler.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Listelenecek dizin (boş bırakılırsa sandbox kökü)",
                        }
                    },
                    "required": [],
                },
            ),
            Tool(
                name="file_move",
                description="Dosyayı taşır veya yeniden adlandırır. Onay gerektirir.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "src": {
                            "type": "string",
                            "description": "Kaynak dosya yolu",
                        },
                        "dst": {
                            "type": "string",
                            "description": "Hedef dosya yolu",
                        },
                    },
                    "required": ["src", "dst"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> CallToolResult:
        from mcp_servers.filesystem_server import filesystem_server as fs

        try:
            if name == "file_read":
                return self.success(fs.file_read(arguments["path"]))
            elif name == "file_write":
                return self.success(fs.file_write(arguments["path"], arguments["content"]))
            elif name == "file_delete":
                return self.success(fs.file_delete(arguments["path"]))
            elif name == "file_list":
                return self.success(fs.file_list(arguments.get("directory", "")))
            elif name == "file_move":
                return self.success(fs.file_move(arguments["src"], arguments["dst"]))
            else:
                return self.error(f"Bilinmeyen tool: {name}")
        except Exception as exc:
            logger.error(f"Filesystem tool hatası [{name}]: {exc}")
            return self.error(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Database MCP Adapter
# ─────────────────────────────────────────────────────────────────────────────


class DatabaseMcpServer(McpServerBase):
    """SQLite veritabanı işlemleri — kısıtlı tablolar korumalı."""

    @property
    def server_name(self) -> str:
        return "database"

    @property
    def server_description(self) -> str:
        return "SQLite veritabanı: tablo listeleme, şema görme, veri sorgulama/ekleme/güncelleme/silme"

    def _define_tools(self) -> list[Tool]:
        return [
            Tool(
                name="db_list_tables",
                description="Veritabanındaki erişilebilir tabloları listeler.",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="db_get_schema",
                description="Belirtilen tablonun sütun şemasını döner.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table": {"type": "string", "description": "Tablo adı"}
                    },
                    "required": ["table"],
                },
            ),
            Tool(
                name="db_query",
                description="Tabloda filtre uygulayarak veri sorgular (serbest SQL değil).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table": {"type": "string", "description": "Tablo adı"},
                        "filters": {
                            "type": "string",
                            "description": 'Filtreler JSON string olarak, örn: {"role": "admin"}',
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maksimum kayıt sayısı (varsayılan: 20)",
                            "default": 20,
                        },
                    },
                    "required": ["table"],
                },
            ),
            Tool(
                name="db_insert",
                description="Tabloya yeni kayıt ekler. Onay gerektirir.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table": {"type": "string", "description": "Tablo adı"},
                        "values": {
                            "type": "string",
                            "description": "Eklenecek değerler JSON string, örn: {\"name\": \"Ali\"}",
                        },
                    },
                    "required": ["table", "values"],
                },
            ),
            Tool(
                name="db_update",
                description="Tabloda belirli bir kaydı günceller. Onay gerektirir.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table": {"type": "string", "description": "Tablo adı"},
                        "id": {"type": "integer", "description": "Güncellenecek kayıt ID'si"},
                        "values": {
                            "type": "string",
                            "description": "Güncellenecek alanlar JSON string",
                        },
                    },
                    "required": ["table", "id", "values"],
                },
            ),
            Tool(
                name="db_delete",
                description="Tablodan belirli bir kaydı siler. ⚠️ Geri alınamaz — onay gerektirir.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table": {"type": "string", "description": "Tablo adı"},
                        "id": {"type": "integer", "description": "Silinecek kayıt ID'si"},
                    },
                    "required": ["table", "id"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> CallToolResult:
        from mcp_servers.database_server import database_server as db_srv

        try:
            if name == "db_list_tables":
                return self.success(db_srv.db_list_tables())
            elif name == "db_get_schema":
                return self.success(db_srv.db_get_schema(arguments["table"]))
            elif name == "db_query":
                import json
                filters = arguments.get("filters")
                if isinstance(filters, str):
                    try:
                        filters = json.loads(filters)
                    except json.JSONDecodeError:
                        filters = {}
                return self.success(
                    db_srv.db_query(
                        arguments["table"],
                        filters=filters or {},
                        limit=arguments.get("limit", 20),
                    )
                )
            elif name == "db_insert":
                import json
                values = arguments.get("values", "{}")
                if isinstance(values, str):
                    values = json.loads(values)
                return self.success(db_srv.db_insert(arguments["table"], values))
            elif name == "db_update":
                import json
                values = arguments.get("values", "{}")
                if isinstance(values, str):
                    values = json.loads(values)
                return self.success(
                    db_srv.db_update(arguments["table"], arguments["id"], values)
                )
            elif name == "db_delete":
                return self.success(db_srv.db_delete(arguments["table"], arguments["id"]))
            else:
                return self.error(f"Bilinmeyen tool: {name}")
        except Exception as exc:
            logger.error(f"Database tool hatası [{name}]: {exc}")
            return self.error(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# HR MCP Adapter
# ─────────────────────────────────────────────────────────────────────────────


class HrMcpServer(McpServerBase):
    """Personel/HR işlemleri — rol bazlı erişim kontrollü."""

    @property
    def server_name(self) -> str:
        return "hr"

    @property
    def server_description(self) -> str:
        return "Personel bilgileri, izin bakiyesi, izin talebi ve onaylama (rol bazlı erişim kontrollü)"

    def _define_tools(self) -> list[Tool]:
        return [
            Tool(
                name="get_employee_leave_balance",
                description="Çalışanın izin bakiyesini sorgular. Kendi verisini herkes görebilir; başkasının verisini sadece HR/Admin görebilir.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Çalışan adı"},
                        "requester": {"type": "string", "description": "Sorguyu yapan kişinin adı (yetki kontrolü için)"},
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="get_employees_on_leave",
                description="Belirli bir tarihte izinli olan çalışanları listeler.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "description": "Tarih (YYYY-MM-DD formatında)"},
                    },
                    "required": ["date"],
                },
            ),
            Tool(
                name="request_leave",
                description="İzin talebi oluşturur. Onay gerektirir.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "employee_name": {"type": "string", "description": "Çalışan adı"},
                        "start_date": {"type": "string", "description": "İzin başlangıç tarihi (YYYY-MM-DD)"},
                        "end_date": {"type": "string", "description": "İzin bitiş tarihi (YYYY-MM-DD)"},
                        "leave_type": {
                            "type": "string",
                            "description": "İzin türü",
                            "enum": ["annual", "sick", "unpaid", "maternity"],
                        },
                    },
                    "required": ["employee_name", "start_date", "end_date", "leave_type"],
                },
            ),
            Tool(
                name="approve_leave",
                description="Bekleyen izin talebini onaylar. ⚠️ Sadece HR/Admin rolü — onay gerektirir.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "request_id": {"type": "integer", "description": "Onaylanacak izin talebi ID'si"},
                        "approver_role": {
                            "type": "string",
                            "description": "Onaylayan kişinin rolü",
                            "enum": ["hr", "admin"],
                        },
                    },
                    "required": ["request_id", "approver_role"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> CallToolResult:
        from mcp_servers.hr_server import hr_server

        try:
            if name == "get_employee_leave_balance":
                return self.success(
                    hr_server.get_employee_leave_balance(
                        arguments["name"],
                        requester=arguments.get("requester", arguments["name"]),
                    )
                )
            elif name == "get_employees_on_leave":
                return self.success(hr_server.get_employees_on_leave(arguments["date"]))
            elif name == "request_leave":
                return self.success(
                    hr_server.request_leave(
                        arguments["employee_name"],
                        arguments["start_date"],
                        arguments["end_date"],
                        arguments["leave_type"],
                    )
                )
            elif name == "approve_leave":
                return self.success(
                    hr_server.approve_leave(
                        arguments["request_id"],
                        arguments["approver_role"],
                    )
                )
            else:
                return self.error(f"Bilinmeyen tool: {name}")
        except Exception as exc:
            logger.error(f"HR tool hatası [{name}]: {exc}")
            return self.error(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Code & Git MCP Adapter
# ─────────────────────────────────────────────────────────────────────────────


class CodeGitMcpServer(McpServerBase):
    """Kod çalıştırma (Docker sandbox) ve Git/GitHub işlemleri."""

    @property
    def server_name(self) -> str:
        return "code_git"

    @property
    def server_description(self) -> str:
        return "Kod çalıştırma (Docker sandbox), lint, git status/diff/branch/commit/push ve GitHub PR"

    def _define_tools(self) -> list[Tool]:
        return [
            Tool(
                name="code_run",
                description="Kodu Docker sandbox içinde güvenli şekilde çalıştırır.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Çalıştırılacak dosya yolu (sandbox içinde)"},
                        "language": {
                            "type": "string",
                            "description": "Programlama dili",
                            "enum": ["python", "javascript", "bash"],
                        },
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="code_lint",
                description="Dosyadaki sözdizim ve kalite hatalarını kontrol eder.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Kontrol edilecek dosya yolu"}
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="git_status",
                description="Git reposunun değişiklik durumunu gösterir.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string", "description": "Git reposunun dizin yolu"}
                    },
                    "required": ["repo_path"],
                },
            ),
            Tool(
                name="git_diff_preview",
                description="Yapılan değişikliklerin özetini (diff) gösterir.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string", "description": "Git reposunun dizin yolu"}
                    },
                    "required": ["repo_path"],
                },
            ),
            Tool(
                name="git_create_branch",
                description="Yeni bir git branch'i oluşturur.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string", "description": "Git reposunun dizin yolu"},
                        "branch_name": {"type": "string", "description": "Yeni branch adı"},
                    },
                    "required": ["repo_path", "branch_name"],
                },
            ),
            Tool(
                name="git_commit_and_push",
                description="Commit oluşturur ve uzak repoya push eder. ⚠️ Onay gerektirir.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string", "description": "Git reposunun dizin yolu"},
                        "message": {"type": "string", "description": "Commit mesajı"},
                        "branch": {"type": "string", "description": "Push yapılacak branch adı"},
                    },
                    "required": ["repo_path", "message", "branch"],
                },
            ),
            Tool(
                name="github_create_pull_request",
                description="GitHub'da Pull Request açar. ⚠️ Onay gerektirir.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string", "description": "GitHub repo adı (owner/repo formatında)"},
                        "branch": {"type": "string", "description": "PR'ın kaynak branch'i"},
                        "title": {"type": "string", "description": "PR başlığı"},
                    },
                    "required": ["repo", "branch", "title"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> CallToolResult:
        from mcp_servers.code_server import code_server

        try:
            if name == "code_run":
                return self.success(
                    code_server.code_run(
                        arguments["path"],
                        language=arguments.get("language", "python"),
                    )
                )
            elif name == "code_lint":
                return self.success(code_server.code_lint(arguments["path"]))
            elif name == "git_status":
                return self.success(code_server.git_status(arguments["repo_path"]))
            elif name == "git_diff_preview":
                return self.success(code_server.git_diff_preview(arguments["repo_path"]))
            elif name == "git_create_branch":
                return self.success(
                    code_server.git_create_branch(
                        arguments["repo_path"],
                        arguments["branch_name"],
                    )
                )
            elif name == "git_commit_and_push":
                return self.success(
                    code_server.git_commit_and_push(
                        arguments["repo_path"],
                        arguments["message"],
                        arguments["branch"],
                    )
                )
            elif name == "github_create_pull_request":
                return self.success(
                    code_server.github_create_pull_request(
                        arguments["repo"],
                        arguments["branch"],
                        arguments["title"],
                    )
                )
            else:
                return self.error(f"Bilinmeyen tool: {name}")
        except Exception as exc:
            logger.error(f"Code/Git tool hatası [{name}]: {exc}")
            return self.error(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Mail & Calendar MCP Adapter
# ─────────────────────────────────────────────────────────────────────────────


class MailCalendarMcpServer(McpServerBase):
    """E-posta ve takvim işlemleri — n8n webhook üzerinden."""

    @property
    def server_name(self) -> str:
        return "mail_calendar"

    @property
    def server_description(self) -> str:
        return "Gmail e-posta okuma/gönderme ve Google Takvim etkinlik yönetimi (n8n üzerinden)"

    def _define_tools(self) -> list[Tool]:
        return [
            Tool(
                name="mail_read_inbox",
                description="Gelen kutusundaki son N e-postayı okur.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "Okunacak e-posta sayısı (varsayılan: 5)",
                            "default": 5,
                        }
                    },
                    "required": [],
                },
            ),
            Tool(
                name="mail_send",
                description="Gmail üzerinden e-posta gönderir. ⚠️ Onay gerektirir.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "to": {"type": "string", "description": "Alıcı e-posta adresi"},
                        "subject": {"type": "string", "description": "E-posta konusu"},
                        "body": {"type": "string", "description": "E-posta içeriği"},
                    },
                    "required": ["to", "subject", "body"],
                },
            ),
            Tool(
                name="mail_extract_meeting",
                description="E-postadan toplantı linki ve tarih/saat bilgisini çıkarır.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "mail_id": {"type": "string", "description": "E-posta ID'si (mail_read_inbox'tan alınır)"}
                    },
                    "required": ["mail_id"],
                },
            ),
            Tool(
                name="calendar_list_events",
                description="Google Takvim'deki etkinlikleri listeler.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "date_from": {
                            "type": "string",
                            "description": "Başlangıç tarihi (YYYY-MM-DD, opsiyonel — bugün varsayılan)",
                        },
                        "date_to": {
                            "type": "string",
                            "description": "Bitiş tarihi (YYYY-MM-DD, opsiyonel — 7 gün sonra varsayılan)",
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="calendar_add_event",
                description="Google Takvim'e yeni etkinlik ekler. ⚠️ Onay gerektirir.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Etkinlik başlığı"},
                        "start": {
                            "type": "string",
                            "description": "Başlangıç zamanı ISO 8601 formatında (örn: 2026-08-01T14:00:00)",
                        },
                        "end": {
                            "type": "string",
                            "description": "Bitiş zamanı ISO 8601 formatında (örn: 2026-08-01T15:00:00)",
                        },
                    },
                    "required": ["title", "start", "end"],
                },
            ),
            Tool(
                name="calendar_delete_event",
                description="Takvim etkinliğini siler. ⚠️ Onay gerektirir.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "event_id": {"type": "string", "description": "Silinecek etkinlik ID'si"}
                    },
                    "required": ["event_id"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> CallToolResult:
        from mcp_servers.mail_calendar_server import mail_calendar_server

        try:
            if name == "mail_read_inbox":
                return self.success(
                    await mail_calendar_server.mail_read_inbox(
                        count=arguments.get("count", 5)
                    )
                )
            elif name == "mail_send":
                return self.success(
                    await mail_calendar_server.mail_send(
                        to=arguments["to"],
                        subject=arguments["subject"],
                        body=arguments["body"],
                    )
                )
            elif name == "mail_extract_meeting":
                return self.success(
                    await mail_calendar_server.mail_extract_meeting(
                        mail_id=arguments["mail_id"]
                    )
                )
            elif name == "calendar_list_events":
                return self.success(
                    await mail_calendar_server.calendar_list_events(
                        date_from=arguments.get("date_from"),
                        date_to=arguments.get("date_to"),
                    )
                )
            elif name == "calendar_add_event":
                return self.success(
                    await mail_calendar_server.calendar_add_event(
                        title=arguments["title"],
                        start=arguments["start"],
                        end=arguments["end"],
                    )
                )
            elif name == "calendar_delete_event":
                return self.success(
                    await mail_calendar_server.calendar_delete_event(
                        event_id=arguments["event_id"]
                    )
                )
            else:
                return self.error(f"Bilinmeyen tool: {name}")
        except Exception as exc:
            logger.error(f"Mail/Calendar tool hatası [{name}]: {exc}")
            return self.error(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# App MCP Adapter
# ─────────────────────────────────────────────────────────────────────────────


class AppMcpServer(McpServerBase):
    """Masaüstü uygulama kontrolü."""

    @property
    def server_name(self) -> str:
        return "app"

    @property
    def server_description(self) -> str:
        return "Masaüstü uygulama kontrolü: açma, kapatma, çalışan uygulamaları listeleme"

    def _define_tools(self) -> list[Tool]:
        return [
            Tool(
                name="app_open",
                description="Bir masaüstü uygulamasını açar (örn: notepad, chrome, calculator).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Uygulama adı (örn: 'notepad', 'chrome', 'calculator', 'vscode')",
                        }
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="app_close",
                description="Çalışan bir uygulamayı kapatır.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Kapatılacak uygulama adı"}
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name="app_list_running",
                description="Şu anda çalışan uygulamaları listeler.",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> CallToolResult:
        from mcp_servers.app_server import app_server

        try:
            if name == "app_open":
                return self.success(app_server.app_open(arguments["name"]))
            elif name == "app_close":
                return self.success(app_server.app_close(arguments["name"]))
            elif name == "app_list_running":
                return self.success(app_server.app_list_running())
            else:
                return self.error(f"Bilinmeyen tool: {name}")
        except Exception as exc:
            logger.error(f"App tool hatası [{name}]: {exc}")
            return self.error(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Multimodal MCP Adapter (Faz 6)
# ─────────────────────────────────────────────────────────────────────────────


class MultimodalMcpServer(McpServerBase):
    """STT, TTS, Vision ve Image Generation — Faz 6'da aktif olacak."""

    @property
    def server_name(self) -> str:
        return "multimodal"

    @property
    def server_description(self) -> str:
        return "Ses tanıma (Whisper STT), metin-ses (Piper TTS), görsel açıklama (qwen2-vl Vision) ve görsel üretimi (Stable Diffusion)"

    def _define_tools(self) -> list[Tool]:
        return [
            Tool(
                name="stt_transcribe",
                description="Ses dosyasını metne çevirir (Whisper STT). [Faz 6]",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "audio_path": {
                            "type": "string",
                            "description": "Ses dosyasının yolu (.wav, .mp3, .ogg — sandbox içinde)",
                        }
                    },
                    "required": ["audio_path"],
                },
            ),
            Tool(
                name="tts_speak",
                description="Metni sese çevirir ve WAV dosyası kaydeder (Piper TTS). [Faz 6]",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Sese çevrilecek metin"},
                        "output_path": {
                            "type": "string",
                            "description": "Çıktı WAV dosya yolu (opsiyonel)",
                        },
                    },
                    "required": ["text"],
                },
            ),
            Tool(
                name="vision_describe",
                description="Görsel dosyasını doğal dil açıklamasına çevirir (qwen2-vl). [Faz 6]",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "image_path": {
                            "type": "string",
                            "description": "Görsel dosyasının yolu (sandbox içinde, .jpg/.png/.webp)",
                        }
                    },
                    "required": ["image_path"],
                },
            ),
            Tool(
                name="image_generate",
                description="Metin açıklamasından görsel üretir (Stable Diffusion). [Faz 6]",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Görsel açıklaması (İngilizce önerilir)",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Çıktı dosya yolu (opsiyonel)",
                        },
                    },
                    "required": ["prompt"],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> CallToolResult:
        try:
            if name == "stt_transcribe":
                from multimodal.stt import stt_transcribe
                return self.success(stt_transcribe(arguments["audio_path"]))
            elif name == "tts_speak":
                from multimodal.tts import tts_speak
                return self.success(
                    tts_speak(arguments["text"], arguments.get("output_path"))
                )
            elif name == "vision_describe":
                from multimodal.vision import vision_describe
                return self.success(vision_describe(arguments["image_path"]))
            elif name == "image_generate":
                from multimodal.image_gen import image_generate
                return self.success(
                    image_generate(arguments["prompt"], arguments.get("output_path"))
                )
            else:
                return self.error(f"Bilinmeyen tool: {name}")
        except NotImplementedError as exc:
            return self.error(f"[Faz 6 - Henüz aktif değil] {exc}")
        except Exception as exc:
            logger.error(f"Multimodal tool hatası [{name}]: {exc}")
            return self.error(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# Tüm adapter'ları kaydet
# ─────────────────────────────────────────────────────────────────────────────


def register_all_servers() -> None:
    """
    Tüm MCP adapter'larını mcp_registry'ye kaydeder.
    FastAPI lifespan'da (api/main.py) bir kez çağrılır.
    """
    from mcp_servers.filesystem_server import FilesystemMcpServer as _FilesystemMcpServer

    mcp_registry.register(_FilesystemMcpServer())
    mcp_registry.register(DatabaseMcpServer())
    mcp_registry.register(HrMcpServer())
    mcp_registry.register(CodeGitMcpServer())
    mcp_registry.register(MailCalendarMcpServer())
    mcp_registry.register(AppMcpServer())
    mcp_registry.register(MultimodalMcpServer())

    logger.info(
        "MCP registry hazır (resmi mcp SDK tipleri aktif)",
        extra={"servers": [s.server_name for s in mcp_registry.all_servers()]},
    )
