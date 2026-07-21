import pytest
import httpx
from unittest.mock import patch, AsyncMock
from mcp_servers.mail_calendar_server import mail_calendar_server

@pytest.fixture
def mock_httpx_post():
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        from unittest.mock import MagicMock
        # Başarılı JSON dönüşünü simüle et
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "data": "mock_data"}
        mock_response.raise_for_status = lambda: None
        mock_post.return_value = mock_response
        yield mock_post

@pytest.mark.asyncio
async def test_mail_read_inbox(mock_httpx_post):
    result = await mail_calendar_server.mail_read_inbox(count=3)
    assert result["success"] is True
    assert result["data"] == "mock_data"
    
    # n8n'e gönderilen payload'u kontrol et
    mock_httpx_post.assert_called_once()
    args, kwargs = mock_httpx_post.call_args
    assert kwargs["json"]["action"] == "mail_read_inbox"
    assert kwargs["json"]["data"]["count"] == 3

@pytest.mark.asyncio
async def test_mail_send(mock_httpx_post):
    result = await mail_calendar_server.mail_send(
        to="test@example.com",
        subject="Merhaba",
        body="Deneme"
    )
    assert result["success"] is True
    
    args, kwargs = mock_httpx_post.call_args
    assert kwargs["json"]["action"] == "mail_send"
    assert kwargs["json"]["data"]["to"] == "test@example.com"
    assert kwargs["json"]["data"]["subject"] == "Merhaba"

@pytest.mark.asyncio
async def test_calendar_add_event(mock_httpx_post):
    result = await mail_calendar_server.calendar_add_event(
        title="Toplantı",
        date="2026-08-01",
        time="14:00",
        duration_minutes=30
    )
    assert result["success"] is True
    
    args, kwargs = mock_httpx_post.call_args
    assert kwargs["json"]["action"] == "calendar_add_event"
    assert kwargs["json"]["data"]["title"] == "Toplantı"

@pytest.mark.asyncio
async def test_n8n_timeout_error():
    # Timeout durumunda sunucunun çökmemesi, anlamlı hata dönmesi testi
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout!")):
        result = await mail_calendar_server.calendar_list_events(date="bugün")
        assert result["success"] is False
        assert "Zaman Aşımı" in result["error"]
