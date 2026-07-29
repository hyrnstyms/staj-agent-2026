"""
integrations/google_oauth.py
-----------------------------
Google OAuth 2.0 per-user token yönetimi.

Bu modül n8n'den bağımsız olarak kullanıcı başına Google access/refresh token
saklar ve gerektiğinde yeniler. mail_calendar_server bu modülden token alır,
n8n'e Authorization header olarak gönderir.

Güvenlik:
    - CSRF koruması: state = secrets.token_urlsafe(32), TTL=10dk
    - access_type=offline + prompt=consent: her zaman refresh_token alınır
    - invalid_grant: hata yakalanır, is_valid=False işaretlenir, anlamlı mesaj döner
    - Token şifreleme: geliştirmede düz metin; production için Fernet önerilir

Kullanım:
    from integrations.google_oauth import generate_auth_url, exchange_code, get_valid_access_token

    url, state = generate_auth_url(user_id=1)
    await exchange_code(code="...", state=state, db=db)
    token = await get_valid_access_token(user_id=1, db=db)
"""

from __future__ import annotations

import secrets
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from config import settings
from core.logger import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Sabitler
# ─────────────────────────────────────────────────────────────────────────────

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_AUTH_BASE = "https://accounts.google.com/o/oauth2/v2/auth"

_STATE_TTL_MINUTES = 10

# CSRF State Cache: state_token → (user_id, expires_at)
_state_cache: dict[str, tuple[int, datetime]] = {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# Auth URL Üretimi (CSRF-safe)
# ─────────────────────────────────────────────────────────────────────────────

def generate_auth_url(user_id: int) -> tuple[str, str]:
    """
    CSRF-safe Google OAuth consent URL üretir.

    state parametresi doğrudan user_id değil, rastgele bir token'dır.
    Bu token kısa ömürlü cache'te user_id ile eşleştirilir.

    Returns:
        (auth_url, state_token)
    """
    _cleanup_state_cache()

    state = secrets.token_urlsafe(32)
    _state_cache[state] = (user_id, _utcnow() + timedelta(minutes=_STATE_TTL_MINUTES))

    scopes = settings.GOOGLE_SCOPES.split()
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(scopes),
        # ── KRİTİK: Her ikisi zorunlu ──────────────────────────────────────
        # access_type=offline  → refresh_token alınır (token expire'da refresh edebilmek için)
        # prompt=consent       → kullanıcı daha önce izin verse bile yeni refresh_token gelir
        #                        Olmadan: ikinci bağlantıda refresh_token=None, sistem kırılır
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }

    auth_url = f"{GOOGLE_AUTH_BASE}?{urllib.parse.urlencode(params)}"
    logger.info("Google OAuth URL üretildi", extra={"user_id": user_id, "state_prefix": state[:8]})
    return auth_url, state


def validate_state(state: str) -> int:
    """
    Callback'ten gelen state'i doğrular ve user_id döner.

    Raises:
        ValueError: state geçersiz, bulunamadı veya süresi dolmuş
    """
    _cleanup_state_cache()
    entry = _state_cache.pop(state, None)
    if entry is None:
        raise ValueError("Geçersiz veya bulunamayan state token. Lütfen yeniden deneyin.")
    user_id, expires_at = entry
    if _utcnow() > expires_at:
        raise ValueError("State token süresi dolmuş (10 dakika). Lütfen yeniden deneyin.")
    return user_id


def _cleanup_state_cache() -> None:
    now = _utcnow()
    expired = [s for s, (_, exp) in _state_cache.items() if now > exp]
    for s in expired:
        _state_cache.pop(s, None)


# ─────────────────────────────────────────────────────────────────────────────
# Authorization Code → Token Exchange
# ─────────────────────────────────────────────────────────────────────────────

