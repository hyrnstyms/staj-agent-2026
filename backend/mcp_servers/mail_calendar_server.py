import httpx
from typing import Any, Dict, List
from config import settings
from core.logger import get_logger

logger = get_logger(__name__)

class MailCalendarServer:
    """
    n8n webhookları üzerinden Mail ve Takvim işlemlerini gerçekleştiren MCP Sunucusu.
    """

    def __init__(self) -> None:
        self.webhook_url = settings.N8N_WEBHOOK_URL
        self.headers = {}
        if settings.N8N_API_KEY:
            self.headers["Authorization"] = f"Bearer {settings.N8N_API_KEY}"

    async def _send_request(self, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """n8n webhook'una ortak istek atma metodu."""
        payload = {
            "action": action,
            "data": data
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers=self.headers,
                    timeout=15.0
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException:
            logger.error(f"n8n webhook timeout (action: {action})")
            return {"success": False, "error": "n8n sunucusuna ulaşılamadı (Zaman Aşımı)."}
        except httpx.HTTPStatusError as e:
            logger.error(f"n8n HTTP hatası (action: {action}): {e.response.text}")
            return {"success": False, "error": f"n8n entegrasyon hatası: {e.response.status_code}"}
        except httpx.RequestError as e:
            logger.error(f"n8n bağlantı hatası (action: {action}): {str(e)}")
            return {"success": False, "error": "n8n sunucusuna ulaşılamadı (Bağlantı Hatası)."}
        except Exception as e:
            logger.error(f"n8n beklenmeyen hata (action: {action}): {str(e)}")
            return {"success": False, "error": f"Beklenmeyen hata: {str(e)}"}

    async def mail_read_inbox(self, count: int = 5) -> Dict[str, Any]:
        """Gelen kutusundaki son e-postaları okur."""
        logger.info("mail_read_inbox çağrıldı", extra={"count": count})
        return await self._send_request("mail_read_inbox", {"count": count})

    async def mail_send(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        """Yeni bir e-posta gönderir. (Onay gerektirir)"""
        logger.info("mail_send çağrıldı", extra={"to": to, "subject": subject})
        return await self._send_request("mail_send", {"to": to, "subject": subject, "body": body})

    async def mail_extract_meeting(self, mail_id: str) -> Dict[str, Any]:
        """E-postadan toplantı linki ve tarih/saat çıkarır."""
        logger.info("mail_extract_meeting çağrıldı", extra={"mail_id": mail_id})
        return await self._send_request("mail_extract_meeting", {"mail_id": mail_id})

    async def calendar_list_events(self, date: str) -> Dict[str, Any]:
        """Belirtilen tarihteki etkinlikleri listeler. (Örn: '2026-07-21' veya 'bugün')"""
        logger.info("calendar_list_events çağrıldı", extra={"date": date})
        return await self._send_request("calendar_list_events", {"date": date})

    async def calendar_add_event(self, title: str, date: str, time: str, duration_minutes: int) -> Dict[str, Any]:
        """Takvime yeni etkinlik ekler. (Onay gerektirir)"""
        logger.info("calendar_add_event çağrıldı", extra={"title": title, "date": date, "time": time})
        return await self._send_request("calendar_add_event", {
            "title": title,
            "date": date,
            "time": time,
            "duration_minutes": duration_minutes
        })

    async def calendar_delete_event(self, event_id: str) -> Dict[str, Any]:
        """Takvimden bir etkinliği siler. (Onay gerektirir)"""
        logger.warning("calendar_delete_event çağrıldı", extra={"event_id": event_id})
        return await self._send_request("calendar_delete_event", {"event_id": event_id})

mail_calendar_server = MailCalendarServer()
