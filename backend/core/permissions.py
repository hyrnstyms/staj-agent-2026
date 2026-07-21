"""
core/permissions.py
-------------------
Merkezi RBAC (Rol Bazlı Erişim Kontrolü) modülü.

Her tool çağrısından önce `check_permission()` çağrılır.
Her tool kendi izin kontrolünü yazmaz — yetki mantığı burada merkezileştirilmiştir.

Veri kaynağı: `permissions` DB tablosu (seed.py ile yüklenir).
Tablo yoksa veya kayıt bulunamazsa `deny_all_unknown` politikasına göre
varsayılan olarak reddedilir.

Kullanım:
    from core.permissions import permission_manager, PermissionResult

    result = permission_manager.check(user_role="employee", tool_name="file_read", db=db)
    if not result.allowed:
        raise HTTPException(403, result.reason)
    if result.requires_approval:
        # onay mekanizmasına yönlendir
        ...
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class PermissionResult:
    """
    İzin kontrolü sonucu.

    Attributes:
        allowed          : Kullanıcı bu tool'u çalıştırabilir mi?
        requires_approval: Çalıştırabiliyorsa kullanıcı onayı gerekiyor mu?
        reason           : İzin verilmeme nedeni (allowed=False ise dolu)
        role             : Kontrol edilen kullanıcı rolü
        tool_name        : Kontrol edilen tool adı
    """

    allowed: bool
    requires_approval: bool
    reason: str
    role: str
    tool_name: str


class PermissionManager:
    """
    Merkezi RBAC yöneticisi.

    Yöntemler:
        check(user_role, tool_name, db) → PermissionResult
        check_by_user_id(user_id, tool_name, db) → PermissionResult
    """

    def check(
        self,
        *,
        user_role: str,
        tool_name: str,
        db: Any,  # SQLAlchemy Session
    ) -> PermissionResult:
        """
        Rol ve tool adına göre erişim iznini kontrol eder.

        Args:
            user_role : Kullanıcının rolü ("employee" | "hr" | "admin")
            tool_name : Çağrılmak istenen tool adı
            db        : SQLAlchemy DB session'ı

        Returns:
            PermissionResult
        """
        from db.models import Permission  # geç import — döngü önlenir

        try:
            perm: Permission | None = (
                db.query(Permission)
                .filter(
                    Permission.role == user_role,
                    Permission.tool_name == tool_name,
                )
                .first()
            )
        except Exception as exc:
            logger.error(
                f"Permission DB sorgusunda hata: {exc}",
                extra={"role": user_role, "tool": tool_name},
            )
            return PermissionResult(
                allowed=False,
                requires_approval=False,
                reason=f"İzin sistemi erişim hatası: {exc}",
                role=user_role,
                tool_name=tool_name,
            )

        if perm is None:
            # Bilinmeyen kombinasyon — güvenli tarafta kal (deny)
            logger.warning(
                f"İzin kaydı bulunamadı, varsayılan: RED",
                extra={"role": user_role, "tool": tool_name},
            )
            return PermissionResult(
                allowed=False,
                requires_approval=False,
                reason=(
                    f"'{user_role}' rolü için '{tool_name}' tool izni "
                    f"tanımlanmamış (varsayılan: reddedildi)"
                ),
                role=user_role,
                tool_name=tool_name,
            )

        if not perm.allowed:
            logger.info(
                f"Erişim reddedildi",
                extra={"role": user_role, "tool": tool_name},
            )
            return PermissionResult(
                allowed=False,
                requires_approval=False,
                reason=f"'{user_role}' rolünün '{tool_name}' tool'una erişim yetkisi yok",
                role=user_role,
                tool_name=tool_name,
            )

        logger.debug(
            f"Erişim izni verildi",
            extra={
                "role": user_role,
                "tool": tool_name,
                "requires_approval": perm.requires_approval,
            },
        )
        return PermissionResult(
            allowed=True,
            requires_approval=perm.requires_approval,
            reason="",
            role=user_role,
            tool_name=tool_name,
        )

    def check_by_user_id(
        self,
        *,
        user_id: int,
        tool_name: str,
        db: Any,
    ) -> PermissionResult:
        """
        Kullanıcı ID'sine göre erişim iznini kontrol eder.

        Kullanıcının rolünü DB'den çeker, ardından `check()` çağırır.

        Args:
            user_id  : Kullanıcı ID'si
            tool_name: Çağrılmak istenen tool adı
            db       : SQLAlchemy DB session'ı

        Returns:
            PermissionResult
        """
        from db.models import User  # geç import

        user: User | None = db.query(User).filter(User.id == user_id).first()

        if user is None:
            return PermissionResult(
                allowed=False,
                requires_approval=False,
                reason=f"Kullanıcı ID={user_id} bulunamadı",
                role="unknown",
                tool_name=tool_name,
            )

        if not user.is_active:
            return PermissionResult(
                allowed=False,
                requires_approval=False,
                reason=f"Kullanıcı ID={user_id} aktif değil",
                role=user.role,
                tool_name=tool_name,
            )

        return self.check(user_role=user.role, tool_name=tool_name, db=db)


# Modül genelinde kullanılan tekil permission yöneticisi
permission_manager = PermissionManager()
