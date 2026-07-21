"""
db/models.py
------------
SQLAlchemy ORM modelleri.

Tablolar:
    - users            : Sisteme giriş yapan kullanıcılar (rol bazlı)
    - employees        : Şirket çalışan kaydı
    - leave_requests   : İzin talepleri
    - leave_balances   : Çalışan başına yıllık izin bakiyesi
    - tool_call_logs   : Her tool çağrısının denetim kaydı
    - permissions      : Rol × tool erişim matrisi

Notlar:
    - Tüm tablolar `created_at` / `updated_at` timestamp'lerine sahip.
    - `tool_call_logs` asla silinmemeli; denetim kaydı olarak kalıcıdır.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    """UTC'de şu anki zamanı döner."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Tüm modellerin türediği temel sınıf."""


# ─────────────────────────────────────────────────────────────────────────────
# users
# ─────────────────────────────────────────────────────────────────────────────
class User(Base):
    """
    Sisteme giriş yapan kullanıcılar.

    Roller:
        - employee : Normal çalışan (kendi verilerine erişir)
        - hr       : İK yöneticisi (tüm çalışan verilerine erişir, izin onaylayabilir)
        - admin    : Tam erişim
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="employee"
    )  # 'employee' | 'hr' | 'admin'
    api_key_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="⚠️ Faz 1 geçici auth — hash'lenmiş API key",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    # İlişkiler
    tool_call_logs: Mapped[list[ToolCallLog]] = relationship(
        "ToolCallLog", back_populates="user", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# employees
# ─────────────────────────────────────────────────────────────────────────────
class Employee(Base):
    """Şirket çalışan kaydı (HR senaryosu için)."""

    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    # İlişkiler
    leave_requests: Mapped[list[LeaveRequest]] = relationship(
        "LeaveRequest", back_populates="employee", lazy="dynamic"
    )
    leave_balances: Mapped[list[LeaveBalance]] = relationship(
        "LeaveBalance", back_populates="employee", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<Employee id={self.id} name={self.name!r} dept={self.department!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# leave_requests
# ─────────────────────────────────────────────────────────────────────────────
class LeaveRequest(Base):
    """Çalışan izin talepleri."""

    __tablename__ = "leave_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id"), nullable=False
    )
    leave_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'annual' | 'sick' | 'unpaid' | ...
    start_date: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # ISO 8601: YYYY-MM-DD
    end_date: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # 'pending' | 'approved' | 'rejected'
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    # İlişkiler
    employee: Mapped[Employee] = relationship(
        "Employee", back_populates="leave_requests"
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveRequest id={self.id} employee_id={self.employee_id} "
            f"status={self.status!r} {self.start_date}→{self.end_date}>"
        )


# ─────────────────────────────────────────────────────────────────────────────
# leave_balances
# ─────────────────────────────────────────────────────────────────────────────
class LeaveBalance(Base):
    """Çalışan başına yıllık izin bakiyesi."""

    __tablename__ = "leave_balances"
    __table_args__ = (
        UniqueConstraint("employee_id", "year", name="uq_leave_balance_emp_year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    total_days: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    used_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    remaining_days: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    # İlişkiler
    employee: Mapped[Employee] = relationship(
        "Employee", back_populates="leave_balances"
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveBalance emp={self.employee_id} year={self.year} "
            f"remaining={self.remaining_days}/{self.total_days}>"
        )


# ─────────────────────────────────────────────────────────────────────────────
# tool_call_logs
# ─────────────────────────────────────────────────────────────────────────────
class ToolCallLog(Base):
    """
    Her tool çağrısının denetim kaydı.

    ⚠️  Bu tablo hiçbir zaman silinmemeli — denetim kaydı olarak kalıcıdır.
    """

    __tablename__ = "tool_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    session_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    parameters_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}"
    )  # JSON string
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # 'pending' | 'approved' | 'rejected' | 'success' | 'error'
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Tool çalışma süresi (ms)"
    )

    # İlişkiler
    user: Mapped[User | None] = relationship("User", back_populates="tool_call_logs")

    def get_parameters(self) -> dict[str, Any]:
        """JSON string'i dict olarak döner."""
        return json.loads(self.parameters_json or "{}")

    def get_result(self) -> Any:
        """JSON string'i Python nesnesine döner."""
        if self.result_json is None:
            return None
        return json.loads(self.result_json)

    def __repr__(self) -> str:
        return (
            f"<ToolCallLog id={self.id} tool={self.tool_name!r} "
            f"status={self.status!r} at={self.timestamp}>"
        )


# ─────────────────────────────────────────────────────────────────────────────
# permissions
# ─────────────────────────────────────────────────────────────────────────────
class Permission(Base):
    """
    Rol × tool erişim matrisi.

    Her (role, tool_name) çifti için:
        - allowed          : Bu rol bu tool'u çağırabilir mi?
        - requires_approval: Çağırabiliyorsa onay gerekiyor mu?
    """

    __tablename__ = "permissions"
    __table_args__ = (
        UniqueConstraint("role", "tool_name", name="uq_permission_role_tool"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    requires_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<Permission role={self.role!r} tool={self.tool_name!r} "
            f"allowed={self.allowed} approval={self.requires_approval}>"
        )
