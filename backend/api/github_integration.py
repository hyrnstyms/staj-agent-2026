"""
api/github_integration.py
--------------------------
GitHub entegrasyon durumu ve token doğrulama endpoint'leri.

Endpoint'ler:
    GET  /integrations/github/status   → GitHub token durumu sorgular
    POST /integrations/github/verify   → GitHub token'ı test eder
    GET  /integrations/github/repos    → Erişilebilir repoları listeler
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import verify_api_key
from config import settings
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/integrations/github", tags=["GitHub Integration"])


class GitHubStatusResponse(BaseModel):
    connected: bool
    username: str | None = None
    scopes: str | None = None
    message: str


class GitHubRepo(BaseModel):
    full_name: str
    description: str | None = None
    private: bool
    html_url: str
    default_branch: str


# ─────────────────────────────────────────────────────────────────────────────
# Durum Sorgulama
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/status", response_model=GitHubStatusResponse)
async def github_status(api_key: str = Depends(verify_api_key)):
    """
    GitHub token'ının yapılandırılmış olup olmadığını ve geçerliliğini kontrol eder.
    """
    import httpx

    token = settings.GITHUB_TOKEN
    if not token:
        return GitHubStatusResponse(
            connected=False,
            message="GitHub token yapılandırılmamış. Backend .env dosyasına GITHUB_TOKEN ekleyin.",
        )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                scopes = resp.headers.get("x-oauth-scopes", "")
                return GitHubStatusResponse(
                    connected=True,
                    username=data.get("login"),
                    scopes=scopes,
                    message=f"Bağlı: {data.get('login')}",
                )
            elif resp.status_code == 401:
                return GitHubStatusResponse(
                    connected=False,
                    message="GitHub token geçersiz veya süresi dolmuş.",
                )
            else:
                return GitHubStatusResponse(
                    connected=False,
                    message=f"GitHub API hatası: {resp.status_code}",
                )
    except Exception as exc:
        logger.error(f"GitHub durum kontrolü hatası: {exc}")
        return GitHubStatusResponse(
            connected=False,
            message=f"GitHub bağlantı hatası: {exc}",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Erişilebilir Repolar
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/repos")
async def github_repos(api_key: str = Depends(verify_api_key)):
    """
    GitHub token'ı ile erişilebilir repoları listeler.
    """
    import httpx

    token = settings.GITHUB_TOKEN
    if not token:
        raise HTTPException(
            status_code=503,
            detail="GitHub token yapılandırılmamış.",
        )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.github.com/user/repos",
                params={"per_page": 30, "sort": "updated", "type": "all"},
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            resp.raise_for_status()
            repos = resp.json()
            return {
                "repos": [
                    {
                        "full_name": r["full_name"],
                        "description": r.get("description"),
                        "private": r["private"],
                        "html_url": r["html_url"],
                        "default_branch": r.get("default_branch", "main"),
                    }
                    for r in repos
                ]
            }
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"GitHub API hatası: {exc.response.text}",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# İzin Verilen Repolar
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/allowed-repos")
async def allowed_repos(api_key: str = Depends(verify_api_key)):
    """
    Sistemde yapılandırılmış ALLOWED_REPOS listesini döner.
    """
    repos = [str(p) for p in settings.allowed_repos_list]
    return {
        "allowed_repos": repos,
        "count": len(repos),
    }
