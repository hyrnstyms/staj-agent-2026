"""
integrations/calendar_tools.py
-------------------------------
Google Calendar entegrasyonu — n8n webhook üzerinden etkinlik yönetimi.
"""

from __future__ import annotations

from typing import Any

from integrations.n8n_client import n8n_call


async def calendar_list_events(date: str = "bugün") -> dict[str, Any]:
    """Belirtilen tarihteki etkinlikleri listeler."""
    return await n8n_call("calendar_list_events", {"date": date})


async def calendar_add_event(
    title: str,
    date: str,
    time: str,
    duration_minutes: int = 60,
    meeting_link: str | None = None,
) -> dict[str, Any]:
    """Takvime yeni etkinlik ekler. ⚠️ Onay gerektirir."""
    return await n8n_call("calendar_add_event", {
        "title": title,
        "date": date,
        "time": time,
        "duration_minutes": duration_minutes,
        "meeting_link": meeting_link,
    })


async def calendar_delete_event(event_id: str) -> dict[str, Any]:
    """Takvimden etkinlik siler. ⚠️ Onay gerektirir."""
    return await n8n_call("calendar_delete_event", {"event_id": event_id})
