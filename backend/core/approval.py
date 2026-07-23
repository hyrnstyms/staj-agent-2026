"""
core/approval.py
----------------
Kullanıcı onay mekanizması.

Riskli tool'lar (silme, gönderme, push, vb.) çalıştırılmadan önce
kullanıcıdan onay alınır. Onay gelmeden tool_executor hiçbir
yazma/silme işlemi başlatmaz.

Faz 1 Uyarısı:
    ⚠️  Onay state'i in-memory dict'te tutulur.
    Sunucu yeniden başlatılırsa bekleyen onaylar kaybolur.
    uvicorn --workers 1 ile çalıştırılmalıdır.
    İleride Redis veya DB'ye taşınacak (aynı arayüz korunarak).

Akış:
    1. tool_executor → request_approval() → approval_id döner
    2. /chat endpoint → {status: "pending_approval", approval_id: "..."} döner
    3. Kullanıcı → POST /approve/{approval_id} veya POST /reject/{approval_id}
    4. agent → get_approval_status() ile bekler (polling veya callback)
    5. Onaylandıysa tool çalıştırılır, reddedildiyse işlem iptal edilir

Kullanım:
    from core.approval import approval_manager

    approval_id = approval_manager.request(
        tool_name="file_delete",
        parameters={"path": "önemli.txt"},
        user_id=1,
        session_id="abc",
        description="'önemli.txt' dosyasını kalıcı olarak silmek üzeresiniz.",
    )

    status = approval_manager.get_status(approval_id)
    # → ApprovalStatus.PENDING | APPROVED | REJECTED | EXPIRED
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from core.logger import get_logger

logger = get_logger(__name__)

# Onay isteğinin varsayılan geçerlilik süresi
DEFAULT_TIMEOUT_MINUTES = 10


class ApprovalStatus(str, Enum):
    """Onay isteğinin olası durumları."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class ApprovalRequest:
    """
    Tek bir onay isteğini temsil eder.

    Attributes:
        approval_id : Benzersiz UUID
        tool_name   : Onay beklenen tool adı
        parameters  : Tool parametreleri
        description : Kullanıcıya gösterilecek açıklama metni
        user_id     : İsteği oluşturan kullanıcı
        session_id  : İlgili konuşma oturumu
        status      : Mevcut durum
        created_at  : Oluşturulma zamanı (UTC)
        expires_at  : Geçerlilik bitiş zamanı (UTC)
        resolved_at : Karar verilme zamanı (UTC, varsa)
        resolved_by : Kararı veren kullanıcı adı (varsa)
    """

    approval_id: str
    tool_name: str
    parameters: dict[str, Any]
    description: str
    user_id: int | None
    session_id: str | None
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
        + timedelta(minutes=DEFAULT_TIMEOUT_MINUTES)
    )
    resolved_at: datetime | None = None
    resolved_by: str | None = None

    def is_expired(self) -> bool:
        """Onay isteğinin süresi doldu mu?"""
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        """API response için dict biçimine dönüştürür."""
        return {
            "approval_id": self.approval_id,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "description": self.description,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
        }


