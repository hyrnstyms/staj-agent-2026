"""
core/mcp_protocol.py
--------------------
Resmi MCP (Model Context Protocol) Python SDK entegrasyonu.

Anthropic'in resmi `mcp` paketi (pip install mcp>=1.0.0) kullanılır.
mcp.types modülündeki resmi tipler (Tool, TextContent, CallToolResult)
bu modül aracılığıyla projeye dahil edilir.

Mimari (Embedded MCP):
    Her MCP server McpServerBase sınıfını extend eder.
    FastAPI HTTP endpoint'i doğrudan handler fonksiyonlarını çağırır.
    Bu "embedded" yaklaşımda her server ayrı process yerine FastAPI
    içinde async olarak çalışır — stdio/SSE transport kullanılmaz.

    Dışa açılan HTTP endpoint'ler (api/mcp_endpoint.py) aracılığıyla
    Claude Desktop ve diğer MCP istemcileri sisteme bağlanabilir.

Protokol referansı: https://spec.modelcontextprotocol.io/
SDK:               https://github.com/modelcontextprotocol/python-sdk
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Resmi MCP SDK tiplerini import et
# ─────────────────────────────────────────────────────────────────────────────

from mcp.types import (
    CallToolResult,
    TextContent,
    Tool,
)

# Proje genelinde kullanılabilmesi için re-export
__all__ = [
    "Tool",
    "TextContent",
    "CallToolResult",
    "McpServerBase",
    "McpRegistry",
    "mcp_registry",
]


# ─────────────────────────────────────────────────────────────────────────────
# McpServerBase — Her MCP server'ın implement etmesi gereken soyut sınıf
# ─────────────────────────────────────────────────────────────────────────────


class McpServerBase(ABC):
    """
    Resmi mcp SDK tipleri kullanan MCP server base sınıfı.

    Subclass'lar şunları implement etmelidir:
        - server_name        → str
        - server_description → str
        - _define_tools()    → list[Tool]      (static, __init__'te çağrılır)
        - call_tool()        → CallToolResult  (async, gerçek I/O yapar)

    Kullanım:
        class FilesystemMcpServer(McpServerBase):

            @property
            def server_name(self) -> str:
                return "filesystem"

            @property
            def server_description(self) -> str:
                return "Dosya sistemi işlemleri"

            def _define_tools(self) -> list[Tool]:
                return [
                    Tool(
                        name="file_read",
                        description="Dosya içeriğini okur.",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "Dosya yolu"}
                            },
                            "required": ["path"],
                        },
                    )
                ]

            async def call_tool(self, name: str, arguments: dict) -> CallToolResult:
                if name == "file_read":
                    content = fs.file_read(arguments["path"])
                    return self.success(content)
                return self.error(f"Bilinmeyen tool: {name}")
    """

    def __init__(self) -> None:
        # Tool listesi static — init'te bir kez hesaplanır, cache'lenir
        self._tools: list[Tool] = self._define_tools()

    # ── Soyut özellikler ────────────────────────────────────────────────────

    @property
    @abstractmethod
    def server_name(self) -> str:
        """Server kimliği — örn: 'filesystem', 'database'"""

    @property
    @abstractmethod
    def server_description(self) -> str:
        """Server'ın ne yaptığının kısa açıklaması."""

    @abstractmethod
    def _define_tools(self) -> list[Tool]:
        """
        Bu server'ın sunduğu tool listesini tanımlar.
        Static veriler döner — init'te bir kez çağrılır.
        mcp.types.Tool nesneleri kullanılır.
        """

    @abstractmethod
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> CallToolResult:
        """
        Verilen tool'u çalıştırır.
        mcp.types.CallToolResult döner.
        Hata durumunda self.error() yardımcısı kullanılır.
        """

    # ── Mevcut tool'ları sorgulama ──────────────────────────────────────────

    def list_tools(self) -> list[Tool]:
        """Bu server'ın sunduğu mcp.types.Tool listesini döner (cache'lenmiş)."""
        return self._tools

    def get_tool(self, name: str) -> Tool | None:
        """İsme göre tek tool döner."""
        return next((t for t in self._tools if t.name == name), None)

    # ── Sonuç yardımcıları ──────────────────────────────────────────────────

    @staticmethod
    def success(data: Any) -> CallToolResult:
        """
        Başarılı tool sonucu oluşturur.
        dict/list → JSON string'e otomatik çevrilir.
        """
        import json

        if not isinstance(data, str):
            data = json.dumps(data, ensure_ascii=False, default=str)
        return CallToolResult(content=[TextContent(type="text", text=data)])

    @staticmethod
    def error(message: str) -> CallToolResult:
        """Hata sonucu oluşturur (isError=True)."""
        return CallToolResult(
            content=[TextContent(type="text", text=message)],
            isError=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# McpRegistry — Tüm server'ları merkezi kayıt
# ─────────────────────────────────────────────────────────────────────────────


class McpRegistry:
    """
    Tüm aktif MCP server'ları merkezi olarak tutar.
    FastAPI endpoint'i (api/mcp_endpoint.py) ve tool_executor bu
    kayıttan server'ları bulup çağırır.
    """

    def __init__(self) -> None:
        self._servers: dict[str, McpServerBase] = {}

    def register(self, server: McpServerBase) -> None:
        """Bir MCP server'ı kayıt altına alır."""
        self._servers[server.server_name] = server

    def get_server(self, name: str) -> McpServerBase | None:
        """İsme göre server döner."""
        return self._servers.get(name)

    def all_servers(self) -> list[McpServerBase]:
        """Kayıtlı tüm server'ların listesini döner."""
        return list(self._servers.values())

    def all_tools(self) -> list[dict]:
        """
        Tüm server'lardan tool şemalarını birleştirir.
        FastAPI GET /mcp/tools endpoint'i bu metodu kullanır.
        Tool dict'lerine '_server' anahtarı eklenir.
        """
        tools = []
        for server in self._servers.values():
            for tool in server.list_tools():
                entry = tool.model_dump()
                entry["_server"] = server.server_name
                tools.append(entry)
        return tools

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> CallToolResult:
        """
        Tool adından doğru server'ı bulup async olarak çalıştırır.
        Tool bulunamazsa isError=True döner.
        """
        for server in self._servers.values():
            if server.get_tool(tool_name) is not None:
                return await server.call_tool(tool_name, arguments)

        return CallToolResult(
            content=[TextContent(type="text", text=f"Tool bulunamadı: '{tool_name}'")],
            isError=True,
        )


# Tekil global registry örneği — tüm proje bu nesneyi kullanır
mcp_registry = McpRegistry()
