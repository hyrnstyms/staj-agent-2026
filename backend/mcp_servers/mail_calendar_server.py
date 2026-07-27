"""
mcp_servers/mail_calendar_server.py
-------------------------------------
Mail ve Takvim işlemlerini n8n webhook'ları üzerinden gerçekleştiren server.

Bu modül tek gerçek n8n implementasyonudur.
integrations/n8n_client.py bu modülün ince wrapper'ı haline getirilmiştir.

Token yönetimi:
    Her çağrı önce integrations.google_oauth.get_valid_access_token() ile
    o kullanıcının güncel access_token'ını alır.
    n8n'e giden payload: {"action": ..., "access_token": "<token>", ...}
    n8n workflow'u HTTP Request node'larında Authorization header olarak kullanır:
        Authorization: Bearer {{ $json.body.access_token }}

Gmail API notu (mail_send):
    Gmail API /messages/send endpoint'i raw MIME mesajı base64url-encode
    edilmiş olarak bekler — düz to/subject/body JSON kabul etmez.
    Bu encode işlemi burada yapılır, n8n'e hazır "raw" string gönderilir.

Gmail API notu (mail_read_inbox):
    messages.list endpoint'i sadece mesaj ID listesi döner.
    n8n workflow'unda bir Code node ile her ID için messages.get çağrısı yapılır.
"""

import base64
import email.message
from typing import Any, Dict

import httpx

from config import settings
from core.logger import get_logger

logger = get_logger(__name__)


