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

import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.websocket import router as ws_router
from config import settings
from core.agent import Agent
from core.approval import approval_manager
from core.logger import Timer, get_logger, log_tool_call
from core.memory import conversation_memory
from db.database import get_db, init_db
from db.models import User
from db.seed import seed_database
from multimodal.stt import stt_transcribe
from multimodal.vision import vision_describe

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

    # MCP adapter'larını kaydet
    try:
        from mcp_servers.mcp_adapters import register_all_servers
        register_all_servers()
    except Exception as exc:
        logger.warning(f"MCP adapter kaydı kısmen başarısız: {exc}")

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

# MCP router
from api.mcp_endpoint import router as mcp_router
app.include_router(mcp_router)

# Tekil agent örneği
_agent = Agent()


# ─────────────────────────────────────────────────────────────────────────────
# Auth Bağımlılığı
# ─────────────────────────────────────────────────────────────────────────────


from api.auth import verify_api_key

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


class UploadResponse(BaseModel):
    """POST /upload yanıt gövdesi."""

    success: bool
    upload_type: str          # "audio" | "image"
    result: str               # transkript veya görsel açıklaması
    mime_type: str
    size_bytes: int
    message: str | None = None


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


# ─────────────────────────────────────────────────────────────────────────────
# Multimodal Upload Endpoint
# ─────────────────────────────────────────────────────────────────────────────

# İzin verilen MIME tipleri (gerçek içerik tipine göre — uzantıya güvenilmez)
_AUDIO_MIMES = {"audio/webm", "audio/ogg", "audio/wav", "audio/mpeg", "audio/mp4"}
_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_ALLOWED_MIMES = _AUDIO_MIMES | _IMAGE_MIMES

# MIME → uzantı eşlemesi (UUID dosya adı için)
_MIME_EXT: dict[str, str] = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

# Boyut sınırları (byte)
_MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB
_MAX_IMAGE_BYTES = 5 * 1024 * 1024   # 5 MB

# Yükleme klasörü TTL (saniye)
_UPLOAD_TTL_SECONDS = 3600  # 1 saat


def _get_upload_dir() -> Path:
    """SANDBOX_ROOT/uploads/ dizinini döner, yoksa oluşturur."""
    upload_dir = settings.SANDBOX_ROOT / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _cleanup_old_uploads() -> int:
    """
    1 saati aşan geçici yükleme dosyalarını siler.
    Başlangıçta ve her yüklemede çağrılır.

    Returns:
        Silinen dosya sayısı.
    """
    upload_dir = _get_upload_dir()
    cutoff = time.time() - _UPLOAD_TTL_SECONDS
    deleted = 0
    for f in upload_dir.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            try:
                f.unlink()
                deleted += 1
            except OSError:
                pass
    if deleted:
        logger.info(f"Upload TTL temizliği: {deleted} dosya silindi")
    return deleted


def _detect_mime(data: bytes) -> str:
    """
    Dosya içeriğinden gerçek MIME tipini tespit eder.
    python-magic varsa magic byte analizi yapar; yoksa Content-Type header'ına
    fallback yapar (güvenlik notu belirtilir).
    """
    try:
        import magic  # type: ignore
        return magic.from_buffer(data[:2048], mime=True)
    except ImportError:
        logger.warning(
            "python-magic yüklü değil — MIME tespiti Content-Type header'ına "
            "fallback yapıyor. Güvenlik için 'pip install python-magic' çalıştırın."
        )
        return ""  # Caller fallback'i yönetir


