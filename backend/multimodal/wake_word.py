"""
multimodal/wake_word.py
-----------------------
"Hey Asistan" sesli uyanma kelimesi (Wake Word) tespit sistemi.

Yaklaşım:
    1. Mikrofon sürekli dinlenir (speech_recognition ile)
    2. Ses algılandığında Whisper ile transkript yapılır
    3. Transkript "hey asistan", "asistan" veya "merhaba asistan" içeriyorsa tetiklenir
    4. Tetiklendiğinde callback çağrılır (asıl komutu dinlemeye başlar)

Bağımlılıklar:
    pip install SpeechRecognition pyaudio openai-whisper

Not:
    - pyaudio macOS'te: brew install portaudio && pip install pyaudio
    - Whisper modeli ilk çağrıda indirilir (~150MB base model)
    - Tamamen yerel çalışır, internet gerekmez
"""

from __future__ import annotations

import io
import os
import queue
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Any, Callable

from core.logger import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Wake word anahtar kelimeleri (Türkçe + İngilizce varyasyonlar)
# ─────────────────────────────────────────────────────────────────────────────

WAKE_PHRASES = [
    "hey asistan",
    "hey assistant",
    "asistan",
    "merhaba asistan",
    "selam asistan",
    "pingo",        # Maskot adı
    "hey pingo",
]


