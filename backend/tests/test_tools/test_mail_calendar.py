"""
tests/test_tools/test_mail_calendar.py
--------------------------------------
mail_calendar_server ve n8n entegrasyonu unit testleri.

Payload formatı: flat yapı (action + diğer alanlar aynı seviyede)
    {"action": "mail_send", "to": "...", "subject": "...", "body": "..."}
"""

import pytest
import httpx
from unittest.mock import patch, AsyncMock, MagicMock

from mcp_servers.mail_calendar_server import mail_calendar_server


@pytest.fixture
def mock_httpx_post():
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success", "message": "İşlem tamamlandı."}
        mock_response.raise_for_status = lambda: None
        mock_post.return_value = mock_response
        yield mock_post


@pytest.mark.asyncio
async def test_mail_read_inbox(mock_httpx_post):
    result = await mail_calendar_server.mail_read_inbox(count=3)
    assert result["status"] == "success"

    mock_httpx_post.assert_called_once()
    _, kwargs = mock_httpx_post.call_args
    payload = kwargs["json"]
    # Flat format: action + parametreler aynı seviyede
    assert payload["action"] == "mail_read_inbox"
    assert payload["count"] == 3
    # Nested "data" wrapper OLMAMALI
    assert "data" not in payload


@pytest.mark.asyncio
async def test_mail_send(mock_httpx_post):
    result = await mail_calendar_server.mail_send(
        to="test@example.com",
        subject="Merhaba",
        body="Deneme mesajı",
    )
    assert result["status"] == "success"

    _, kwargs = mock_httpx_post.call_args
    payload = kwargs["json"]
    assert payload["action"] == "mail_send"
    assert payload["to"] == "test@example.com"
    assert payload["subject"] == "Merhaba"
    assert payload["body"] == "Deneme mesajı"
    assert "data" not in payload


@pytest.mark.asyncio
async def test_mail_extract_meeting(mock_httpx_post):
    result = await mail_calendar_server.mail_extract_meeting(mail_id="abc123")
    assert result["status"] == "success"

    _, kwargs = mock_httpx_post.call_args
    payload = kwargs["json"]
    assert payload["action"] == "mail_extract_meeting"
    assert payload["mail_id"] == "abc123"
    assert "data" not in payload


@pytest.mark.asyncio
async def test_calendar_add_event(mock_httpx_post):
    """calendar_add_event artık start/end ISO8601 string alıyor (date+time+duration değil)."""
    result = await mail_calendar_server.calendar_add_event(
        title="Sprint Toplantısı",
        start="2026-08-01T14:00:00",
        end="2026-08-01T15:00:00",
    )
    assert result["status"] == "success"

    _, kwargs = mock_httpx_post.call_args
    payload = kwargs["json"]
    assert payload["action"] == "calendar_add_event"
    assert payload["title"] == "Sprint Toplantısı"
    assert payload["start"] == "2026-08-01T14:00:00"
    assert payload["end"] == "2026-08-01T15:00:00"
    assert "date" not in payload
    assert "time" not in payload
    assert "data" not in payload


@pytest.mark.asyncio
async def test_calendar_list_events(mock_httpx_post):
    result = await mail_calendar_server.calendar_list_events(
        date_from="2026-08-01T00:00:00",
        date_to="2026-08-07T23:59:59",
    )
    assert result["status"] == "success"

    _, kwargs = mock_httpx_post.call_args
    payload = kwargs["json"]
    assert payload["action"] == "calendar_list_events"
    assert payload["date_from"] == "2026-08-01T00:00:00"
    assert payload["date_to"] == "2026-08-07T23:59:59"
    assert "data" not in payload


@pytest.mark.asyncio
async def test_calendar_delete_event(mock_httpx_post):
    result = await mail_calendar_server.calendar_delete_event(event_id="evt_xyz789")
    assert result["status"] == "success"

    _, kwargs = mock_httpx_post.call_args
    payload = kwargs["json"]
    assert payload["action"] == "calendar_delete_event"
    assert payload["event_id"] == "evt_xyz789"
    assert "data" not in payload


@pytest.mark.asyncio
async def test_n8n_timeout_error():
    """n8n timeout durumunda sunucu çökmemeli, anlamlı hata dönmeli."""
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout!")):
        result = await mail_calendar_server.calendar_list_events()
        assert result["success"] is False
        assert "Zaman Aşımı" in result["error"]


@pytest.mark.asyncio
async def test_n8n_connection_error():
    """n8n sunucusu kapalıyken anlamlı hata mesajı dönmeli."""
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        result = await mail_calendar_server.mail_read_inbox()
        assert result["success"] is False
        assert "n8n" in result["error"].lower() or "ulaşılamadı" in result["error"]
