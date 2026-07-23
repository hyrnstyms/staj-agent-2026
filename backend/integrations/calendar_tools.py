"""
integrations/calendar_tools.py
-------------------------------
Google Calendar entegrasyonu — n8n webhook üzerinden etkinlik yönetimi.

Bu fonksiyonlar mcp_servers/mail_calendar_server.py'den bağımsız olarak
doğrudan çağrılabilir (test, cron job vb. için).
"""

from __future__ import annotations

from typing import Any

from integrations.n8n_client import n8n_call


async def calendar_list_events(
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """
    Google Takvim etkinliklerini listeler.

    Args:
        date_from: Başlangıç ISO 8601 (opsiyonel, varsayılan: şimdi)
        date_to:   Bitiş ISO 8601 (opsiyonel, varsayılan: 7 gün sonra)
    """
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    return await n8n_call("calendar_list_events", {
        "date_from": date_from or now.strftime("%Y-%m-%dT%H:%M:%S"),
        "date_to": date_to or (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S"),
    })


async def calendar_add_event(
    title: str,
    start: str,
    end: str,
) -> dict[str, Any]:
    """
    Takvime yeni etkinlik ekler. ⚠️ Onay gerektirir.

    Args:
        title: Etkinlik başlığı
        start: Başlangıç ISO 8601 (örn: '2026-08-01T14:00:00')
        end:   Bitiş ISO 8601   (örn: '2026-08-01T15:00:00')
    """
    return await n8n_call("calendar_add_event", {
        "title": title,
        "start": start,
        "end": end,
    })


async def calendar_delete_event(event_id: str) -> dict[str, Any]:
    """Takvimden etkinlik siler. ⚠️ Onay gerektirir."""
    return await n8n_call("calendar_delete_event", {"event_id": event_id})
