"""
multimodal/image_gen.py
------------------------
Görsel Üretimi — Ollama / AUTOMATIC1111 Stable Diffusion entegrasyonu.

Varsayılan olarak yerel Ollama API'sini kullanmaya çalışır.
Stable Diffusion için AUTOMATIC1111 WebUI'si çalıştırılmalıdır.
"""

from __future__ import annotations

import base64
import time
from typing import Any

from config import settings
from core.logger import get_logger

logger = get_logger(__name__)


def image_generate(prompt: str, output_path: str | None = None) -> dict[str, Any]:
    """
    Metin açıklamasından görsel üretir.

    AUTOMATIC1111 WebUI veya uyumlu bir API gerektir.
    Görsel sandbox dizinine kaydedilir.

    Args:
        prompt      : Görsel açıklaması (İngilizce önerilir)
        output_path : Çıktı dosyası yolu (None ise sandbox'a otomatik kaydedilir)

    Returns:
        {"success": bool, "file": str, "message": str} veya {"success": False, "error": str}
    """
    logger.info("image_generate çağrıldı", extra={"prompt_preview": prompt[:80]})

    if not prompt.strip():
        return {"success": False, "error": "Boş prompt ile görsel üretilemez."}

    # Çıktı yolunu belirle
    if output_path is None:
        timestamp = int(time.time())
        output_file = settings.SANDBOX_ROOT / f"generated_{timestamp}.png"
    else:
        output_file = (settings.SANDBOX_ROOT / output_path).resolve()
        try:
            output_file.relative_to(settings.SANDBOX_ROOT)
        except ValueError:
            return {"success": False, "error": "Güvenlik ihlali: Çıktı sandbox dışında."}

    # AUTOMATIC1111 API (txt2img)
    try:
        import httpx

        a1111_url = "http://localhost:7860"  # AUTOMATIC1111 WebUI varsayılan port

        with httpx.Client(timeout=120) as client:
            response = client.post(
                f"{a1111_url}/sdapi/v1/txt2img",
                json={
                    "prompt": prompt,
                    "negative_prompt": "ugly, blurry, low quality, deformed",
                    "steps": 20,
                    "width": 512,
                    "height": 512,
                    "cfg_scale": 7,
                },
            )
            response.raise_for_status()
            data = response.json()

            images = data.get("images", [])
            if not images:
                return {"success": False, "error": "API görsel döndürmedi."}

            # Base64 → PNG dosyası
            img_data = base64.b64decode(images[0])
            output_file.write_bytes(img_data)

            logger.info("image_generate başarılı", extra={"file": str(output_file)})
            return {
                "success": True,
                "file": str(output_file),
                "message": f"Görsel oluşturuldu: {output_file.name}",
            }

    except ImportError:
        return {"success": False, "error": "httpx modülü bulunamadı."}
    except Exception as exc:
        # AUTOMATIC1111 çalışmıyorsa anlamlı hata ver
        if "Connection refused" in str(exc) or "ConnectError" in str(exc):
            return {
                "success": False,
                "error": (
                    "Görsel üretim servisi (AUTOMATIC1111 WebUI) çalışmıyor. "
                    "Stable Diffusion WebUI'yi başlatın: "
                    "python launch.py --api (port 7860)"
                ),
            }
        logger.error(f"image_generate hatası: {exc}")
        return {"success": False, "error": str(exc)}
