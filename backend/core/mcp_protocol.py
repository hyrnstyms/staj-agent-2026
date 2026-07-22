"""
core/mcp_protocol.py
--------------------
Anthropic MCP (Model Context Protocol) uyumlu tool interface.

Her MCP server'ın implement etmesi gereken:
    - list_tools()  → Standart MCP tool schema listesi döner
    - call_tool()   → Tool çalıştırır, MCP formatında sonuç döner

Bu modül ayrıca MCP JSON-RPC mesaj formatlarını tanımlar.
FastAPI endpoint'i (api/mcp_endpoint.py) bu protokolü HTTP üzerinden açar.

Protokol referansı: https://spec.modelcontextprotocol.io/
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


# ─────────────────────────────────────────────────────────────────────────────
# MCP Tool Schema Tipleri
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class McpInputProperty:
    """Bir tool parametresinin JSON Schema tanımı."""
    type: str                          # "string" | "integer" | "boolean" | "number"
    description: str
    enum: list[str] | None = None      # İzin verilen değerler (varsa)
    default: Any = None


@dataclass
class McpInputSchema:
    """Tool'un giriş parametreleri şeması (JSON Schema subset)."""
    type: Literal["object"] = "object"
    properties: dict[str, McpInputProperty] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        props = {}
        for name, prop in self.properties.items():
            p: dict[str, Any] = {"type": prop.type, "description": prop.description}
            if prop.enum:
                p["enum"] = prop.enum
            if prop.default is not None:
                p["default"] = prop.default
            props[name] = p
        return {
            "type": self.type,
            "properties": props,
            "required": self.required,
        }


@dataclass
class McpTool:
    """Tek bir MCP tool tanımı."""
    name: str
    description: str
    input_schema: McpInputSchema

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema.to_dict(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# MCP İçerik Tipleri (tool sonucu)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class McpTextContent:
    text: str
    type: Literal["text"] = "text"

    def to_dict(self) -> dict:
        return {"type": self.type, "text": self.text}


@dataclass
class McpToolResult:
    """Tool çalıştırma sonucu — MCP formatında."""
    content: list[McpTextContent]
    is_error: bool = False

    def to_dict(self) -> dict:
        return {
            "content": [c.to_dict() for c in self.content],
            "isError": self.is_error,
        }

    @classmethod
    def success(cls, text: str) -> "McpToolResult":
        import json
        # dict/list ise JSON string'e çevir
        if not isinstance(text, str):
            text = json.dumps(text, ensure_ascii=False, default=str)
        return cls(content=[McpTextContent(text=text)])

    @classmethod
    def error(cls, message: str) -> "McpToolResult":
        return cls(content=[McpTextContent(text=message)], is_error=True)


# ─────────────────────────────────────────────────────────────────────────────
# MCP Server Base Sınıfı
# ─────────────────────────────────────────────────────────────────────────────

class McpServer(ABC):
    """
    Her MCP server'ın implement etmesi gereken soyut sınıf.

    Kullanım:
        class FilesystemServer(McpServer):
            def list_tools(self) -> list[McpTool]:
                return [McpTool(name="file_read", ...)]

            async def call_tool(self, name: str, arguments: dict) -> McpToolResult:
                if name == "file_read":
                    ...
    """

    @property
    @abstractmethod
    def server_name(self) -> str:
        """Server kimliği — örn: "filesystem", "database" """

    @property
    @abstractmethod
    def server_description(self) -> str:
        """Server'ın ne yaptığının kısa açıklaması."""

    @abstractmethod
    def list_tools(self) -> list[McpTool]:
        """Bu server'ın sunduğu tool listesini döner."""

    @abstractmethod
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> McpToolResult:
        """Verilen tool'u çalıştırır ve MCP formatında sonuç döner."""

    def get_tool(self, name: str) -> McpTool | None:
        """İsme göre tek tool döner."""
        return next((t for t in self.list_tools() if t.name == name), None)


# ─────────────────────────────────────────────────────────────────────────────
# MCP Registry — Tüm server'ları merkezi kayıt
# ─────────────────────────────────────────────────────────────────────────────

class McpRegistry:
    """
    Tüm aktif MCP server'ları tutar.
    FastAPI endpoint'i ve tool_executor bu kayıttan server'ları bulur.
    """

    def __init__(self) -> None:
        self._servers: dict[str, McpServer] = {}

    def register(self, server: McpServer) -> None:
        """Server'ı kaydet."""
        self._servers[server.server_name] = server

    def get_server(self, name: str) -> McpServer | None:
        return self._servers.get(name)

    def all_servers(self) -> list[McpServer]:
        return list(self._servers.values())

    def all_tools(self) -> list[dict]:
        """Tüm server'lardan tool listesi — FastAPI /mcp/tools için."""
        tools = []
        for server in self._servers.values():
            for tool in server.list_tools():
                entry = tool.to_dict()
                entry["_server"] = server.server_name  # Hangi server'dan geldiği
                tools.append(entry)
        return tools

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> McpToolResult:
        """Tool adından doğru server'ı bulup çalıştırır."""
        for server in self._servers.values():
            if server.get_tool(tool_name) is not None:
                return await server.call_tool(tool_name, arguments)
        return McpToolResult.error(f"Tool bulunamadı: '{tool_name}'")


# Tekil global registry örneği
mcp_registry = McpRegistry()