class MailCalendarServer:
    """
    n8n webhook'ları üzerinden Mail ve Takvim işlemlerini gerçekleştiren server.

    Tüm metodlar user_id ve db alır; token'ı integrations.google_oauth'tan çeker.
    n8n Switch node'u $json.body.action okur, diğer alanlar $json.body.* ile okunur.
    """

    def __init__(self) -> None:
        self.webhook_url = settings.N8N_WEBHOOK_URL.replace("localhost", "127.0.0.1")
        self._n8n_headers: dict[str, str] = {}
        if settings.N8N_API_KEY:
            self._n8n_headers["Authorization"] = f"Bearer {settings.N8N_API_KEY}"

    # ── İç yardımcı ─────────────────────────────────────────────────────────

    async def _call(
        self,
        action: str,
        data: Dict[str, Any],
        user_id: int,
        db: Any,
    ) -> Dict[str, Any]:
        """
        n8n webhook'una istek atar.

        Token çekme:
            get_valid_access_token() çağrısı başarısız olursa (hesap bağlı değil,
            invalid_grant vb.) {"success": False, "error": "..."} döner.

        Payload formatı (flat):
            {"action": action, "access_token": "<token>", "field1": val1, ...}
        """
        # 1) Kullanıcının geçerli Google access token'ını al
        try:
            from integrations.google_oauth import get_valid_access_token
            access_token = await get_valid_access_token(user_id=user_id, db=db)
        except ValueError as e:
            logger.warning(f"Google token alınamadı (action={action}): {e}")
            return {"success": False, "error": str(e)}

        # 2) n8n'e gönder
        payload = {"action": action, "access_token": access_token, **data}
        logger.info(f"n8n çağrısı: {action}", extra={"webhook": self.webhook_url})

        try:
            async with httpx.AsyncClient(timeout=15.0, proxy=None, trust_env=False) as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers=self._n8n_headers,
                )
                response.raise_for_status()
                return response.json()

        except httpx.TimeoutException:
            logger.error(f"n8n timeout (action={action})")
            return {"success": False, "error": "n8n sunucusuna ulaşılamadı (Zaman Aşımı)."}
        except httpx.HTTPStatusError as exc:
            logger.error(f"n8n HTTP hatası (action={action}): {exc.response.status_code}")
            return {"success": False, "error": f"n8n entegrasyon hatası: {exc.response.status_code}"}
        except httpx.RequestError as exc:
            logger.error(f"n8n bağlantı hatası (action={action}): {exc}")
            return {
                "success": False,
                "error": "n8n sunucusuna ulaşılamadı. docker-compose up -d n8n ile başlatın.",
            }
        except Exception as exc:
            logger.error(f"n8n beklenmeyen hata (action={action}): {exc}")
            return {"success": False, "error": str(exc)}

    # ── Mail ────────────────────────────────────────────────────────────────

    async def mail_read_inbox(
        self, count: int = 5, *, user_id: int, db: Any
    ) -> Dict[str, Any]:
        """
        Gelen kutusundaki son N e-postayı okur.

        n8n workflow notu:
            messages.list sadece ID döner. n8n'deki Code node her ID için
            messages.get çağrısı yapar ve subject/from/snippet toplar.
        """
        logger.info("mail_read_inbox çağrıldı", extra={"count": count, "user_id": user_id})
        return await self._call("mail_read_inbox", {"count": count}, user_id=user_id, db=db)

    async def mail_send(
        self,
        to: str,
        subject: str,
        body: str,
        *,
        user_id: int,
        db: Any,
    ) -> Dict[str, Any]:
        """
        Gmail üzerinden e-posta gönderir. ⚠️ Onay gerektirir.

        Gmail API notu:
            /messages/send endpoint'i base64url-encoded RFC 2822 MIME mesajı bekler.
            Burada encode yapılır, n8n'e hazır "raw" string gönderilir.
            n8n HTTP Request node'unda body: {"raw": "{{ $json.body.raw }}"} kullanılır.
        """
        logger.info("mail_send çağrıldı", extra={"to": to, "subject": subject, "user_id": user_id})

        # RFC 2822 MIME mesajı oluştur + base64url encode
        msg = email.message.EmailMessage()
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        raw_bytes = msg.as_bytes()
        raw_b64 = base64.urlsafe_b64encode(raw_bytes).decode("utf-8")

        return await self._call(
            "mail_send",
            {"to": to, "subject": subject, "raw": raw_b64},
            user_id=user_id,
            db=db,
        )

    async def mail_extract_meeting(
        self, mail_id: str, *, user_id: int, db: Any
    ) -> Dict[str, Any]:
        """E-postadan toplantı linki ve tarih/saat bilgisini çıkarır."""
        logger.info("mail_extract_meeting çağrıldı", extra={"mail_id": mail_id})
        return await self._call(
            "mail_extract_meeting", {"mail_id": mail_id}, user_id=user_id, db=db
        )

    # ── Takvim ──────────────────────────────────────────────────────────────

    async def calendar_list_events(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        *,
        user_id: int,
        db: Any,
    ) -> Dict[str, Any]:
        """
        Google Takvim'deki etkinlikleri listeler.

        n8n HTTP Request node URL:
            GET https://www.googleapis.com/calendar/v3/calendars/primary/events
                ?timeMin={{ $json.body.date_from }}&timeMax={{ $json.body.date_to }}
                &singleEvents=true&orderBy=startTime
        """
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        data: Dict[str, Any] = {
            "date_from": date_from or now.strftime("%Y-%m-%dT%H:%M:%S"),
            "date_to": date_to or (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S"),
        }
        logger.info("calendar_list_events çağrıldı", extra={**data, "user_id": user_id})
        return await self._call("calendar_list_events", data, user_id=user_id, db=db)

    async def calendar_add_event(
        self,
        title: str,
        start: str,
        end: str,
        *,
        user_id: int,
        db: Any,
    ) -> Dict[str, Any]:
        """
        Google Takvim'e yeni etkinlik ekler. ⚠️ Onay gerektirir.

        n8n HTTP Request node URL:
            POST https://www.googleapis.com/calendar/v3/calendars/primary/events
            Body: {"summary": "{{ $json.body.title }}", "start": {...}, "end": {...}}
        """
        logger.info(
            "calendar_add_event çağrıldı",
            extra={"title": title, "start": start, "end": end, "user_id": user_id},
        )
        return await self._call(
            "calendar_add_event",
            {"title": title, "start": start, "end": end},
            user_id=user_id,
            db=db,
        )

    async def calendar_delete_event(
        self, event_id: str, *, user_id: int, db: Any
    ) -> Dict[str, Any]:
        """
        Takvim etkinliğini siler. ⚠️ Onay gerektirir.

        n8n HTTP Request node URL:
            DELETE https://www.googleapis.com/calendar/v3/calendars/primary/events/{{ $json.body.event_id }}
        """
        logger.warning(
            "calendar_delete_event çağrıldı",
            extra={"event_id": event_id, "user_id": user_id},
        )
        return await self._call(
            "calendar_delete_event", {"event_id": event_id}, user_id=user_id, db=db
        )


mail_calendar_server = MailCalendarServer()
