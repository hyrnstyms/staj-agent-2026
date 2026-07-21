"""
core/logger.py
--------------
Merkezi loglama modülü.

İki hedef:
    1. Yapılandırılmış JSON log dosyası + renkli console çıkışı
    2. Her tool çağrısı `tool_call_logs` DB tablosuna yazılır

Kullanım:
    from core.logger import get_logger, log_tool_call

    logger = get_logger(__name__)
    logger.info("Mesaj", extra={"session_id": "abc"})

    log_tool_call(
        db=db,
        tool_name="file_read",
        category="dosya",
        parameters={"path": "README.md"},
        result={"content": "..."},
        status="success",
        user_id=1,
        session_id="abc",
        duration_ms=45,
    )
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from config import settings

# ─────────────────────────────────────────────────────────────────────────────
# JSON Formatter
# ─────────────────────────────────────────────────────────────────────────────


class JsonFormatter(logging.Formatter):
    """
    Log kayıtlarını tek satır JSON olarak biçimlendirir.

    Örnek çıktı:
        {"ts": "2026-07-20T12:00:00Z", "level": "INFO", "logger": "core.agent",
         "msg": "Tool seçildi", "session_id": "abc123", "tool": "file_read"}
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Extra alanlar (session_id, tool_name, vb.)
        for key, value in record.__dict__.items():
            if key not in (
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "id", "levelname", "levelno",
                "lineno", "message", "module", "msecs", "msg", "name",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName", "taskName",
            ):
                payload[key] = value

        # Exception bilgisi
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# Logger kurulum
# ─────────────────────────────────────────────────────────────────────────────

_configured = False


def _configure_root_logger() -> None:
    """Root logger'ı bir kez yapılandırır (tekrar çağrılsa da idempotent)."""
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.LOG_LEVEL))

    # Console handler (renkli değil, düz metin — ileride rich eklenebilir)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root.addHandler(console_handler)

    # Dosya handler (JSON)
    try:
        file_handler = logging.FileHandler(settings.LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(JsonFormatter())
        root.addHandler(file_handler)
    except OSError as e:
        root.warning(f"Log dosyası açılamadı: {e}")

    # Gürültülü kütüphaneleri sustur
    for noisy in ("httpx", "httpcore", "urllib3", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    İsimlendirilmiş bir logger döner.

    Args:
        name: Genellikle `__name__` ile çağrılır.

    Returns:
        Yapılandırılmış Logger örneği.
    """
    _configure_root_logger()
    return logging.getLogger(name)


# ─────────────────────────────────────────────────────────────────────────────
# DB Tool Call Logging
# ─────────────────────────────────────────────────────────────────────────────


def log_tool_call(
    *,
    tool_name: str,
    parameters: dict[str, Any],
    status: str,
    db: Any = None,  # sqlalchemy Session — Any ile import döngüsü önlenir
    category: str | None = None,
    result: Any = None,
    user_id: int | None = None,
    session_id: str | None = None,
    approved_by: str | None = None,
    error_message: str | None = None,
    duration_ms: int | None = None,
) -> int | None:
    """
    Tool çağrısını hem Python logger'a hem de `tool_call_logs` tablosuna yazar.

    Args:
        tool_name    : Tool adı (örn: "file_read")
        parameters   : Tool parametreleri (dict)
        status       : "pending" | "approved" | "rejected" | "success" | "error"
        db           : SQLAlchemy Session (None ise DB'ye yazılmaz)
        category     : Router kategorisi (örn: "dosya")
        result       : Tool dönüş değeri (serileştirilebilir)
        user_id      : Çağıran kullanıcı ID'si
        session_id   : Konuşma oturum ID'si
        approved_by  : Onaylayan kullanıcı adı (varsa)
        error_message: Hata mesajı (status="error" ise)
        duration_ms  : Tool çalışma süresi (ms)

    Returns:
        Oluşturulan log kaydının ID'si, DB yoksa None.
    """
    logger = get_logger("core.logger")

    log_extra: dict[str, Any] = {
        "tool_name": tool_name,
        "category": category,
        "status": status,
        "user_id": user_id,
        "session_id": session_id,
        "duration_ms": duration_ms,
    }

    if status == "error":
        logger.error(
            f"Tool çağrısı başarısız: {tool_name} — {error_message}",
            extra=log_extra,
        )
    elif status in ("rejected",):
        logger.warning(f"Tool reddedildi: {tool_name}", extra=log_extra)
    else:
        logger.info(f"Tool çağrısı: {tool_name} [{status}]", extra=log_extra)

    if db is None:
        return None

    # DB'ye yaz
    try:
        from db.models import ToolCallLog  # burada import — döngü önlenir

        log_entry = ToolCallLog(
            user_id=user_id,
            session_id=session_id,
            tool_name=tool_name,
            category=category,
            parameters_json=json.dumps(parameters, ensure_ascii=False, default=str),
            result_json=(
                json.dumps(result, ensure_ascii=False, default=str)
                if result is not None
                else None
            ),
            status=status,
            approved_by=approved_by,
            error_message=error_message,
            duration_ms=duration_ms,
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        return log_entry.id
    except Exception as exc:
        logger.error(f"DB log yazma hatası: {exc}", exc_info=True)
        return None


class Timer:
    """
    Basit context manager tabanlı zamanlayıcı.

    Kullanım:
        with Timer() as t:
            result = call_tool(...)
        duration_ms = t.elapsed_ms
    """

    def __init__(self) -> None:
        self._start: float = 0.0
        self.elapsed_ms: int = 0

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        self.elapsed_ms = int((time.perf_counter() - self._start) * 1000)
