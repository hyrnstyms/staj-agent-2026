"""
api/auth.py
-----------
MCP ve diger endpoint'ler icin API key dogrulama bagimliligı.

MCP endpoint'leri User nesnesi gerektirmez — sadece gecerli key yeterli.
Ana /chat endpoint'i ise main.py icindeki verify_api_key (User donduruyor) kullanır.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from config import settings


async def verify_api_key(
    x_api_key: str | None = Header(default=None),
) -> str:
    """
    X-API-Key header'ını dogrular ve key'i string olarak doner.

    MCP endpoint'leri User nesnesi gerektirmez — sadece gecerli key yeterli.

    Returns:
        Dogrulanmis API key string'i.

    Raises:
        HTTPException 401: Key eksik veya gecersiz.
    """
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key header'ı eksik. Lutfen API key'inizi ekleyin.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gecersiz API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return x_api_key