class WakeWordDetector:
    """
    Sürekli mikrofon dinleyerek wake word tespit eden sınıf.

    Kullanım:
        detector = WakeWordDetector(on_wake=my_callback)
        detector.start()   # Arka planda dinlemeye başla
        ...
        detector.stop()    # Durdur
    """

    def __init__(
        self,
        on_wake: Callable[[str], None] | None = None,
        on_command: Callable[[str], None] | None = None,
        whisper_model: str = "base",
        energy_threshold: int = 300,
        pause_threshold: float = 1.0,
        listen_timeout: float = 5.0,
        command_timeout: float = 10.0,
    ) -> None:
        """
        Args:
            on_wake:          Wake word algılandığında çağrılır (transkript ile)
            on_command:       Wake word sonrası komut algılandığında çağrılır
            whisper_model:    Whisper model boyutu ("tiny", "base", "small", "medium")
            energy_threshold: Mikrofon sessizlik eşiği
            pause_threshold:  Konuşma bitişi bekleme süresi (saniye)
            listen_timeout:   Ses bekleme timeout'u (saniye)
            command_timeout:  Komut dinleme timeout'u (saniye)
        """
        self.on_wake = on_wake
        self.on_command = on_command
        self.whisper_model_name = whisper_model
        self.energy_threshold = energy_threshold
        self.pause_threshold = pause_threshold
        self.listen_timeout = listen_timeout
        self.command_timeout = command_timeout

        self._whisper_model = None
        self._recognizer = None
        self._microphone = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._state = "idle"  # idle, listening, wake_detected, command_listening
        self._state_callbacks: list[Callable[[str, dict], None]] = []

    # ── State yönetimi ────────────────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    @state.setter
    def state(self, value: str) -> None:
        old = self._state
        self._state = value
        logger.info(f"Wake word state: {old} → {value}")
        for cb in self._state_callbacks:
            try:
                cb(value, {"previous": old})
            except Exception as e:
                logger.error(f"State callback hatası: {e}")

    def on_state_change(self, callback: Callable[[str, dict], None]) -> None:
        """State değişikliğinde çağrılacak callback ekle."""
        self._state_callbacks.append(callback)

    @property
    def is_running(self) -> bool:
        return self._running

    # ── Lazy model yükleme ────────────────────────────────────────────────────

    def _load_whisper(self):
        """Whisper modelini lazy-load et (ilk kullanımda)."""
        if self._whisper_model is not None:
            return

        try:
            import whisper  # type: ignore
            logger.info(f"Whisper modeli yükleniyor: {self.whisper_model_name}")
            self._whisper_model = whisper.load_model(self.whisper_model_name)
            logger.info("Whisper modeli hazır")
        except ImportError:
            raise RuntimeError(
                "Whisper yüklü değil. Yüklemek için:\n"
                "  pip install openai-whisper\n"
                "macOS'te ayrıca ffmpeg gerekir:\n"
                "  brew install ffmpeg"
            )

    def _init_recognizer(self):
        """speech_recognition'ı başlat."""
        if self._recognizer is not None:
            return

        try:
            import speech_recognition as sr  # type: ignore
            self._recognizer = sr.Recognizer()
            self._recognizer.energy_threshold = self.energy_threshold
            self._recognizer.pause_threshold = self.pause_threshold
            self._recognizer.dynamic_energy_threshold = True
            self._microphone = sr.Microphone()
            logger.info("Mikrofon hazır")
        except ImportError:
            raise RuntimeError(
                "SpeechRecognition yüklü değil. Yüklemek için:\n"
                "  pip install SpeechRecognition pyaudio\n"
                "macOS'te ayrıca:\n"
                "  brew install portaudio"
            )
        except OSError as e:
            raise RuntimeError(
                f"Mikrofon bulunamadı: {e}\n"
                "pyaudio kurulumu:\n"
                "  brew install portaudio && pip install pyaudio"
            )

    # ── Ses → Metin dönüşümü ─────────────────────────────────────────────────

    def _transcribe_audio(self, audio_data) -> str:
        """speech_recognition AudioData nesnesini Whisper ile transkript et."""
        import speech_recognition as sr  # type: ignore

        # AudioData → WAV bytes → geçici dosya → Whisper
        wav_bytes = audio_data.get_wav_data()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name

        try:
            result = self._whisper_model.transcribe(
                tmp_path,
                language="tr",  # Türkçe öncelikli
                fp16=False,     # CPU uyumluluğu
            )
            text = result.get("text", "").strip().lower()
            return text
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _is_wake_word(self, text: str) -> bool:
        """Transkript wake word içeriyor mu?"""
        text_clean = text.lower().strip()
        for phrase in WAKE_PHRASES:
            if phrase in text_clean:
                return True
        return False

    # ── Ana dinleme döngüsü ──────────────────────────────────────────────────

    def _listen_loop(self) -> None:
        """Arka plan thread'inde çalışan ana dinleme döngüsü."""
        import speech_recognition as sr  # type: ignore

        logger.info("Wake word dinleme başladı")
        self.state = "listening"

        while self._running:
            try:
                with self._microphone as source:
                    # Ortam gürültüsüne uyum sağla (sadece başlangıçta)
                    if self.state == "listening":
                        try:
                            self._recognizer.adjust_for_ambient_noise(
                                source, duration=0.5
                            )
                        except Exception:
                            pass

                    # Ses bekle
                    try:
                        audio = self._recognizer.listen(
                            source,
                            timeout=self.listen_timeout,
                            phrase_time_limit=3,  # Wake word kısa bir cümle
                        )
                    except sr.WaitTimeoutError:
                        continue  # Ses yok, tekrar dene

                # Whisper ile transkript
                text = self._transcribe_audio(audio)
                if not text:
                    continue

                logger.debug(f"Duyulan: '{text}'")

                # Wake word kontrolü
                if self.state == "listening" and self._is_wake_word(text):
                    logger.info(f"🔔 Wake word algılandı: '{text}'")
                    self.state = "wake_detected"

                    if self.on_wake:
                        self.on_wake(text)

                    # Şimdi asıl komutu dinle
                    self._listen_for_command()

            except Exception as exc:
                if self._running:
                    logger.error(f"Dinleme hatası: {exc}")
                    time.sleep(1)  # Hata sonrası kısa bekleme

        self.state = "idle"
        logger.info("Wake word dinleme durduruldu")

    def _listen_for_command(self) -> None:
        """Wake word algılandıktan sonra asıl komutu dinle."""
        import speech_recognition as sr  # type: ignore

        self.state = "command_listening"
        logger.info("Komut dinleniyor...")

        try:
            with self._microphone as source:
                audio = self._recognizer.listen(
                    source,
                    timeout=self.command_timeout,
                    phrase_time_limit=15,  # Komut daha uzun olabilir
                )

            command_text = self._transcribe_audio(audio)

            if command_text:
                logger.info(f"📝 Komut: '{command_text}'")
                if self.on_command:
                    self.on_command(command_text)
            else:
                logger.info("Komut anlaşılamadı")

        except sr.WaitTimeoutError:
            logger.info("Komut bekleme süresi doldu")
        except Exception as exc:
            logger.error(f"Komut dinleme hatası: {exc}")
        finally:
            self.state = "listening"  # Wake word dinlemeye geri dön

    # ── Başlat / Durdur ──────────────────────────────────────────────────────

    def start(self) -> dict[str, Any]:
        """
        Wake word dinlemeyi başlat (arka plan thread'i).

        Returns:
            {"success": bool, "state": str, "message": str}
        """
        if self._running:
            return {
                "success": True,
                "state": self._state,
                "message": "Zaten dinleniyor.",
            }

        try:
            self._load_whisper()
            self._init_recognizer()
        except RuntimeError as e:
            return {"success": False, "state": "error", "message": str(e)}

        self._running = True
        self._thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name="wake-word-listener",
        )
        self._thread.start()

        return {
            "success": True,
            "state": "listening",
            "message": (
                "Wake word dinleme başladı. "
                "'Hey Asistan' veya 'Pingo' diyerek başlatın."
            ),
        }

    def stop(self) -> dict[str, Any]:
        """
        Wake word dinlemeyi durdur.

        Returns:
            {"success": bool, "state": str, "message": str}
        """
        if not self._running:
            return {
                "success": True,
                "state": "idle",
                "message": "Zaten durdurulmuş.",
            }

        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        # Whisper modelini bellekten çıkar (lazy unload)
        self._whisper_model = None
        self.state = "idle"

        return {
            "success": True,
            "state": "idle",
            "message": "Wake word dinleme durduruldu. Whisper modeli bellekten çıkarıldı.",
        }

    def get_status(self) -> dict[str, Any]:
        """Mevcut durumu döner."""
        return {
            "running": self._running,
            "state": self._state,
            "whisper_model": self.whisper_model_name,
            "whisper_loaded": self._whisper_model is not None,
            "wake_phrases": WAKE_PHRASES,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Tekil (singleton) detector instance — API endpoint'leri bunu kullanır
# ─────────────────────────────────────────────────────────────────────────────

_detector: WakeWordDetector | None = None


def get_detector() -> WakeWordDetector:
    """Tekil WakeWordDetector instance'ını döner (lazy init)."""
    global _detector
    if _detector is None:
        _detector = WakeWordDetector()
    return _detector


def wake_word_listen() -> dict[str, Any]:
    """Geriye uyumluluk — MCP adapter'dan çağrılır."""
    return get_detector().start()
