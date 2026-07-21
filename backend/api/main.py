"""
api/main.py
-----------
FastAPI uygulama ana girişi.

Endpoint'ler:
    GET  /health                  — Sistem sağlık kontrolü
    POST /chat                    — Mesaj gönder, cevap al
    POST /approve/{approval_id}   — Bekleyen işlemi onayla
    POST /reject/{approval_id}    — Bekleyen işlemi reddet
    GET  /approvals/pending       — Bekleyen onay isteklerini listele
    GET  /sessions/{session_id}/history — Konuşma geçmişi

Auth:
    ⚠️ FAZ 1 GEÇİCİ AUTH — X-API-Key header'ı doğrulanır.
    user_id request body'sinden değil, bu header'dan türetilir.
    Production'da JWT tabanlı auth ile değiştirilmelidir.

Worker Kısıtı:
    ⚠️ Tek worker (--workers 1) ile çalıştırılmalıdır.
    In-memory onay ve hafıza state'i farklı worker'lar arasında paylaşılamaz.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.websocket import router as ws_router
from config import settings
from core.agent import Agent
from core.approval import approval_manager
from core.logger import get_logger
from core.memory import conversation_memory
from db.database import get_db, init_db
from db.models import User
from db.seed import seed_database

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Uygulama başlangıç/bitiş
# ─────────────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama başlangıç ve bitiş işlemleri."""
    logger.info("Asistan backend başlatılıyor...")

    # Veritabanı tabloları oluştur
    init_db()
    logger.info("Veritabanı hazır")

    # Demo verilerini yükle (yoksa)
    try:
        seed_database()
    except Exception as exc:
        logger.warning(f"Seed atlandı: {exc}")

    logger.info(
        f"Backend hazır — model: {settings.OLLAMA_MODEL} @ {settings.OLLAMA_BASE_URL}"
    )
    logger.warning(
        "⚠️  FAZ 1 GEÇİCİ AUTH AKTIF — Production'da JWT ile değiştirin."
    )
    logger.warning(
        f"⚠️  TEK WORKER MODU — Workers: {settings.WORKERS}. "
        "In-memory state birden fazla worker'da çalışmaz."
    )

    yield

    # Kapatma
    logger.info("Backend kapatılıyor...")
    approval_manager.cleanup_expired()
    logger.info("Backend kapatıldı.")


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI uygulaması
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Asistan API",
    description=(
        "Yerel çalışan AI asistanı — Ollama + Qwen2.5 + Tool Calling\n\n"
        "⚠️ **Faz 1 Auth**: Tüm isteklere `X-API-Key` header'ı eklenmelidir.\n"
        "⚠️ **Tek Worker**: `--workers 1` ile çalıştırılmalıdır."
    ),
    version="0.1.0-faz1",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # İleri fazda daraltılacak
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket router
app.include_router(ws_router)

# Tekil agent örneği
_agent = Agent()


# ─────────────────────────────────────────────────────────────────────────────
# Auth Bağımlılığı
# ─────────────────────────────────────────────────────────────────────────────


