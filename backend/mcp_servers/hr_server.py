"""
mcp_servers/hr_server.py
------------------------
İnsan Kaynakları MCP Server — Faz 2 tam implementasyon.

DatabaseServer'ın üzerine HR-spesifik bir katman olarak inşa edilmiştir.
Bu modül, hassas HR tablolarına (employees, leave_requests, leave_balances)
erişim sağlar; ancak her fonksiyon kendi rol ve durum kontrolünü uygular.

Güvenlik Modeli:
    ✅  Rol kontrolü: employee yalnızca kendi verisine erişir;
        HR/admin tüm çalışanları görebilir.
    ✅  Durum geçiş kontrolü: approve_leave yalnızca "pending"
        durumundaki talepler için çalışır; zaten karara bağlanmış
        talepler tekrar işlenemez (çift düşüş önlenir).
    ✅  Bakiye yeterliliği kontrolü: request_leave, yeterli izin
        hakkı yoksa talebi reddeder.
    ✅  Tarih parse işlemi deterministik Python (datetime.strptime)
        ile yapılır; modele bırakılmaz.
    ✅  Tüm DB erişimi ORM parametreli sorgularla yapılır.

Tool'lar:
    - get_employee_leave_balance(name, requester)           → dict
    - get_employees_on_leave(date)                         → dict
    - request_leave(employee_name, start_date, end_date,
                    leave_type)                            → dict
    - approve_leave(request_id, approver_role)             → dict

Kullanım:
    from mcp_servers.hr_server import hr_server

    result = hr_server.get_employee_leave_balance(
        name="Ahmet Yılmaz", requester="Ahmet Yılmaz"
    )
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from core.logger import get_logger
from db.database import SessionLocal
from db.models import Employee, LeaveBalance, LeaveRequest

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Sabitler
# ─────────────────────────────────────────────────────────────────────────────

# Bu rollerdeki kullanıcılar tüm çalışanların verilerini görebilir
PRIVILEGED_ROLES: frozenset[str] = frozenset({"hr", "admin"})

# Geçerli izin tipleri
VALID_LEAVE_TYPES: frozenset[str] = frozenset(
    {"annual", "sick", "unpaid", "maternity", "paternity", "bereavement"}
)

# Tarih formatı (deterministik parse)
DATE_FORMAT = "%Y-%m-%d"


# ─────────────────────────────────────────────────────────────────────────────
# Yardımcı fonksiyonlar
# ─────────────────────────────────────────────────────────────────────────────


def _parse_date(date_str: str, field_name: str = "tarih") -> datetime:
    """
    ISO 8601 tarih dizesini (YYYY-MM-DD) deterministik olarak parse eder.

    ⚠️  Tarih hesaplama modele bırakılmaz; Python datetime modülü kullanılır.

    Args:
        date_str  : Parse edilecek tarih dizesi
        field_name: Hata mesajı için alan adı

    Returns:
        datetime nesnesi

    Raises:
        ValueError: Format geçersizse
    """
    try:
        return datetime.strptime(date_str.strip(), DATE_FORMAT)
    except (ValueError, AttributeError):
        raise ValueError(
            f"'{field_name}' için geçersiz tarih formatı: '{date_str}'. "
            f"Beklenen format: YYYY-MM-DD (örn: 2026-08-01)"
        )


def _count_leave_days(start_date: datetime, end_date: datetime) -> int:
    """
    İzin başlangıç ve bitiş tarihleri arasındaki gün sayısını hesaplar.
    Başlangıç ve bitiş günleri dahil (inclusive).

    Args:
        start_date: İzin başlangıç tarihi
        end_date  : İzin bitiş tarihi

    Returns:
        Toplam izin günü sayısı

    Raises:
        ValueError: Bitiş tarihi başlangıçtan önce ise
    """
    if end_date < start_date:
        raise ValueError(
            f"Bitiş tarihi ({end_date.date()}) başlangıç tarihinden "
            f"({start_date.date()}) önce olamaz."
        )
    return (end_date - start_date).days + 1


def _find_employee(db, name: str) -> Employee | None:
    """
    İsme göre çalışanı arar (ORM parametreli sorgu).

    Tam eşleşme önce denenir, bulunamazsa büyük/küçük harf duyarsız
    'içerir' araması yapılır.
    """
    # Tam eşleşme (case-sensitive)
    emp = db.query(Employee).where(Employee.name == name).first()
    if emp:
        return emp

    # Büyük/küçük harf duyarsız içerir araması
    # SQLite LIKE varsayılan olarak ASCII karakterler için case-insensitive
    emp = db.query(Employee).filter(
        Employee.name.ilike(f"%{name}%")
    ).first()
    return emp


# ─────────────────────────────────────────────────────────────────────────────
# HrServer
# ─────────────────────────────────────────────────────────────────────────────


class HrServer:
    """
    İK (İnsan Kaynakları) tool koleksiyonu.

    Hassas HR tablolarına erişim bu sınıf üzerinden yapılır.
    Her metod kendi yetki ve durum kontrolünü uygular.
    """

    def _session(self):
        """Yeni bir DB session açar. Çağıran taraf kapatmakla sorumludur."""
        return SessionLocal()

    # ── İzin Bakiyesi ────────────────────────────────────────────────────────

    def get_employee_leave_balance(
        self, name: str, requester: str, requester_role: str = "employee"
    ) -> dict[str, Any]:
        """
        Çalışanın izin bakiyesini döner.

        Rol kontrolü:
            - employee: Yalnızca kendi bakiyesini sorgulayabilir.
            - hr / admin: Tüm çalışanların bakiyesini görebilir.

        Args:
            name          : Sorgulanacak çalışanın adı
            requester     : İsteği yapan kullanıcının adı
            requester_role: İsteği yapan kullanıcının rolü

        Returns:
            {
                "success": True,
                "employee_name": str,
                "year": int,
                "total_days": int,
                "used_days": int,
                "remaining_days": int,
                "pending_requests": int,
            }
        """
        db = self._session()
        try:
            # ── Rol kontrolü ─────────────────────────────────────────────────
            if requester_role not in PRIVILEGED_ROLES:
                # Employee yalnızca kendisini sorgulayabilir
                if name.lower().strip() != requester.lower().strip():
                    logger.warning(
                        "get_employee_leave_balance — yetersiz yetki",
                        extra={
                            "requester": requester,
                            "target": name,
                            "role": requester_role,
                        },
                    )
                    return {
                        "success": False,
                        "error": (
                            f"'{requester_role}' rolündeki kullanıcı yalnızca kendi "
                            f"izin bakiyesini sorgulayabilir. Başka bir çalışanın "
                            f"bakiyesini görmek için HR veya Admin yetkisi gereklidir."
                        ),
                    }

            # ── Çalışanı bul ─────────────────────────────────────────────────
            emp = _find_employee(db, name)
            if emp is None:
                return {
                    "success": False,
                    "error": f"'{name}' adında bir çalışan bulunamadı.",
                }

            # ── Bu yılki bakiyeyi al ─────────────────────────────────────────
            current_year = datetime.now().year
            balance: LeaveBalance | None = (
                db.query(LeaveBalance)
                .where(
                    LeaveBalance.employee_id == emp.id,
                    LeaveBalance.year == current_year,
                )
                .first()
            )

            if balance is None:
                return {
                    "success": False,
                    "error": (
                        f"'{emp.name}' için {current_year} yılı izin bakiyesi bulunamadı."
                    ),
                }

            # ── Beklemedeki talep sayısı ──────────────────────────────────────
            pending_count = (
                db.query(LeaveRequest)
                .where(
                    LeaveRequest.employee_id == emp.id,
                    LeaveRequest.status == "pending",
                )
                .count()
            )

            logger.info(
                "get_employee_leave_balance",
                extra={"employee": emp.name, "requester": requester},
            )
            return {
                "success": True,
                "employee_name": emp.name,
                "department": emp.department,
                "year": current_year,
                "total_days": balance.total_days,
                "used_days": balance.used_days,
                "remaining_days": balance.remaining_days,
                "pending_requests": pending_count,
            }
        finally:
            db.close()

    # ── İzinde Olan Çalışanlar ───────────────────────────────────────────────

    def get_employees_on_leave(self, date: str | None = None) -> dict[str, Any]:
        """
        Belirtilen tarihte onaylanmış izinde olan çalışanları listeler.

        ⚠️  Tarih parse işlemi deterministik Python datetime ile yapılır.

        Args:
            date: ISO 8601 tarihi (YYYY-MM-DD). None ise bugünkü tarih kullanılır.

        Returns:
            {
                "success": True,
                "date": str,
                "employees_on_leave": [{"name": str, "department": str,
                                        "leave_type": str, "end_date": str}, ...]
                "total": int,
            }
        """
        db = self._session()
        try:
            # ── Tarih parse (deterministik) ──────────────────────────────────
            if date:
                query_date = _parse_date(date, "date")
            else:
                query_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            date_str = query_date.strftime(DATE_FORMAT)

            # ── Onaylanmış ve tarihi kapsayan talepleri bul ──────────────────
            # Koşul: start_date <= date_str <= end_date AND status = "approved"
            # SQLAlchemy ORM parametreli bağlama (SQL injection güvenli)
            approved_requests = (
                db.query(LeaveRequest)
                .where(
                    LeaveRequest.status == "approved",
                    LeaveRequest.start_date <= date_str,
                    LeaveRequest.end_date >= date_str,
                )
                .all()
            )

            result_list = []
            for req in approved_requests:
                emp = db.query(Employee).where(Employee.id == req.employee_id).first()
                if emp:
                    result_list.append(
                        {
                            "name": emp.name,
                            "department": emp.department,
                            "leave_type": req.leave_type,
                            "start_date": req.start_date,
                            "end_date": req.end_date,
                        }
                    )

            logger.info(
                "get_employees_on_leave",
                extra={"date": date_str, "count": len(result_list)},
            )
            return {
                "success": True,
                "date": date_str,
                "employees_on_leave": result_list,
                "total": len(result_list),
            }
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        finally:
            db.close()

    # ── İzin Talebi ──────────────────────────────────────────────────────────

    def request_leave(
        self,
        employee_name: str,
        start_date: str,
        end_date: str,
        leave_type: str,
    ) -> dict[str, Any]:
        """
        Çalışan adına izin talebi oluşturur.

        ⚠️  Bu işlem onay gerektirir (tool_executor.py tarafından kontrol edilir).
        ⚠️  Tarih parse işlemi deterministik Python datetime ile yapılır.
        ⚠️  Bakiye yeterliliği kontrol edilir; yetersizse talep reddedilir.

        Args:
            employee_name: İzin talep eden çalışanın adı
            start_date   : İzin başlangıç tarihi (YYYY-MM-DD)
            end_date     : İzin bitiş tarihi (YYYY-MM-DD)
            leave_type   : İzin türü (annual | sick | unpaid | ...)

        Returns:
            {
                "success": True,
                "request_id": int,
                "employee_name": str,
                "start_date": str,
                "end_date": str,
                "leave_type": str,
                "days_requested": int,
                "status": "pending",
            }
        """
        db = self._session()
        try:
            # ── Tarih parse (deterministik) ──────────────────────────────────
            start = _parse_date(start_date, "start_date")
            end = _parse_date(end_date, "end_date")
            days_requested = _count_leave_days(start, end)

            # ── İzin tipi doğrulaması ─────────────────────────────────────────
            if leave_type not in VALID_LEAVE_TYPES:
                return {
                    "success": False,
                    "error": (
                        f"Geçersiz izin tipi: '{leave_type}'. "
                        f"Geçerli tipler: {sorted(VALID_LEAVE_TYPES)}"
                    ),
                }

            # ── Çalışanı bul ─────────────────────────────────────────────────
            emp = _find_employee(db, employee_name)
            if emp is None:
                return {
                    "success": False,
                    "error": f"'{employee_name}' adında bir çalışan bulunamadı.",
                }

            # ── Bakiye yeterliliği kontrolü (yalnızca yıllık izin için) ─────
            if leave_type == "annual":
                current_year = start.year
                balance = (
                    db.query(LeaveBalance)
                    .where(
                        LeaveBalance.employee_id == emp.id,
                        LeaveBalance.year == current_year,
                    )
                    .first()
                )
                if balance is None:
                    return {
                        "success": False,
                        "error": (
                            f"'{emp.name}' için {current_year} yılı izin bakiyesi bulunamadı."
                        ),
                    }
                if balance.remaining_days < days_requested:
                    return {
                        "success": False,
                        "error": (
                            f"Yetersiz izin bakiyesi. Talep edilen: {days_requested} gün, "
                            f"Mevcut bakiye: {balance.remaining_days} gün."
                        ),
                    }

            # ── Çakışan onaylı izin kontrolü ─────────────────────────────────
            conflict = (
                db.query(LeaveRequest)
                .where(
                    LeaveRequest.employee_id == emp.id,
                    LeaveRequest.status == "approved",
                    LeaveRequest.start_date <= end_date,
                    LeaveRequest.end_date >= start_date,
                )
                .first()
            )
            if conflict:
                return {
                    "success": False,
                    "error": (
                        f"Bu tarih aralığında ({start_date} – {end_date}) zaten "
                        f"onaylanmış bir izin talebi mevcut (ID: {conflict.id})."
                    ),
                }

            # ── Talebi oluştur ───────────────────────────────────────────────
            new_request = LeaveRequest(
                employee_id=emp.id,
                leave_type=leave_type,
                start_date=start_date,
                end_date=end_date,
                status="pending",
            )
            db.add(new_request)
            db.commit()
            db.refresh(new_request)

            logger.info(
                "request_leave",
                extra={
                    "employee": emp.name,
                    "leave_type": leave_type,
                    "start": start_date,
                    "end": end_date,
                    "days": days_requested,
                    "request_id": new_request.id,
                },
            )
            return {
                "success": True,
                "request_id": new_request.id,
                "employee_name": emp.name,
                "start_date": start_date,
                "end_date": end_date,
                "leave_type": leave_type,
                "days_requested": days_requested,
                "status": "pending",
                "message": (
                    f"İzin talebi oluşturuldu (ID: {new_request.id}). "
                    f"İK yöneticisinin onayı bekleniyor."
                ),
            }
        except ValueError as exc:
            db.rollback()
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            db.rollback()
            logger.error(f"request_leave hatası: {exc}")
            return {"success": False, "error": str(exc)}
        finally:
            db.close()

    # ── İzin Onayı ───────────────────────────────────────────────────────────

    def approve_leave(
        self, request_id: int, approver_role: str, approver_name: str = "İK Yöneticisi"
    ) -> dict[str, Any]:
        """
        Beklemedeki (pending) izin talebini onaylar.

        ⚠️  Bu işlem onay gerektirir (tool_executor.py tarafından kontrol edilir).
        ⚠️  Yalnızca hr / admin rolündeki kullanıcılar onay verebilir.
        ⚠️  DURUM GEÇİŞ KONTROLÜ: Yalnızca status="pending" olan talepler
            işlenebilir. Zaten "approved" veya "rejected" durumundaki bir
            talep tekrar işlenmeye çalışılırsa hata döner — bu, leave_balances
            tablosunda çift düşüşü önler.

        Args:
            request_id   : Onaylanacak izin talebi ID'si
            approver_role: Onaylayan kullanıcının rolü (hr | admin)
            approver_name: Onaylayan kullanıcının adı (log için)

        Returns:
            {
                "success": True,
                "request_id": int,
                "employee_name": str,
                "status": "approved",
                "days_approved": int,
                "remaining_balance": int,
            }
        """
        db = self._session()
        try:
            # ── Rol kontrolü ─────────────────────────────────────────────────
            if approver_role not in PRIVILEGED_ROLES:
                logger.warning(
                    "approve_leave — yetersiz yetki",
                    extra={"approver_role": approver_role, "request_id": request_id},
                )
                return {
                    "success": False,
                    "error": (
                        f"'{approver_role}' rolündeki kullanıcı izin onaylayamaz. "
                        f"İzin onaylamak için 'hr' veya 'admin' yetkisi gereklidir."
                    ),
                }

            # ── Talebi bul ───────────────────────────────────────────────────
            leave_req: LeaveRequest | None = (
                db.query(LeaveRequest).where(LeaveRequest.id == request_id).first()
            )
            if leave_req is None:
                return {
                    "success": False,
                    "error": f"ID={request_id} izin talebi bulunamadı.",
                }

            # ── DURUM GEÇİŞ KONTROLÜ ─────────────────────────────────────────
            # Yalnızca "pending" talepler işlenebilir.
            # Bu kontrol olmadan aynı talep birden fazla kez onaylanıp
            # leave_balances'tan birden fazla gün düşebilir.
            if leave_req.status != "pending":
                logger.warning(
                    "approve_leave — zaten karara bağlanmış talep",
                    extra={
                        "request_id": request_id,
                        "current_status": leave_req.status,
                    },
                )
                return {
                    "success": False,
                    "error": (
                        f"ID={request_id} izin talebi zaten '{leave_req.status}' "
                        f"durumunda. Tekrar işlenemiyor (çift onay engellendi)."
                    ),
                }

            # ── Çalışan ve bakiyeyi bul ──────────────────────────────────────
            emp = db.query(Employee).where(Employee.id == leave_req.employee_id).first()
            if emp is None:
                return {"success": False, "error": "Çalışan kaydı bulunamadı."}

            # ── Gün hesabı (deterministik Python) ───────────────────────────
            start = _parse_date(leave_req.start_date, "start_date")
            end = _parse_date(leave_req.end_date, "end_date")
            days_approved = _count_leave_days(start, end)

            # ── Bakiyeyi güncelle (yalnızca yıllık izin için) ───────────────
            if leave_req.leave_type == "annual":
                balance = (
                    db.query(LeaveBalance)
                    .where(
                        LeaveBalance.employee_id == emp.id,
                        LeaveBalance.year == start.year,
                    )
                    .first()
                )
                if balance is None:
                    return {
                        "success": False,
                        "error": f"'{emp.name}' için {start.year} izin bakiyesi bulunamadı.",
                    }
                if balance.remaining_days < days_approved:
                    return {
                        "success": False,
                        "error": (
                            f"Onaylanamaz: Yetersiz bakiye. "
                            f"Talep edilen: {days_approved} gün, "
                            f"Mevcut: {balance.remaining_days} gün."
                        ),
                    }
                balance.used_days += days_approved
                balance.remaining_days -= days_approved
                remaining = balance.remaining_days
            else:
                remaining = None  # Ücretsiz/hastalık izinleri bakiyeyi düşürmez

            # ── Talebi güncelle ──────────────────────────────────────────────
            leave_req.status = "approved"
            leave_req.approved_by = approver_name
            db.commit()

            logger.info(
                "approve_leave",
                extra={
                    "request_id": request_id,
                    "employee": emp.name,
                    "days": days_approved,
                    "approver": approver_name,
                    "remaining_balance": remaining,
                },
            )
            return {
                "success": True,
                "request_id": request_id,
                "employee_name": emp.name,
                "leave_type": leave_req.leave_type,
                "start_date": leave_req.start_date,
                "end_date": leave_req.end_date,
                "status": "approved",
                "days_approved": days_approved,
                "remaining_balance": remaining,
                "approved_by": approver_name,
                "message": (
                    f"'{emp.name}' için {days_approved} günlük izin talebi onaylandı."
                ),
            }
        except ValueError as exc:
            db.rollback()
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            db.rollback()
            logger.error(f"approve_leave hatası: {exc}", extra={"request_id": request_id})
            return {"success": False, "error": str(exc)}
        finally:
            db.close()


# Modül genelinde kullanılan tekil server örneği
hr_server = HrServer()
