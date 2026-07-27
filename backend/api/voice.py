"""
api/voice.py
------------
Sesli komut API endpoint'leri.

Endpoint'ler:
    POST /voice/start     — Wake word dinlemeyi başlat
    POST /voice/stop      — Wake word dinlemeyi durdur
    GET  /voice/status    — Dinleme durumunu sorgula
    POST /voice/command   — Doğrudan sesli komut gönder (wake word olmadan)

WebSocket:
    /ws/voice             — Gerçek zamanlı ses durumu bildirimleri (SSE benzeri)
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from api.auth import verify_api_key
from config import settings
from core.agent import Agent
from core.logger import get_logger
from core.memory import conversation_memory
from db.database import SessionLocal
from db.models import User

logger = get_logger(__name__)

router = APIRouter(prefix="/voice", tags=["Voice"])

# Agent instance
_agent = Agent()


def _get_admin_user(db) -> User:
    """API key doğrulandıktan sonra admin user'ı bul (geçici Faz-1 auth)."""
    user = db.query(User).filter(User.email == "admin@sirket.com").first()
    if user:
        return user
    return User(id=1, name="Admin", email="admin@sirket.com", role="admin")


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic modelleri
# ─────────────────────────────────────────────────────────────────────────────

class VoiceResponse(BaseModel):
    success: bool
    state: str
    message: str


class VoiceStatusResponse(BaseModel):
    running: bool
    state: str
    whisper_model: str
    whisper_loaded: bool
    wake_phrases: list[str]


class VoiceCommandRequest(BaseModel):
    """Doğrudan sesli komut (metin olarak)."""
    text: str
    session_id: str | None = None
    speak_response: bool = True  # Yanıtı sesli okusun mu?


class VoiceCommandResponse(BaseModel):
    success: bool
    command: str
    response: str
    session_id: str
    audio_file: str | None = None  # TTS çıktı dosyası (varsa)


# ─────────────────────────────────────────────────────────────────────────────
# Wake Word aktif bağlantıları (WebSocket üzerinden bildirim)
# ─────────────────────────────────────────────────────────────────────────────

_voice_ws_clients: list[WebSocket] = []


async def _broadcast_voice_event(event_type: str, data: dict[str, Any] = {}) -> None:
    """Tüm bağlı WebSocket istemcilerine voice event gönder."""
    message = {"type": event_type, **data}
    disconnected = []
    for ws in _voice_ws_clients:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        _voice_ws_clients.remove(ws)


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint'ler
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/start", response_model=VoiceResponse)
async def start_listening(
    api_key: str = Depends(verify_api_key),
):
    """
    Wake word dinlemeyi başlatır.

    Arka planda mikrofon sürekli dinler. "Hey Asistan" veya "Pingo"
    duyulduğunda, ardından gelen komutu Whisper ile transkript eder
    ve agent'a gönderir.

    ⚠️ İlk çağrıda Whisper modeli indirilir (~150MB).
    """
    try:
        from multimodal.wake_word import get_detector

        detector = get_detector()

        # Wake word algılandığında agent'a komut gönder
        def on_wake(text: str):
            logger.info(f"🔔 Wake word: {text}")
            asyncio.run_coroutine_threadsafe(
                _broadcast_voice_event("wake_detected", {"text": text}),
                asyncio.get_event_loop(),
            )

        def on_command(command: str):
            logger.info(f"📝 Sesli komut: {command}")
            db = SessionLocal()
            user = _get_admin_user(db)
            db.close()
            asyncio.run_coroutine_threadsafe(
                _handle_voice_command(command, user),
                asyncio.get_running_loop(),
            )

        detector.on_wake = on_wake
        detector.on_command = on_command

        # State değişikliklerini WebSocket'e yayınla
        def on_state(new_state: str, info: dict):
            try:
                loop = asyncio.get_running_loop()
                asyncio.run_coroutine_threadsafe(
                    _broadcast_voice_event("state_change", {
                        "state": new_state,
                        **info,
                    }),
                    loop,
                )
            except RuntimeError:
                pass
            except Exception:
                pass

        detector.on_state_change(on_state)

        result = detector.start()
        return VoiceResponse(**result)

    except Exception as exc:
        logger.error(f"Wake word başlatma hatası: {exc}", exc_info=True)
        return VoiceResponse(
            success=False,
            state="error",
            message=str(exc),
        )


@router.post("/stop", response_model=VoiceResponse)
async def stop_listening(
    api_key: str = Depends(verify_api_key),
):
    """Wake word dinlemeyi durdurur ve Whisper modelini bellekten çıkarır."""
    try:
        from multimodal.wake_word import get_detector
        result = get_detector().stop()

        await _broadcast_voice_event("stopped", {"message": result["message"]})

        return VoiceResponse(**result)
    except Exception as exc:
        return VoiceResponse(success=False, state="error", message=str(exc))


