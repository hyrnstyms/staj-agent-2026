"""
api/mcp_endpoint.py
-------------------
FastAPI router — MCP protokolünü HTTP üzerinden açar.

Endpoint'ler:
    GET  /mcp/servers          → Kayıtlı tüm server'ların listesi
    GET  /mcp/tools            → Tüm tool'ların standart MCP şeması
    GET  /mcp/tools/{server}   → Belirli server'ın tool listesi
    POST /mcp/call             → Tool çalıştırma (onay mekanizması bypass eder —
                                  sadece yetkilendirilmiş X-API-Key ile çalışır)

Güvenlik:
    - Tüm endpoint'ler X-API-Key header'ı gerektirir (mevcut auth sistemi)
    - call endpoint'i tool_executor üzerinden DEĞİL, doğrudan mcp_registry üzerinden
      çalışır — bu yüzden REQUIRES_APPROVAL kontrolü BURADA yapılır.
    - Bu endpoint öncelikle harici MCP istemcileri (Claude Desktop, VS Code vb.)
      için tasarlanmıştır; iç agent akışı tool_executor'ü kullanmaya devam eder.

Kullanım (Claude Desktop config):
    {
      "mcpServers": {
        "asistan": {
          "url": "http://localhost:8000/mcp",
          "transport": "http",
          "headers": { "X-API-Key": "dev-api-key-change-in-production" }
        }
      }
    }
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import verify_api_key
from core.mcp_protocol import mcp_registry
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/mcp", tags=["MCP"])

# Onay gerektiren tool'lar — mcp/call'dan direkt çağrılırsa reddedilir.
# Bunlar sadece agent akışı (WebSocket chat → tool_executor) üzerinden çalışır.
MCP_REQUIRES_APPROVAL = {
    "file_delete", "file_move", "file_write",
    "db_delete", "db_update", "db_insert",
    "git_commit_and_push", "github_create_pull_request",
    "approve_leave", "request_leave",
    "mail_send",
    "calendar_add_event", "calendar_delete_event",
}


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response modelleri
# ─────────────────────────────────────────────────────────────────────────────

class McpCallRequest(BaseModel):
    tool_name:  str
    arguments:  dict[str, Any] = {}
    """
    Örnek:
        { "tool_name": "file_read", "arguments": { "path": "README.md" } }
    """


class McpCallResponse(BaseModel):
    tool_name:  str
    success:    bool
    result:     Any
    is_error:   bool
    server:     str | None = None


class McpServerInfo(BaseModel):
    name:        str
    description: str
    tool_count:  int


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint'ler
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/servers",
    response_model=list[McpServerInfo],
    summary="Kayıtlı MCP server listesi",
)
async def list_servers(_: str = Depends(verify_api_key)) -> list[McpServerInfo]:
    """Aktif MCP server'ları ve her birinin kaç tool sunduğunu döner."""
    return [
        McpServerInfo(
            name=s.server_name,
            description=s.server_description,
            tool_count=len(s.list_tools()),
        )
        for s in mcp_registry.all_servers()
    ]


@router.get(
    "/tools",
    summary="Tüm tool'ların MCP şeması",
)
async def list_all_tools(_: str = Depends(verify_api_key)) -> dict:
    """
    Tüm server'lardan tool listesini standart MCP formatında döner.
    Claude Desktop ve diğer MCP istemcileri bu endpoint'i kullanır.
    """
    tools = mcp_registry.all_tools()
    return {
        "tools":      tools,
        "tool_count": len(tools),
        "servers":    [s.server_name for s in mcp_registry.all_servers()],
    }


@router.get(
    "/tools/{server_name}",
    summary="Belirli server'ın tool listesi",
)
async def list_server_tools(
    server_name: str,
    _: str = Depends(verify_api_key),
) -> dict:
    """Tek bir server'ın tool listesini döner."""
    server = mcp_registry.get_server(server_name)
    if not server:
        raise HTTPException(
            status_code=404,
            detail=f"MCP server bulunamadı: '{server_name}'. Mevcut: {[s.server_name for s in mcp_registry.all_servers()]}",
        )
    return {
        "server":     server_name,
        "description": server.server_description,
        "tools":      [t.to_dict() for t in server.list_tools()],
    }


@router.post(
    "/call",
    response_model=McpCallResponse,
    summary="MCP tool çalıştır",
)
async def call_tool(
    req: McpCallRequest,
    _: str = Depends(verify_api_key),
) -> McpCallResponse:
    """
    Belirtilen tool'u doğrudan çalıştırır.

    ⚠️  Onay gerektiren tool'lar bu endpoint üzerinden çalışmaz.
    Bunlar için kullanıcı onaylı WebSocket chat akışını kullan.
    """
    # Onay gerektiren tool'ları reddet
    if req.tool_name in MCP_REQUIRES_APPROVAL:
        logger.warning(f"MCP /call — onay gerektiren tool direkt çağrıldı: {req.tool_name}")
        raise HTTPException(
            status_code=403,
            detail=(
                f"'{req.tool_name}' onay gerektiren bir işlem. "
                "Bu tool yalnızca WebSocket chat akışı üzerinden çağrılabilir."
            ),
        )

    # Tool'u bul ve çalıştır
    result = await mcp_registry.call_tool(req.tool_name, req.arguments)

    # Hangi server'dan geldi?
    server_name = None
    for s in mcp_registry.all_servers():
        if s.get_tool(req.tool_name) is not None:
            server_name = s.server_name
            break

    # Loglama
    logger.info(
        f"MCP tool çağrıldı: {req.tool_name}",
        extra={
            "tool": req.tool_name,
            "server": server_name,
            "is_error": result.is_error,
        },
    )

    # İçerik — tek text content varsayılır
    content_text = result.content[0].text if result.content else ""
    try:
        parsed = json.loads(content_text)
    except (json.JSONDecodeError, TypeError):
        parsed = content_text

    return McpCallResponse(
        tool_name=req.tool_name,
        success=not result.is_error,
        result=parsed,
        is_error=result.is_error,
        server=server_name,
    )