@app.post("/upload", response_model=UploadResponse, tags=["Multimodal"])
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """
    Ses veya görsel dosyası yükler; STT/vision işlemi uygular.

    Güvenlik:
    - MIME tipi python-magic ile gerçek içerikten tespit edilir (uzantıya güvenilmez)
    - Dosya adı: UUID4 tabanlı — orijinal ad ASLA kullanılmaz
    - Kayıt: SANDBOX_ROOT/uploads/ — sandbox dışına çıkış yok
    - Boyut: ses max 10MB, görsel max 5MB
    - TTL: İşlem sonrası silinir; 1 saati aşan dosyalar temizlenir
    - Her işlem tool_call_logs'a yazılır

    Ses: WebM/Opus (MediaRecorder default), WAV, OGG, MP3 kabul edilir.
    Görsel: JPEG, PNG, WebP, GIF kabul edilir.

    Headers:
        X-API-Key: API anahtarı (Faz 1 auth)
    """
    # Eski dosyaları temizle
    _cleanup_old_uploads()

    # Dosyayı belleğe oku (boyut kontrolü için)
    raw_bytes = await file.read()
    size_bytes = len(raw_bytes)

    # MIME tespiti (magic bytes)
    detected_mime = _detect_mime(raw_bytes)

    # Fallback: python-magic yoksa Content-Type kullan
    if not detected_mime:
        detected_mime = (file.content_type or "").split(";")[0].strip().lower()

    logger.info(
        "POST /upload",
        extra={
            "user": current_user.email,
            "size_bytes": size_bytes,
            "detected_mime": detected_mime,
            "original_filename": "[gizlendi — güvenlik]",
        },
    )

    # MIME whitelist kontrolü
    if detected_mime not in _ALLOWED_MIMES:
        log_tool_call(
            tool_name="upload",
            parameters={"mime": detected_mime, "size": size_bytes},
            status="error",
            db=db,
            category="gorsel_ses",
            user_id=current_user.id,
            error_message=f"İzin verilmeyen MIME tipi: {detected_mime}",
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Desteklenmeyen dosya tipi: '{detected_mime}'. "
                f"İzin verilenler: {sorted(_ALLOWED_MIMES)}"
            ),
        )

    # Boyut sınırı kontrolü
    is_audio = detected_mime in _AUDIO_MIMES
    is_image = detected_mime in _IMAGE_MIMES
    max_bytes = _MAX_AUDIO_BYTES if is_audio else _MAX_IMAGE_BYTES
    upload_type = "audio" if is_audio else "image"

    if size_bytes > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        log_tool_call(
            tool_name="upload",
            parameters={"mime": detected_mime, "size": size_bytes},
            status="error",
            db=db,
            category="gorsel_ses",
            user_id=current_user.id,
            error_message=f"Dosya boyutu aşıldı: {size_bytes} > {max_bytes}",
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"{upload_type.capitalize()} dosyası max {max_mb}MB olabilir.",
        )

    # UUID tabanlı güvenli dosya adıyla SANDBOX_ROOT/uploads/ altına kaydet
    ext = _MIME_EXT.get(detected_mime, ".bin")
    safe_filename = f"{uuid.uuid4()}{ext}"
    upload_dir = _get_upload_dir()
    save_path = upload_dir / safe_filename

    # Path traversal kontrolü (teorik — UUID adı zaten güvenli, ama defense-in-depth)
    try:
        save_path.resolve().relative_to(settings.SANDBOX_ROOT.resolve())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Güvenlik ihlali: Hedef yol sandbox dışında.",
        )

    save_path.write_bytes(raw_bytes)

    # STT veya Vision işlemi
    result_text = ""
    error_msg = None

    with Timer() as t:
        try:
            if is_audio:
                stt_result = stt_transcribe(str(save_path))
                if stt_result["success"]:
                    result_text = stt_result["text"]
                else:
                    error_msg = stt_result.get("error", "STT hatası")
            else:  # image
                # vision_describe sandbox-relative path bekler
                rel_path = save_path.relative_to(settings.SANDBOX_ROOT)
                vision_result = vision_describe(str(rel_path))
                if vision_result["success"]:
                    result_text = vision_result["description"]
                else:
                    error_msg = vision_result.get("error", "Vision hatası")
        except Exception as exc:
            logger.error(f"Upload işleme hatası: {exc}", exc_info=True)
            error_msg = str(exc)
        finally:
            # İşlem bittikten sonra dosyayı sil (geçici)
            try:
                save_path.unlink(missing_ok=True)
            except OSError:
                pass

    # Loglama
    log_status = "success" if not error_msg else "error"
    log_tool_call(
        tool_name=f"upload_{upload_type}",
        parameters={"mime": detected_mime, "size_bytes": size_bytes},
        result={"text_length": len(result_text)} if result_text else None,
        status=log_status,
        db=db,
        category="gorsel_ses",
        user_id=current_user.id,
        error_message=error_msg,
        duration_ms=t.elapsed_ms,
    )

    if error_msg:
        return UploadResponse(
            success=False,
            upload_type=upload_type,
            result="",
            mime_type=detected_mime,
            size_bytes=size_bytes,
            message=error_msg,
        )

    return UploadResponse(
        success=True,
        upload_type=upload_type,
        result=result_text,
        mime_type=detected_mime,
        size_bytes=size_bytes,
    )
