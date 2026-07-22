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
