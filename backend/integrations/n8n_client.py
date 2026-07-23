"""
integrations/n8n_client.py
--------------------------
n8n webhook istemcisi — mail ve takvim işlemlerini n8n üzerinden yürütür.

Bu modül mcp_servers/mail_calendar_server.py'nin düşük seviyeli HTTP
iletişimini sarmalar. Doğrudan kullanılabilir veya
mail_tools.py / calendar_tools.py üzerinden çağrılabilir.

Kullanım:
    from integrations.n8n_client import n8n_call
    result = await n8n_call("mail_read_inbox", {"count": 5})
"""

from __future__ import annotations

from typing import Any

import httpx

from config import settings
from core.logger import get_logger

logger = get_logger(__name__)


async def n8n_call(action: str, data: dict[str, Any]) -> dict[str, Any]:
    """
    n8n webhook'una istek atar.

    Args:
        action: İşlem adı (mail_read_inbox, mail_send, calendar_add_event vb.)
        data:   İşlem parametreleri

    Returns:
        n8n'den dönen JSON yanıt.
        Bağlantı hatası varsa {"success": False, "error": "..."} döner.
    """
    webhook_url = settings.N8N_WEBHOOK_URL
    headers: dict[str, str] = {}
    if settings.N8N_API_KEY:
        headers["Authorization"] = f"Bearer {settings.N8N_API_KEY}"

    payload = {"action": action, "data": data}

    logger.info(f"n8n çağrısı: {action}", extra={"webhook": webhook_url})

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(webhook_url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        logger.error(f"n8n timeout: {action}")
        return {"success": False, "error": "n8n sunucusuna ulaşılamadı (Zaman Aşımı)."}
    except httpx.HTTPStatusError as e:
        logger.error(f"n8n HTTP hatası: {e.response.status_code}")
        return {"success": False, "error": f"n8n entegrasyon hatası: {e.response.status_code}"}
    except httpx.RequestError as e:
        logger.error(f"n8n bağlantı hatası: {e}")
        return {
            "success": False,
            "error": (
                "n8n sunucusuna ulaşılamadı. "
                "docker-compose up -d n8n ile başlatın."
            ),
        }
    except Exception as e:
        logger.error(f"n8n beklenmeyen hata: {e}")
        return {"success": False, "error": str(e)}
