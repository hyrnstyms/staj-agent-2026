"""
core/memory.py
--------------
Konuşma geçmişi (context) yönetimi.

Faz 1: In-memory sözlük. Her session_id için ayrı geçmiş tutulur.

⚠️  FAZ 1 KISITI — In-memory olduğu için:
    - Sunucu yeniden başlatılırsa geçmiş sıfırlanır.
    - Tek worker (--workers 1) zorunludur.
    - İleride Redis/DB'ye taşınabilir (aynı arayüz korunarak).

Kullanım:
    from core.memory import ConversationMemory

    mem = ConversationMemory()
    mem.add_message("session_1", "user", "Merhaba!")
    mem.add_message("session_1", "assistant", "Merhaba! Nasıl yardımcı olabilirim?")
    history = mem.get_history("session_1")
"""

from __future__ import annotations

import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Literal

from config import settings
from core.logger import get_logger

logger = get_logger(__name__)

# Ollama mesaj formatı
MessageRole = Literal["system", "user", "assistant", "tool"]


class Message:
    """Tek bir konuşma mesajını temsil eder."""

    __slots__ = ("role", "content", "timestamp", "tool_call_id", "tool_name")

    def __init__(
        self,
        role: MessageRole,
        content: str,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
    ) -> None:
        self.role = role
        self.content = content
        self.timestamp = datetime.now(timezone.utc)
        self.tool_call_id = tool_call_id  # tool cevabı için
        self.tool_name = tool_name

    def to_ollama_dict(self) -> dict:
        """Ollama API'sinin beklediği formata dönüştürür."""
        d: dict = {"role": self.role, "content": self.content}
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d

    def __repr__(self) -> str:
        preview = self.content[:60].replace("\n", " ")
        return f"<Message role={self.role!r} content={preview!r}>"


class ConversationMemory:
    """
    Tüm aktif oturumların konuşma geçmişini tutan merkezi sınıf.

    Thread-safe: Birden fazla thread aynı anda farklı session'lara
    yazabilir (tek worker'da gerekli değil ama sağlamlık için eklendi).

    Attributes:
        _store    : session_id → Message listesi
        _lock     : Yazma kilidi
        limit     : Her oturum için maksimum mesaj sayısı
    """

    def __init__(self, limit: int | None = None) -> None:
        self._store: dict[str, list[Message]] = defaultdict(list)
        self._lock = threading.Lock()
        self.limit = limit or settings.CONVERSATION_HISTORY_LIMIT

    # ── Public API ────────────────────────────────────────────────────────────

    def add_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
    ) -> None:
        """
        Oturuma yeni bir mesaj ekler.

        Limit aşılırsa en eski user/assistant mesajlar (sistem mesajı korunur)
        budanır.

        Args:
            session_id  : Oturum kimliği
            role        : "user" | "assistant" | "tool" | "system"
            content     : Mesaj içeriği
            tool_call_id: (tool mesajları için) çağrı ID'si
            tool_name   : (tool mesajları için) tool adı
        """
        msg = Message(
            role=role,
            content=content,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
        )
        with self._lock:
            self._store[session_id].append(msg)
            self._trim(session_id)

        logger.debug(
            "Mesaj eklendi",
            extra={"session_id": session_id, "role": role, "length": len(content)},
        )

    def get_history(
        self,
        session_id: str,
        as_dicts: bool = True,
    ) -> list[dict] | list[Message]:
        """
        Oturumun konuşma geçmişini döner.

        Args:
            session_id: Oturum kimliği
            as_dicts  : True → Ollama API formatında dict listesi döner.
                        False → Message nesnesi listesi döner.

        Returns:
            Mesajların listesi (en yeniden en eskiye değil, sıralı).
        """
        with self._lock:
            messages = list(self._store[session_id])

        if as_dicts:
            return [m.to_ollama_dict() for m in messages]
        return messages

    def clear(self, session_id: str) -> None:
        """Oturumun geçmişini temizler."""
        with self._lock:
            self._store.pop(session_id, None)
        logger.info("Oturum temizlendi", extra={"session_id": session_id})

    def clear_all(self) -> None:
        """Tüm oturumların geçmişini temizler (dikkatli kullan)."""
        with self._lock:
            count = len(self._store)
            self._store.clear()
        logger.warning(f"Tüm oturumlar temizlendi ({count} oturum)")

    def session_count(self) -> int:
        """Aktif oturum sayısını döner."""
        with self._lock:
            return len(self._store)

    def message_count(self, session_id: str) -> int:
        """Belirli bir oturumdaki mesaj sayısını döner."""
        with self._lock:
            return len(self._store[session_id])

    # ── Private ───────────────────────────────────────────────────────────────

    def _trim(self, session_id: str) -> None:
        """
        Oturumu `limit` sayısına budlar.

        Strateji: İlk mesaj sistem mesajıysa onu koru,
        geri kalanlardan en eski olanları çıkar.
        """
        messages = self._store[session_id]
        if len(messages) <= self.limit:
            return

        excess = len(messages) - self.limit
        if messages and messages[0].role == "system":
            # Sistem mesajını koru, devamından çıkar
            del messages[1 : 1 + excess]
        else:
            del messages[:excess]

        logger.debug(
            "Oturum budandı",
            extra={"session_id": session_id, "removed": excess, "remaining": len(messages)},
        )


# Modül genelinde kullanılan tekil bellek örneği
# ⚠️ Bu singleton --workers 1 kısıtına dayalıdır
conversation_memory = ConversationMemory()
