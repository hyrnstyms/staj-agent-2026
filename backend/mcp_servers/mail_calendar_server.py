import httpx
from typing import Any, Dict
from config import settings
from core.logger import get_logger

logger = get_logger(__name__)


class MailCalendarServer:
    """
    n8n webhook'ları üzerinden Mail ve Takvim işlemlerini gerçekleştiren server.

    n8n Webhook URL: settings.N8N_WEBHOOK_URL
    Payload formatı: {"action": "<eylem>", "<param1>": ..., "<param2>": ...}
        (düz/flat yapı — n8n Switch node'u $json.body.action okur)

    Not: Tüm tool'ların gerçek implementasyonu n8n workflow'u içindedir.
         Bu sınıf yalnızca n8n'e HTTP isteği atar ve cevabı iletir.
    """

    def __init__(self) -> None:
        self.webhook_url = settings.N8N_WEBHOOK_URL
        self.headers: dict[str, str] = {}
        if settings.N8N_API_KEY:
            self.headers["Authorization"] = f"Bearer {settings.N8N_API_KEY}"

    async def _call(self, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        n8n webhook'una istek atar.

        Payload formatı flat:
            {"action": action, "field1": val1, "field2": val2, ...}
        n8n Switch node'u $json.body.action ile eşleşir,
        diğer alanlar $json.body.field1 vb. ile okunur.
        """
        payload = {"action": action, **data}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers=self.headers,
                )
                response.raise_for_status()
                return response.json()

        except httpx.TimeoutException:
            logger.error(f"n8n timeout (action: {action})")
            return {"success": False, "error": "n8n sunucusuna ulaşılamadı (Zaman Aşımı)."}
        except httpx.HTTPStatusError as exc:
            logger.error(f"n8n HTTP hatası (action: {action}): {exc.response.status_code}")
            return {"success": False, "error": f"n8n entegrasyon hatası: {exc.response.status_code}"}
        except httpx.RequestError as exc:
            logger.error(f"n8n bağlantı hatası (action: {action}): {exc}")
            return {
                "success": False,
                "error": "n8n sunucusuna ulaşılamadı. docker-compose up -d n8n ile başlatın.",
            }
        except Exception as exc:
            logger.error(f"n8n beklenmeyen hata (action: {action}): {exc}")
            return {"success": False, "error": str(exc)}

    # ── Mail ────────────────────────────────────────────────────────────────

    async def mail_read_inbox(self, count: int = 5) -> Dict[str, Any]:
        """Gelen kutusundaki son N e-postayı okur."""
        logger.info("mail_read_inbox çağrıldı", extra={"count": count})
        return await self._call("mail_read_inbox", {"count": count})

    async def mail_send(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        """Gmail üzerinden e-posta gönderir. ⚠️ Onay gerektirir."""
        logger.info("mail_send çağrıldı", extra={"to": to, "subject": subject})
        return await self._call("mail_send", {"to": to, "subject": subject, "body": body})

    async def mail_extract_meeting(self, mail_id: str) -> Dict[str, Any]:
        """E-postadan toplantı linki ve tarih/saat bilgisini çıkarır."""
        logger.info("mail_extract_meeting çağrıldı", extra={"mail_id": mail_id})
        return await self._call("mail_extract_meeting", {"mail_id": mail_id})

    # ── Takvim ──────────────────────────────────────────────────────────────

    async def calendar_list_events(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> Dict[str, Any]:
        """Google Takvim'deki etkinlikleri listeler."""
        from datetime import datetime, timedelta

        now = datetime.utcnow()
        data: Dict[str, Any] = {
            "date_from": date_from or now.strftime("%Y-%m-%dT%H:%M:%S"),
            "date_to": date_to or (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S"),
        }
        logger.info("calendar_list_events çağrıldı", extra=data)
        return await self._call("calendar_list_events", data)

    async def calendar_add_event(
        self,
        title: str,
        start: str,
        end: str,
    ) -> Dict[str, Any]:
        """
        Google Takvim'e yeni etkinlik ekler. ⚠️ Onay gerektirir.

        Args:
            title: Etkinlik başlığı
            start: Başlangıç ISO 8601 (örn: '2026-08-01T14:00:00')
            end:   Bitiş ISO 8601   (örn: '2026-08-01T15:00:00')
        """
        logger.info(
            "calendar_add_event çağrıldı",
            extra={"title": title, "start": start, "end": end},
        )
        return await self._call(
            "calendar_add_event",
            {"title": title, "start": start, "end": end},
        )

    async def calendar_delete_event(self, event_id: str) -> Dict[str, Any]:
        """Takvim etkinliğini siler. ⚠️ Onay gerektirir."""
        logger.warning("calendar_delete_event çağrıldı", extra={"event_id": event_id})
        return await self._call("calendar_delete_event", {"event_id": event_id})


mail_calendar_server = MailCalendarServer()
