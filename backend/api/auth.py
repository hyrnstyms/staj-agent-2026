"""
api/auth.py
-----------
MCP ve diger endpoint'ler icin API key dogrulama bagimliligı.

MCP endpoint'leri User nesnesi gerektirmez — sadece gecerli key yeterli.
Ana /chat endpoint'i ise main.py icindeki verify_api_key (User donduruyor) kullanır.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, Query, status

from config import settings


async def verify_api_key(
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None),
) -> str:
    """
    X-API-Key header'ını veya api_key query parametresini dogrular ve key'i doner.

    MCP endpoint'leri User nesnesi gerektirmez — sadece gecerli key yeterli.
    OAuth redirect'leri (tarayıcıdan gelen GET istekleri) header gonderemez,
    bu yuzden query parametresi (api_key) de kabul edilir.

    Returns:
        Dogrulanmis API key string'i.

    Raises:
        HTTPException 401: Key eksik veya gecersiz.
    """
    token = x_api_key or api_key

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key header'ı veya api_key parametresi eksik.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if token != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gecersiz API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return x_api_key
