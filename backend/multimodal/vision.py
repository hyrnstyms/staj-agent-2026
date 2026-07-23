"""
multimodal/vision.py
--------------------
Görsel Açıklama — Ollama Vision Model (qwen2-vl veya llava) entegrasyonu.

Görseli base64'e çevirip Ollama'ya gönderir ve
doğal dil açıklaması alır.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx

from config import settings
from core.logger import get_logger

logger = get_logger(__name__)

SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


def vision_describe(image_path: str) -> dict[str, Any]:
    """
    Görseli doğal dil açıklamasına çevirir.

    Ollama vision modelini (qwen2-vl veya llava) kullanır.
    Görsel SANDBOX_ROOT içinde olmalıdır.

    Args:
        image_path: Görsel dosyasının yolu (sandbox içinde)

    Returns:
        {"success": bool, "description": str} veya {"success": False, "error": str}
    """
    logger.info("vision_describe çağrıldı", extra={"path": image_path})

    # Path doğrulama
    target = (settings.SANDBOX_ROOT / image_path).resolve()
    try:
        target.relative_to(settings.SANDBOX_ROOT)
    except ValueError:
        return {
            "success": False,
            "error": "Güvenlik ihlali: Görsel sandbox dışında.",
        }

    if not target.is_file():
        return {"success": False, "error": f"Görsel dosyası bulunamadı: {image_path}"}

    if target.suffix.lower() not in SUPPORTED_FORMATS:
        return {
            "success": False,
            "error": f"Desteklenmeyen görsel formatı: {target.suffix}. Desteklenenler: {SUPPORTED_FORMATS}",
        }

    # Görseli base64'e çevir
    try:
        with open(target, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
    except Exception as exc:
        return {"success": False, "error": f"Görsel okunamadı: {exc}"}

    # Ollama vision model çağrısı
    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.OLLAMA_VISION_MODEL,
                    "messages": [
                        {
                            "role": "user",
                            "content": "Bu görseli Türkçe olarak ayrıntılı açıkla.",
                            "images": [image_data],
                        }
                    ],
                    "stream": False,
                    "options": {"temperature": 0.5},
                },
            )
            response.raise_for_status()
            data = response.json()
            description = data.get("message", {}).get("content", "")

            if not description:
                return {"success": False, "error": "Vision modeli boş yanıt döndürdü."}

            logger.info("vision_describe başarılı", extra={"chars": len(description)})
            return {
                "success": True,
                "description": description,
                "model": settings.OLLAMA_VISION_MODEL,
            }

    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return {
                "success": False,
                "error": (
                    f"Vision modeli '{settings.OLLAMA_VISION_MODEL}' bulunamadı. "
                    f"'ollama pull {settings.OLLAMA_VISION_MODEL}' ile indirin."
                ),
            }
        return {"success": False, "error": f"Ollama API hatası: {exc.response.status_code}"}
    except Exception as exc:
        logger.error(f"vision_describe hatası: {exc}")
        return {"success": False, "error": str(exc)}
