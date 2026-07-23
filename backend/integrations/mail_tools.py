"""
integrations/mail_tools.py
--------------------------
Gmail entegrasyonu — n8n webhook üzerinden mail okuma, gönderme, toplantı çıkarma.

Bu fonksiyonlar mcp_servers/mail_calendar_server.py'den bağımsız olarak
doğrudan çağrılabilir (test, cron job vb. için).
"""

from __future__ import annotations

from typing import Any

from integrations.n8n_client import n8n_call


async def mail_read_inbox(count: int = 5) -> dict[str, Any]:
    """Gelen kutusundaki son N e-postayı okur."""
    return await n8n_call("mail_read_inbox", {"count": count})


async def mail_send(to: str, subject: str, body: str) -> dict[str, Any]:
    """Gmail üzerinden e-posta gönderir. ⚠️ Onay gerektirir."""
    return await n8n_call("mail_send", {"to": to, "subject": subject, "body": body})


async def mail_extract_meeting(mail_id: str) -> dict[str, Any]:
    """E-postadan toplantı linki ve tarih/saat çıkarır."""
    return await n8n_call("mail_extract_meeting", {"mail_id": mail_id})
