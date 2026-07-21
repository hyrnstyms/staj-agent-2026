"""
config.py
---------
Merkezi yapılandırma modülü.
Tüm ayarlar .env dosyasından okunur; hiçbir değer kod içine hardcode edilmez.

Kullanım:
    from config import settings
    print(settings.OLLAMA_MODEL)
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Uygulama genelinde kullanılan yapılandırma nesnesi.
    Değerler önce ortam değişkenlerinden, sonra .env dosyasından okunur.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Ollama / LLM ──────────────────────────────────────────────────────────
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        description="Ollama sunucusunun base URL'i",
    )
    OLLAMA_MODEL: str = Field(
        default="qwen2.5:3b-instruct",
        description="Ana orkestratör model adı (ileride 7B/14B'ye geçmek için buradan değiştir)",
    )
    OLLAMA_VISION_MODEL: str = Field(
        default="qwen2-vl",
        description="Görsel açıklama için kullanılan vision model adı",
    )
    OLLAMA_TIMEOUT: int = Field(
        default=120,
        description="Ollama API çağrısı zaman aşımı (saniye)",
    )

    # ── Güvenlik / Auth ───────────────────────────────────────────────────────
    API_KEY: str = Field(
        default="dev-api-key-change-in-production",
        description=(
            "⚠️  FAZ 1 GEÇİCİ AUTH — X-API-Key header'ı olarak gönderilir. "
            "Production'da JWT tabanlı auth ile değiştirilmelidir."
        ),
    )

    # ── n8n / Entegrasyonlar ──────────────────────────────────────────────────
    N8N_WEBHOOK_URL: str = Field(
        default="http://localhost:5678/webhook/agent",
        description="n8n üzerindeki ana webhook adresi (Mail/Takvim vb. otomasyonlar için)",
    )
    N8N_API_KEY: str = Field(
        default="",
        description="n8n webhook isteğini doğrulayan anahtar (Bearer Auth için opsiyonel)",
    )

    # ── Dosya Sistemi Sandbox ─────────────────────────────────────────────────
    SANDBOX_ROOT: Path = Field(
        default=Path("sandbox"),
        description=(
            "Dosya işlemlerinin yalnızca bu dizin altında çalışmasına izin verilir. "
            "Bu dizinin dışına çıkan path'ler (path traversal) reddedilir."
        ),
    )

    @field_validator("SANDBOX_ROOT", mode="before")
    @classmethod
    def resolve_sandbox_root(cls, v: str | Path) -> Path:
        """SANDBOX_ROOT'u mutlak path'e çevirir ve dizini oluşturur."""
        path = Path(v).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    # ── Veritabanı ────────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="sqlite:///./local_agent.db",
        description="SQLAlchemy bağlantı URL'i (SQLite → PostgreSQL için değiştirilebilir)",
    )

    # ── Loglama ───────────────────────────────────────────────────────────────
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Python logging seviyesi",
    )
    LOG_FILE: Path = Field(
        default=Path("logs/agent.log"),
        description="Log dosyasının yolu",
    )

    @field_validator("LOG_FILE", mode="before")
    @classmethod
    def resolve_log_file(cls, v: str | Path) -> Path:
        """LOG_FILE dizinini otomatik oluşturur."""
        path = Path(v)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    # ── Agent Davranışı ───────────────────────────────────────────────────────
    MAX_TOOL_RETRIES: int = Field(
        default=2,
        description="Tool çağrısı başarısız olduğunda maksimum yeniden deneme sayısı",
    )
    CONVERSATION_HISTORY_LIMIT: int = Field(
        default=20,
        description="Context penceresine alınacak maksimum mesaj sayısı",
    )
    MAX_TOOLS_PER_CATEGORY: int = Field(
        default=8,
        description="Modele aynı anda gösterilebilecek maksimum tool sayısı",
    )

    # ── Sunucu ────────────────────────────────────────────────────────────────
    HOST: str = Field(default="0.0.0.0", description="FastAPI sunucu host'u")
    PORT: int = Field(default=8000, description="FastAPI sunucu portu")
    WORKERS: int = Field(
        default=1,
        description=(
            "⚠️  FAZ 1 KISITI — in-memory onay ve hafıza state'i nedeniyle "
            "bu değer 1'den büyük yapılmamalıdır. "
            "Redis/DB entegrasyonuna kadar tek worker zorunludur."
        ),
    )
    DEBUG: bool = Field(default=False, description="FastAPI debug modu")

    # ── GitHub & Kod Yönetimi (Faz 3) ────────────────────────────────────────
    GITHUB_TOKEN: str = Field(
        default="",
        description="GitHub Pull Request işlemleri için kullanılacak Personal Access Token (PAT).",
    )
    ALLOWED_REPOS: str = Field(
        default="",
        description="Virgülle ayrılmış izin verilen Git repolarının yolları (örneğin: './sandbox/repo1,./sandbox/repo2').",
    )

    @property
    def allowed_repos_list(self) -> list[Path]:
        """ALLOWED_REPOS string'ini parçalayıp resolve edilmiş Path listesi döner."""
        if not self.ALLOWED_REPOS:
            return []
        paths = []
        for p in self.ALLOWED_REPOS.split(","):
            if p.strip():
                paths.append(Path(p.strip()).resolve())
        return paths

# Modül genelinde kullanılan tekil settings örneği
settings = Settings()
