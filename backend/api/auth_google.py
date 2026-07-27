"""
api/auth_google.py
-------------------
Google OAuth 2.0 bağlantı endpoint'leri.

Endpoint'ler:
    GET  /auth/google/connect    → Google consent sayfasına redirect
    GET  /auth/google/callback   → code+state alır, token exchange, DB kayıt
    GET  /auth/google/status     → bağlantı durumu sorgular
    DELETE /auth/google/disconnect → Google bağlantısını keser

Güvenlik notu:
    - state parametresi CSRF-safe (secrets.token_urlsafe(32), TTL=10dk)
    - access_type=offline + prompt=consent ile her zaman refresh_token alınır
    - invalid_grant: is_valid=False işaretlenir, anlamlı hata mesajı döner
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from api.auth import verify_api_key
from db.database import SessionLocal
from integrations.google_oauth import (
    exchange_code,
    generate_auth_url,
    get_token_status,
    disconnect_google,
)

router = APIRouter(prefix="/auth/google", tags=["Google OAuth"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Bağlantı Başlatma
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/connect")
async def google_connect(
    user_id: int = Query(..., description="Bağlanacak kullanıcının DB ID'si"),
    api_key: str = Depends(verify_api_key),
):
    """
    Google OAuth consent sayfasına yönlendirir.

    CSRF koruması: state parametresi rastgele token (user_id değil).
    access_type=offline + prompt=consent ile her seferinde refresh_token alınır.
    """
    from config import settings
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=503,
            detail=(
                "Google OAuth yapılandırılmamış. "
                ".env dosyasına GOOGLE_CLIENT_ID ve GOOGLE_CLIENT_SECRET ekleyin."
            ),
        )

    auth_url, _state = generate_auth_url(user_id=user_id)
    return RedirectResponse(url=auth_url)


# ─────────────────────────────────────────────────────────────────────────────
# OAuth Callback
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/callback")
async def google_callback(
    code: str = Query(..., description="Google authorization code"),
    state: str = Query(..., description="CSRF doğrulama state token'ı"),
    error: str | None = Query(default=None, description="Google hata kodu (kullanıcı reddettiyse)"),
    db: Session = Depends(get_db),
):
    """
    Google'dan gelen callback'i işler.

    - state doğrular (CSRF)
    - code → access_token + refresh_token exchange
    - DB'ye kaydeder
    - Başarılıysa frontend'e redirect, değilse hata JSON
    """
    if error:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": f"Google OAuth reddedildi: {error}",
                "message": "Kullanıcı izin vermedi veya bir hata oluştu.",
            },
        )

    result = await exchange_code(code=code, state=state, db=db)

    if not result.get("success"):
        return JSONResponse(
            status_code=400,
            content=result,
        )

    # Başarılı — frontend'i bilgilendir
    # Production'da: frontend URL'ine redirect + query param
    # Şimdilik: JSON yanıt (Tauri/desktop app fetch ile alır)
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "message": result.get("message", "Google hesabı bağlandı."),
            "google_email": result.get("google_email"),
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Durum Sorgulama
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/status")
async def google_status(
    user_id: int = Query(..., description="Sorgulanan kullanıcının DB ID'si"),
    api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """
    Kullanıcının Google hesap bağlantı durumunu döner.

    Returns:
        {
            "connected": bool,
            "google_email": str | null,
            "is_valid": bool,
            "expires_at": str | null,
            "scopes": str
        }
    """
    return get_token_status(user_id=user_id, db=db)


# ─────────────────────────────────────────────────────────────────────────────
# Bağlantı Kesme
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/disconnect")
async def google_disconnect(
    user_id: int = Query(..., description="Bağlantısı kesilecek kullanıcının DB ID'si"),
    api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """
    Kullanıcının Google hesap bağlantısını keser (DB'den siler).

    ⚠️ Bu işlem access_token ve refresh_token'ı siler.
    Kullanıcının yeniden /connect akışını çalıştırması gerekir.
    """
    result = disconnect_google(user_id=user_id, db=db)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))
    return result
