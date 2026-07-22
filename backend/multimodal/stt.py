"""
multimodal/stt.py
-----------------
Ses tanıma (STT) — Ollama Whisper entegrasyonu.

Ollama üzerinden herhangi bir konuşma tanıma API'si mevcut değil;
bu nedenle burada basit bir stub ile "not supported" mesajı dönülür.
Daha gelişmiş kullanım için 'openai-whisper' paketi requirements.txt'te
yorumdan çıkarılabilir.
"""

from __future__ import annotations

from typing import Any

from core.logger import get_logger

logger = get_logger(__name__)


def stt_transcribe(audio_path: str) -> dict[str, Any]:
    """
    Ses dosyasını metne çevirir.

    NOT: Bu özellik yerel Whisper modeli gerektirir.
    Etkinleştirmek için requirements.txt'te 'openai-whisper' satırını
    yorumdan çıkarın ve modeli indirin: whisper.load_model("base")

    Args:
        audio_path: Ses dosyasının yolu (.wav, .mp3, .ogg)

    Returns:
        {"success": bool, "text": str} veya {"success": False, "error": str}
    """
    logger.info("stt_transcribe çağrıldı", extra={"path": audio_path})

    # Whisper yüklüyse kullan, değilse anlamlı hata döndür
    try:
        import whisper  # type: ignore
        from pathlib import Path

        path = Path(audio_path)
        if not path.is_file():
            return {"success": False, "error": f"Ses dosyası bulunamadı: {audio_path}"}

        model = whisper.load_model("base")
        result = model.transcribe(str(path))
        text = result.get("text", "").strip()

        logger.info("stt_transcribe başarılı", extra={"chars": len(text)})
        return {"success": True, "text": text, "language": result.get("language", "unknown")}

    except ImportError:
        return {
            "success": False,
            "error": (
                "Whisper modülü yüklü değil. "
                "requirements.txt'te 'openai-whisper==20240930' satırını "
                "yorumdan çıkarıp 'pip install openai-whisper' çalıştırın."
            ),
        }
    except Exception as exc:
        logger.error(f"stt_transcribe hatası: {exc}")
        return {"success": False, "error": str(exc)}
