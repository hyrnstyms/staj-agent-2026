<<<<<<< HEAD
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from config import settings
from db.database import get_db
from db.models import User

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
=======
"""
api/auth.py
-----------
MCP endpoint'leri için ayrı auth bağımlılığı.

api/main.py'deki verify_api_key fonksiyonu User nesnesi döner,
ancak MCP endpoint'leri sadece API key doğrulaması gerektirir.
Bu modül MCP router'ın import edebileceği hafif bir doğrulama sağlar.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from config import settings


async def verify_api_key(
    x_api_key: str | None = Header(default=None),
) -> str:
    """
    X-API-Key header'ını doğrular ve key'i string olarak döner.

    MCP endpoint'leri User nesnesi gerektirmez — sadece geçerli key yeterli.

    Returns:
        Doğrulanmış API key string'i.

    Raises:
        HTTPException 401: Key eksik veya geçersiz.
>>>>>>> 503cec5 (mcp entegrasyonu)
    """
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key header'ı eksik. Lütfen API key'inizi ekleyin.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

<<<<<<< HEAD
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
=======
    if x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return x_api_key
>>>>>>> 503cec5 (mcp entegrasyonu)