@router.get("/status", response_model=VoiceStatusResponse)
async def get_voice_status(
    api_key: str = Depends(verify_api_key),
):
    """Wake word dinleme durumunu sorgular."""
    try:
        from multimodal.wake_word import get_detector
        status = get_detector().get_status()
        return VoiceStatusResponse(**status)
    except Exception as exc:
        return VoiceStatusResponse(
            running=False,
            state="error",
            whisper_model="base",
            whisper_loaded=False,
            wake_phrases=[],
        )


@router.post("/command", response_model=VoiceCommandResponse)
async def direct_voice_command(
    request: VoiceCommandRequest,
    api_key: str = Depends(verify_api_key),
):
    """
    Doğrudan sesli komut gönderir (wake word olmadan).

    Frontend mikrofon kaydını yapıp STT sonucunu buraya gönderir.
    Agent yanıtı opsiyonel olarak TTS ile sese çevrilir.
    """
    session_id = request.session_id or str(uuid.uuid4())
    db = SessionLocal()
    current_user = _get_admin_user(db)

    logger.info(
        "POST /voice/command",
        extra={"command": request.text[:80], "session": session_id},
    )

    try:
        response = await _agent.chat(
            session_id=session_id,
            message=request.text,
            user_id=current_user.id,
            user_role=current_user.role,
            db=db,
        )

        audio_file = None
        if request.speak_response and response.message:
            audio_file = _speak_response(response.message)

        return VoiceCommandResponse(
            success=True,
            command=request.text,
            response=response.message,
            session_id=session_id,
            audio_file=audio_file,
        )
    except Exception as exc:
        logger.error(f"Sesli komut hatası: {exc}", exc_info=True)
        return VoiceCommandResponse(
            success=False,
            command=request.text,
            response=f"Hata: {exc}",
            session_id=session_id,
        )
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket — gerçek zamanlı ses durumu
# ─────────────────────────────────────────────────────────────────────────────

@router.websocket("/ws")
async def voice_websocket(websocket: WebSocket):
    """
    Gerçek zamanlı ses durumu WebSocket'i.

    Event tipleri:
        state_change   — Wake word detector durumu değişti
        wake_detected  — Wake word algılandı
        command        — Komut algılandı ve agent'a gönderildi
        response       — Agent yanıtı hazır
        stopped        — Dinleme durduruldu
    """
    await websocket.accept()
    _voice_ws_clients.append(websocket)

    try:
        # İlk durum bilgisini gönder
        try:
            from multimodal.wake_word import get_detector
            status = get_detector().get_status()
        except Exception:
            status = {"running": False, "state": "idle"}

        await websocket.send_json({
            "type": "connected",
            "status": status,
        })

        # İstemci mesajlarını dinle (keepalive / kontrol)
        while True:
            data = await websocket.receive_text()
            # Gelecekte: istemciden kontrol komutları
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _voice_ws_clients:
            _voice_ws_clients.remove(websocket)


# ─────────────────────────────────────────────────────────────────────────────
# Yardımcı fonksiyonlar
# ─────────────────────────────────────────────────────────────────────────────

async def _handle_voice_command(command: str, user: User) -> None:
    """Wake word sonrası algılanan komutu agent'a gönder."""
    session_id = f"voice-{uuid.uuid4().hex[:8]}"

    await _broadcast_voice_event("command", {
        "text": command,
        "session_id": session_id,
    })

    db = SessionLocal()
    try:
        response = await _agent.chat(
            session_id=session_id,
            message=command,
            user_id=user.id,
            user_role=user.role,
            db=db,
        )

        # Yanıtı sesli oku
        audio_file = _speak_response(response.message)

        await _broadcast_voice_event("response", {
            "text": response.message,
            "session_id": session_id,
            "audio_file": audio_file,
            "tool_name": response.tool_name,
        })

    except Exception as exc:
        logger.error(f"Voice command hatası: {exc}", exc_info=True)
        await _broadcast_voice_event("error", {"message": str(exc)})
    finally:
        db.close()


def _speak_response(text: str) -> str | None:
    """Agent yanıtını TTS ile sese çevir. Başarısızlıkta None döner."""
    try:
        from multimodal.tts import tts_speak
        result = tts_speak(text)
        if result.get("success"):
            return result.get("file")
    except Exception as exc:
        logger.warning(f"TTS hatası (devam ediliyor): {exc}")
    return None