async def exchange_code(code: str, state: str, db: Any) -> dict[str, Any]:
    """
    Google'dan gelen authorization code'u token'a çevirir, DB'ye kaydeder.

    Returns:
        {"success": bool, "google_email": str, "message": str}
    """
    from db.models import GoogleOAuthToken

    # 1) state → user_id (CSRF kontrolü)
    try:
        user_id = validate_state(state)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    # 2) code → tokens
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            resp.raise_for_status()
            token_data = resp.json()
    except Exception as e:
        logger.error(f"Google token exchange hatası: {e}")
        return {"success": False, "error": f"Google token alınamadı: {e}"}

    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 3600)
    scope = token_data.get("scope", "")

    if not refresh_token:
        logger.warning(
            "Google'dan refresh_token gelmedi — "
            "access_type=offline ve prompt=consent parametrelerini kontrol edin!"
        )

    # 3) Kullanıcının Gmail adresini al
    google_email = ""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            info_resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            google_email = info_resp.json().get("email", "")
    except Exception:
        pass

    expires_at = _utcnow() + timedelta(seconds=max(expires_in - 60, 0))

    # 4) Upsert: varsa güncelle, yoksa yeni kayıt
    existing = db.query(GoogleOAuthToken).filter_by(user_id=user_id).first()
    if existing:
        existing.access_token = access_token
        # Eğer yeni refresh_token geldiyse güncelle, gelmemişse eskileri koru
        if refresh_token:
            existing.refresh_token = refresh_token
        existing.expires_at = expires_at
        existing.scopes = scope
        existing.google_email = google_email
        existing.is_valid = True
    else:
        db.add(GoogleOAuthToken(
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            scopes=scope,
            google_email=google_email,
            is_valid=True,
        ))

    db.commit()
    logger.info("Google OAuth token kaydedildi", extra={"user_id": user_id, "email": google_email})
    return {
        "success": True,
        "google_email": google_email,
        "message": f"Google hesabı başarıyla bağlandı: {google_email}",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Token Alma + Otomatik Refresh
# ─────────────────────────────────────────────────────────────────────────────

async def get_valid_access_token(user_id: int, db: Any) -> str:
    """
    Geçerli bir access_token döner. Gerekirse otomatik refresh yapar.

    Raises:
        ValueError: Hesap bağlı değil, is_valid=False, veya refresh başarısız
    """
    from db.models import GoogleOAuthToken

    token_row = (
        db.query(GoogleOAuthToken)
        .filter_by(user_id=user_id, is_valid=True)
        .first()
    )

    if token_row is None:
        # is_valid=False kaydı var mı kontrol et
        invalid = db.query(GoogleOAuthToken).filter_by(user_id=user_id).first()
        if invalid and not invalid.is_valid:
            raise ValueError(
                "Google hesabı bağlantısı kopmuş — kullanıcı erişimi iptal etmiş olabilir. "
                "Lütfen Ayarlar → Google Entegrasyonu bölümünden yeniden bağlayın."
            )
        raise ValueError(
            "Google hesabı bağlı değil. "
            "Lütfen Ayarlar → Google Entegrasyonu bölümünden hesabınızı bağlayın."
        )

    # Token hâlâ geçerliyse direkt dön
    exp_time = token_row.expires_at
    if exp_time.tzinfo is None:
        exp_time = exp_time.replace(tzinfo=timezone.utc)
    
    if _utcnow() < exp_time:
        return token_row.access_token

    # Expire olmuş → refresh
    logger.info("Google access_token yenileniyor", extra={"user_id": user_id})
    await _refresh_token(token_row, db)
    return token_row.access_token


async def _refresh_token(token_row: Any, db: Any) -> None:
    """Refresh token ile yeni access_token alır, DB'yi günceller."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "refresh_token": token_row.refresh_token,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "grant_type": "refresh_token",
                },
            )
            resp.raise_for_status()
            data = resp.json()

    except httpx.HTTPStatusError as e:
        body = e.response.text
        logger.error(f"Google refresh HTTP hatası: {body}")
        if "invalid_grant" in body:
            # Kullanıcı erişimi iptal etmiş veya token çürümüş
            token_row.is_valid = False
            db.commit()
            raise ValueError(
                "Google erişim izni geçersiz (invalid_grant). "
                "Kullanıcı Google hesabından erişimi iptal etmiş olabilir. "
                "Lütfen Ayarlar → Google Entegrasyonu bölümünden yeniden bağlayın."
            )
        raise ValueError(f"Token yenileme başarısız: {body}")

    except Exception as e:
        raise ValueError(f"Token yenileme bağlantı hatası: {e}")

    token_row.access_token = data.get("access_token", "")
    token_row.expires_at = _utcnow() + timedelta(seconds=max(data.get("expires_in", 3600) - 60, 0))
    db.commit()
    logger.info("Google access_token başarıyla yenilendi", extra={"user_id": token_row.user_id})


# ─────────────────────────────────────────────────────────────────────────────
# Status / Disconnect
# ─────────────────────────────────────────────────────────────────────────────

def get_token_status(user_id: int, db: Any) -> dict[str, Any]:
    """Kullanıcının Google hesap bağlantı durumunu döner."""
    from db.models import GoogleOAuthToken
    row = db.query(GoogleOAuthToken).filter_by(user_id=user_id).first()
    if row is None:
        return {"connected": False, "google_email": None, "is_valid": False}
    return {
        "connected": row.is_valid,
        "google_email": row.google_email,
        "is_valid": row.is_valid,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "scopes": row.scopes,
    }


def disconnect_google(user_id: int, db: Any) -> dict[str, Any]:
    """Kullanıcının Google hesap bağlantısını keser."""
    from db.models import GoogleOAuthToken
    row = db.query(GoogleOAuthToken).filter_by(user_id=user_id).first()
    if row is None:
        return {"success": False, "error": "Bağlı Google hesabı bulunamadı."}
    db.delete(row)
    db.commit()
    logger.info("Google hesabı bağlantısı kesildi", extra={"user_id": user_id})
    return {"success": True, "message": "Google hesabı bağlantısı kesildi."}