async def verify_api_key(
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """
    ⚠️ FAZ 1 GEÇİCİ AUTH

    X-API-Key header'ını doğrular.
    - Eğer header yoksa → 401
    - Eğer geliştirme API key'i ise → admin user döner
    - Production'da JWT ile değiştirilmeli

    Returns:
        Doğrulanmış User nesnesi
    """
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key header'ı eksik. Lütfen API key'inizi ekleyin.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Geliştirme API key'i kontrolü
    if x_api_key == settings.API_KEY:
        # Demo: admin user'ı bul veya oluştur
        user = db.query(User).filter(User.email == "admin@sirket.com").first()
        if user:
            return user
        # Seed çalışmamışsa fallback
        return User(id=1, name="Admin", email="admin@sirket.com", role="admin")

    # İleride: DB'den API key hash'i karşılaştır
    # user = db.query(User).filter(User.api_key_hash == hash(x_api_key)).first()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz API key.",
        headers={"WWW-Authenticate": "ApiKey"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Modelleri
# ─────────────────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    """POST /chat istek gövdesi."""

    message: str
    session_id: str | None = None  # None ise otomatik UUID oluşturulur
    approval_id: str | None = None  # Onay dönüşü için


class ChatResponse(BaseModel):
    """POST /chat yanıt gövdesi."""

    message: str
    status: str
    session_id: str
    tool_name: str | None = None
    approval_id: str | None = None
    category: str | None = None
    phase1_success: bool = True
    phase2_success: bool = True
    tool_result: Any = None


class ApprovalResponse(BaseModel):
    """POST /approve veya /reject yanıt gövdesi."""

    approval_id: str
    decision: str
    tool_name: str
    message: str


class HealthResponse(BaseModel):
    """GET /health yanıt gövdesi."""

    status: str
    model: str
    ollama_url: str
    sandbox_root: str
    active_sessions: int
    pending_approvals: int
    worker_warning: str


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint'ler
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """
    Sistem sağlık durumunu döner.
    Auth gerektirmez — monitoring için açık bırakılmıştır.
    """
    pending = len(approval_manager.list_pending())
    return HealthResponse(
        status="ok",
        model=settings.OLLAMA_MODEL,
        ollama_url=settings.OLLAMA_BASE_URL,
        sandbox_root=str(settings.SANDBOX_ROOT),
        active_sessions=conversation_memory.session_count(),
        pending_approvals=pending,
        worker_warning=(
            "⚠️ In-memory state: --workers 1 ile çalıştırılmalıdır. "
            "Redis/DB entegrasyonuna kadar bu kısıt geçerlidir."
        ),
    )


@app.post("/chat", response_model=ChatResponse, tags=["Agent"])
async def chat(
    request: ChatRequest,
    current_user: User = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """
    Kullanıcı mesajını işler ve agent yanıtı döner.

    Riskli bir işlem (silme, gönderme, push) seçilirse:
    - `status: "pending_approval"` ve `approval_id` döner
    - Kullanıcı `POST /approve/{approval_id}` ile onaylayabilir

    Headers:
        X-API-Key: API anahtarı (⚠️ Faz 1 geçici auth)
    """
    session_id = request.session_id or str(uuid.uuid4())

    logger.info(
        f"POST /chat",
        extra={
            "session": session_id,
            "user": current_user.email,
            "role": current_user.role,
            "message_preview": request.message[:80],
        },
    )

    try:
        response = await _agent.chat(
            session_id=session_id,
            message=request.message,
            user_id=current_user.id,
            user_role=current_user.role,
            db=db,
            approval_id=request.approval_id,
        )
    except Exception as exc:
        logger.error(f"Agent hatası: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent hatası: {exc}",
        )

    return ChatResponse(
        message=response.message,
        status=response.status,
        session_id=session_id,
        tool_name=response.tool_name,
        approval_id=response.approval_id,
        category=response.category,
        phase1_success=response.phase1_success,
        phase2_success=response.phase2_success,
        tool_result=response.tool_result,
    )


@app.post("/approve/{approval_id}", response_model=ApprovalResponse, tags=["Approval"])
async def approve_action(
    approval_id: str,
    current_user: User = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """
    Bekleyen bir onay isteğini onaylar ve tool'u çalıştırır.

    Headers:
        X-API-Key: API anahtarı
    """
    try:
        req = approval_manager.resolve(
            approval_id=approval_id,
            approved=True,
            resolved_by=current_user.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Onay isteği bulunamadı: {approval_id}",
        )

    logger.info(
        f"Onay verildi",
        extra={"approval_id": approval_id, "tool": req.tool_name, "by": current_user.email},
    )

    return ApprovalResponse(
        approval_id=approval_id,
        decision="approved",
        tool_name=req.tool_name,
        message=(
            f"'{req.tool_name}' işlemi onaylandı. "
            f"Tool'u çalıştırmak için aynı mesajı `approval_id` ile tekrar gönderin."
        ),
    )


@app.post("/reject/{approval_id}", response_model=ApprovalResponse, tags=["Approval"])
async def reject_action(
    approval_id: str,
    current_user: User = Depends(verify_api_key),
):
    """
    Bekleyen bir onay isteğini reddeder.

    Headers:
        X-API-Key: API anahtarı
    """
    try:
        req = approval_manager.resolve(
            approval_id=approval_id,
            approved=False,
            resolved_by=current_user.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if req is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Onay isteği bulunamadı: {approval_id}",
        )

    logger.info(
        f"Onay reddedildi",
        extra={"approval_id": approval_id, "tool": req.tool_name, "by": current_user.email},
    )

    return ApprovalResponse(
        approval_id=approval_id,
        decision="rejected",
        tool_name=req.tool_name,
        message=f"'{req.tool_name}' işlemi iptal edildi.",
    )


@app.get("/approvals/pending", tags=["Approval"])
async def list_pending_approvals(
    current_user: User = Depends(verify_api_key),
):
    """Bekleyen onay isteklerini listeler."""
    pending = approval_manager.list_pending()
    return {
        "total": len(pending),
        "items": [req.to_dict() for req in pending],
    }


@app.get("/sessions/{session_id}/history", tags=["Session"])
async def get_session_history(
    session_id: str,
    current_user: User = Depends(verify_api_key),
):
    """Bir oturumun konuşma geçmişini döner."""
    history = conversation_memory.get_history(session_id, as_dicts=True)
    return {
        "session_id": session_id,
        "message_count": len(history),
        "messages": history,
    }


@app.delete("/sessions/{session_id}", tags=["Session"])
async def clear_session(
    session_id: str,
    current_user: User = Depends(verify_api_key),
):
    """Bir oturumun konuşma geçmişini temizler."""
    conversation_memory.clear(session_id)
    return {"session_id": session_id, "cleared": True}
