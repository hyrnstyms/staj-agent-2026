"""
multimodal/tts.py
-----------------
Metin-Ses Dönüşümü (TTS) — Windows SAPI veya pyttsx3 entegrasyonu.

Sistem TTS motorunu (Windows SAPI5 / macOS say / Linux espeak)
kullanarak metni sese çevirir, wav dosyası olarak kaydeder.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from core.logger import get_logger

logger = get_logger(__name__)


def tts_speak(text: str, output_path: str | None = None) -> dict[str, Any]:
    """
    Metni sese çevirir.

    pyttsx3 yüklüyse sistem TTS motorunu kullanır (offline, Whisper gerekmez).
    Çıktı WAV dosyası olarak kaydedilir.

    Args:
        text        : Sese çevrilecek metin
        output_path : Çıktı dosyası yolu (None ise geçici dosya oluşturulur)

    Returns:
        {"success": bool, "file": str} veya {"success": False, "error": str}
    """
    logger.info("tts_speak çağrıldı", extra={"chars": len(text)})

    if not text.strip():
        return {"success": False, "error": "Boş metin sese çevrilemez."}

    try:
        import pyttsx3  # type: ignore

        engine = pyttsx3.init()
        engine.setProperty("rate", 175)   # konuşma hızı (kelime/dakika)
        engine.setProperty("volume", 0.9)

        if output_path is None:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            output_path = tmp.name
            tmp.close()

        engine.save_to_file(text, output_path)
        engine.runAndWait()

        if Path(output_path).exists() and Path(output_path).stat().st_size > 0:
            logger.info("tts_speak başarılı", extra={"file": output_path})
            return {
                "success": True,
                "file": output_path,
                "message": f"Ses dosyası oluşturuldu: {output_path}",
            }
        else:
            return {"success": False, "error": "Ses dosyası oluşturulamadı (boş çıktı)."}

    except ImportError:
        return {
            "success": False,
            "error": (
                "pyttsx3 modülü yüklü değil. "
                "'pip install pyttsx3' komutuyla yükleyin."
            ),
        }
    except Exception as exc:
        logger.error(f"tts_speak hatası: {exc}")
        return {"success": False, "error": str(exc)}
