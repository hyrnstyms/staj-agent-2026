"""
api/websocket.py
----------------
WebSocket endpoint'i — Streaming chat cevapları için.

Bağlantı:
    ws://localhost:8000/ws/chat?session_id=abc123&api_key=dev-api-key-change-in-production

Mesaj formatı (client → server):
    {
        "message": "Kullanıcı mesajı",
        "approval_id": "uuid-or-null"   # opsiyonel
    }

Event formatı (server → client):
    {"type": "token",   "content": "..."}              # LLM stream token'ı
    {"type": "done",    "status": "success", ...}      # Cevap tamamlandı
    {"type": "approval","approval_id": "...", "description": "..."} # Onay gerekiyor
    {"type": "error",   "message": "..."}              # Hata

⚠️  Auth: WebSocket'te HTTP header eklemek yaygın değil,
    bu yüzden api_key query parametresi olarak alınır.
    Production'da WSS + token tabanlı auth kullanılmalı.
"""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from config import settings
from core.agent import Agent
from core.approval import approval_manager
from core.logger import get_logger
from db.database import SessionLocal
from db.models import User

logger = get_logger(__name__)

router = APIRouter()
_agent = Agent()


@router.websocket("/ws/chat")
async def websocket_chat(
    websocket: WebSocket,
    session_id: str | None = None,
    api_key: str | None = None,
):
    """
    WebSocket streaming chat endpoint.

    Query Parameters:
        session_id : Oturum kimliği (boşsa UUID oluşturulur)
        api_key    : API anahtarı (⚠️ Faz 1 geçici auth)
    """
    # Auth kontrolü
    if api_key != settings.API_KEY:
        await websocket.close(code=4001, reason="Geçersiz API key")
        return

    await websocket.accept()

    session_id = session_id or str(uuid.uuid4())
    db: Session = SessionLocal()

    # Demo user
    user = db.query(User).filter(User.email == "admin@sirket.com").first()
    if user is None:
        user = User(id=1, name="Admin", email="admin@sirket.com", role="admin")

    logger.info(
        "WebSocket bağlandı",
        extra={"session": session_id, "user": user.email},
    )

    try:
        # Oturum başlangıç bilgisi gönder
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message": "Asistan bağlantısı kuruldu.",
        })

        while True:
            # Kullanıcı mesajı bekle
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Geçersiz JSON"})
                continue

            message = data.get("message", "").strip()
            approval_id = data.get("approval_id")

            if not message:
                await websocket.send_json({"type": "error", "message": "Mesaj boş olamaz"})
                continue

            logger.info(
                "WS mesaj alındı",
                extra={"session": session_id, "preview": message[:60]},
            )

            # Streaming yanıt gönder
            full_response = ""
            async for token in _agent.chat_stream(
                session_id=session_id,
                message=message,
                user_id=user.id,
                user_role=user.role,
                db=db,
                approval_id=approval_id,
            ):
                # Onay bekleme sinyali
                if token.startswith("[PENDING_APPROVAL:"):
                    import re
                    match = re.match(r"\[PENDING_APPROVAL:([^\]]+)\] (.+)", token, re.DOTALL)
                    if match:
                        appr_id = match.group(1)
                        description = match.group(2)
                        req = approval_manager.get_request(appr_id)
                        await websocket.send_json({
                            "type": "approval",
                            "approval_id": appr_id,
                            "tool_name": req.tool_name if req else "",
                            "description": description,
                        })
                    continue

                full_response += token
                await websocket.send_json({"type": "token", "content": token})

            # Tamamlandı eventi
            await websocket.send_json({
                "type": "done",
                "status": "success",
                "session_id": session_id,
                "full_response": full_response,
            })

    except WebSocketDisconnect:
        logger.info("WebSocket bağlantısı kesildi", extra={"session": session_id})
    except Exception as exc:
        logger.error(f"WebSocket hatası: {exc}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        db.close()
        logger.info("WebSocket session kapatıldı", extra={"session": session_id})