class ApprovalManager:
    """
    Kullanıcı onay isteklerini yöneten merkezi sınıf.

    ⚠️  In-memory — tek worker zorunlu.
    """

    def __init__(self) -> None:
        self._store: dict[str, ApprovalRequest] = {}
        self._lock = threading.Lock()

    def request(
        self,
        *,
        tool_name: str,
        parameters: dict[str, Any],
        user_id: int | None = None,
        session_id: str | None = None,
        description: str | None = None,
        timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES,
    ) -> str:
        """
        Yeni bir onay isteği oluşturur.

        Args:
            tool_name       : Onay beklenen tool adı
            parameters      : Tool parametreleri
            user_id         : İsteği oluşturan kullanıcı ID'si
            session_id      : Konuşma oturum ID'si
            description     : Kullanıcıya gösterilecek açıklama (oluşturulmazsa otomatik)
            timeout_minutes : Onay süresi aşımı (dakika)

        Returns:
            approval_id: Onay takip ID'si (UUID4)
        """
        approval_id = str(uuid.uuid4())

        if description is None:
            description = _default_description(tool_name, parameters)

        req = ApprovalRequest(
            approval_id=approval_id,
            tool_name=tool_name,
            parameters=parameters,
            description=description,
            user_id=user_id,
            session_id=session_id,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=timeout_minutes),
        )

        with self._lock:
            self._store[approval_id] = req

        logger.info(
            "Onay isteği oluşturuldu",
            extra={
                "approval_id": approval_id,
                "tool_name": tool_name,
                "user_id": user_id,
                "session_id": session_id,
            },
        )
        return approval_id

    def get_status(self, approval_id: str) -> ApprovalStatus:
        """
        Onay isteğinin mevcut durumunu döner.

        Süresi dolmuş `PENDING` istekler otomatik olarak `EXPIRED` döner.

        Args:
            approval_id: Onay ID'si

        Returns:
            ApprovalStatus (PENDING | APPROVED | REJECTED | EXPIRED)
        """
        with self._lock:
            req = self._store.get(approval_id)

        if req is None:
            logger.warning("Onay isteği bulunamadı", extra={"approval_id": approval_id})
            return ApprovalStatus.EXPIRED

        if req.status == ApprovalStatus.PENDING and req.is_expired():
            with self._lock:
                req.status = ApprovalStatus.EXPIRED
            logger.info(
                "Onay isteği süresi doldu", extra={"approval_id": approval_id}
            )

        return req.status

    def get_request(self, approval_id: str) -> ApprovalRequest | None:
        """Onay isteğini döner (None ise bulunamadı)."""
        with self._lock:
            return self._store.get(approval_id)

    def resolve(
        self,
        approval_id: str,
        approved: bool,
        resolved_by: str | None = None,
    ) -> ApprovalRequest | None:
        """
        Onay isteğini karara bağlar.

        Args:
            approval_id : Onay ID'si
            approved    : True → onaylandı, False → reddedildi
            resolved_by : Kararı veren kullanıcı adı

        Returns:
            Güncellenen ApprovalRequest, bulunamazsa None.

        Raises:
            ValueError: İstek zaten karara bağlanmış veya süresi dolmuşsa.
        """
        with self._lock:
            req = self._store.get(approval_id)

        if req is None:
            logger.warning("Resolve: bulunamadı", extra={"approval_id": approval_id})
            return None

        if req.status != ApprovalStatus.PENDING:
            raise ValueError(
                f"Onay isteği ({approval_id}) zaten karara bağlanmış: {req.status.value}"
            )

        if req.is_expired():
            with self._lock:
                req.status = ApprovalStatus.EXPIRED
            raise ValueError(f"Onay isteği ({approval_id}) süresi dolmuş")

        with self._lock:
            req.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            req.resolved_at = datetime.now(timezone.utc)
            req.resolved_by = resolved_by

        logger.info(
            "Onay isteği karara bağlandı",
            extra={
                "approval_id": approval_id,
                "decision": "APPROVED" if approved else "REJECTED",
                "resolved_by": resolved_by,
            },
        )
        return req

    def list_pending(self, session_id: str | None = None) -> list[ApprovalRequest]:
        """
        Bekleyen (PENDING) onay isteklerini listeler.

        Args:
            session_id: Filtre (None ise tüm session'lar)

        Returns:
            PENDING durumundaki ApprovalRequest listesi
        """
        with self._lock:
            reqs = list(self._store.values())

        result = []
        for req in reqs:
            if req.status == ApprovalStatus.PENDING and not req.is_expired():
                if session_id is None or req.session_id == session_id:
                    result.append(req)
        return result

    def cleanup_expired(self) -> int:
        """
        Süresi dolmuş ve karara bağlanmış istekleri temizler.
        Bellek sızıntısını önlemek için periyodik çağrılabilir.

        Returns:
            Silinen kayıt sayısı
        """
        with self._lock:
            to_delete = [
                aid
                for aid, req in self._store.items()
                if req.status != ApprovalStatus.PENDING or req.is_expired()
            ]
            for aid in to_delete:
                del self._store[aid]

        if to_delete:
            logger.debug(f"Temizlendi: {len(to_delete)} eski onay isteği")
        return len(to_delete)


def _default_description(tool_name: str, parameters: dict[str, Any]) -> str:
    """Tool adına göre kullanıcı dostu onay açıklaması üretir."""
    descriptions = {
        "file_delete": lambda p: f"⚠️  '{p.get('path', '?')}' dosyasını kalıcı olarak silmek üzeresiniz.",
        "file_write":  lambda p: f"'{p.get('path', '?')}' dosyasını oluşturmak/üzerine yazmak üzeresiniz.",
        "file_move":   lambda p: f"'{p.get('src', '?')}' dosyasını '{p.get('dst', '?')}' konumuna taşımak üzeresiniz.",
        "db_insert":   lambda p: f"'{p.get('table', '?')}' tablosuna yeni kayıt eklemek üzeresiniz.",
        "db_update":   lambda p: f"'{p.get('table', '?')}' tablosunda ID={p.get('id', '?')} kaydını güncellemek üzeresiniz.",
        "db_delete":   lambda p: f"⚠️  '{p.get('table', '?')}' tablosundan ID={p.get('id', '?')} kaydını silmek üzeresiniz.",
        "mail_send":           lambda p: f"'{p.get('to', '?')}' adresine '{p.get('subject', '?')}' konulu e-posta göndermek üzeresiniz.",
        "calendar_add_event":  lambda p: f"'{p.get('title', '?')}' başlıklı etkinliği takvime eklemek üzeresiniz.",
        "calendar_delete_event": lambda p: f"⚠️  Takvimden ID={p.get('id', '?')} etkinliği silmek üzeresiniz.",
        "git_commit_and_push": lambda p: f"'{p.get('message', '?')}' commit mesajıyla '{p.get('branch', 'main')}' branch'ine push yapmak üzeresiniz.",
        "github_create_pull_request": lambda p: f"'{p.get('title', '?')}' başlıklı Pull Request açmak üzeresiniz.",
        "request_leave":  lambda p: f"'{p.get('employee_name', '?')}' için {p.get('start_date', '?')} – {p.get('end_date', '?')} tarihli izin talebi oluşturulmak üzere.",
        "approve_leave":  lambda p: f"İzin talebi ID={p.get('request_id', '?')} onaylanmak üzere.",
    }

    factory = descriptions.get(tool_name)
    if factory:
        try:
            return factory(parameters)
        except Exception:
            pass  # Fallback'e düş

    # Genel fallback
    param_str = ", ".join(f"{k}={v!r}" for k, v in list(parameters.items())[:3])
    return f"'{tool_name}' işlemini çalıştırmak üzeresiniz. Parametreler: {param_str}"


# Modül genelinde kullanılan tekil onay yöneticisi
# ⚠️ Bu singleton --workers 1 kısıtına dayalıdır
approval_manager = ApprovalManager()
