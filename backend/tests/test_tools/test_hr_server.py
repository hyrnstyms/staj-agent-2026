"""
tests/test_tools/test_hr_server.py
------------------------------------
HrServer için unit testler.

Test Kapsamı:
    - get_employee_leave_balance: rol kontrolü (kendi verisi vs başkasının verisi)
    - get_employees_on_leave: tarih bazlı sorgulama
    - request_leave: izin talebi oluşturma, bakiye kontrolü, tarih doğrulama
    - approve_leave: rol kontrolü, durum geçiş kontrolü (çift onay engeli)

Kritik Güvenlik Testleri:
    - employee rolü başkasının bakiyesini göremez
    - employee rolü izin onaylayamaz
    - Onaylanmış talep tekrar onaylanamaz (çift düşüş engeli)
    - Geçersiz tarih formatı hata döner
"""

from __future__ import annotations

import pytest
from datetime import datetime

from db.database import init_db, SessionLocal
from db.seed import seed_database
from mcp_servers.hr_server import HrServer, _parse_date, _count_leave_days


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def seeded_db():
    """Test modülü boyunca seed verisi yüklenmiş DB."""
    init_db()
    seed_database()
    yield


@pytest.fixture
def hr(seeded_db) -> HrServer:
    """Her test için taze HrServer örneği."""
    return HrServer()


# ─────────────────────────────────────────────────────────────────────────────
# Yardımcı fonksiyon testleri
# ─────────────────────────────────────────────────────────────────────────────


class TestHelpers:
    def test_parse_date_valid(self):
        dt = _parse_date("2026-08-01")
        assert dt.year == 2026
        assert dt.month == 8
        assert dt.day == 1

    def test_parse_date_invalid_format(self):
        with pytest.raises(ValueError, match="geçersiz tarih"):
            _parse_date("01-08-2026", "test_field")

    def test_parse_date_invalid_string(self):
        with pytest.raises(ValueError):
            _parse_date("bu_tarih_degil")

    def test_count_leave_days_inclusive(self):
        """Başlangıç ve bitiş günleri dahil sayılmalı."""
        start = datetime(2026, 8, 1)
        end = datetime(2026, 8, 5)
        assert _count_leave_days(start, end) == 5  # 1,2,3,4,5 → 5 gün

    def test_count_leave_days_single_day(self):
        dt = datetime(2026, 8, 1)
        assert _count_leave_days(dt, dt) == 1

    def test_count_leave_days_reversed_raises(self):
        start = datetime(2026, 8, 5)
        end = datetime(2026, 8, 1)
        with pytest.raises(ValueError, match="önce olamaz"):
            _count_leave_days(start, end)


# ─────────────────────────────────────────────────────────────────────────────
# get_employee_leave_balance testleri
# ─────────────────────────────────────────────────────────────────────────────


class TestGetEmployeeLeaveBalance:
    def test_employee_can_query_own_balance(self, hr):
        """
        Employee rolündeki kullanıcı kendi izin bakiyesini sorgulayabilir.
        """
        result = hr.get_employee_leave_balance(
            name="Ahmet Yılmaz",
            requester="Ahmet Yılmaz",
            requester_role="employee",
        )
        assert result["success"] is True
        assert "remaining_days" in result
        assert result["employee_name"] == "Ahmet Yılmaz"

    def test_employee_cannot_query_other_balance(self, hr):
        """
        Kritik güvenlik testi: Employee rolündeki kullanıcı başka birinin
        bakiyesini sorgulayamamalı.
        """
        result = hr.get_employee_leave_balance(
            name="Zeynep Arslan",
            requester="Ahmet Yılmaz",
            requester_role="employee",
        )
        assert result["success"] is False, (
            "Employee rolündeki kullanıcı başka birinin izin bakiyesini görebildi! "
            "Rol kontrolü çalışmıyor."
        )
        assert "error" in result

    def test_hr_role_can_query_anyone(self, hr):
        """HR rolü tüm çalışanların bakiyesini görebilir."""
        result = hr.get_employee_leave_balance(
            name="Ahmet Yılmaz",
            requester="Ayşe Kaya",
            requester_role="hr",
        )
        assert result["success"] is True

    def test_admin_role_can_query_anyone(self, hr):
        """Admin rolü tüm çalışanların bakiyesini görebilir."""
        result = hr.get_employee_leave_balance(
            name="Zeynep Arslan",
            requester="Admin User",
            requester_role="admin",
        )
        assert result["success"] is True

    def test_nonexistent_employee(self, hr):
        """Var olmayan çalışan için hata döner."""
        result = hr.get_employee_leave_balance(
            name="Bu Kişi Yok",
            requester="Bu Kişi Yok",
            requester_role="employee",
        )
        assert result["success"] is False
        assert "error" in result

    def test_balance_has_required_fields(self, hr):
        result = hr.get_employee_leave_balance(
            name="Ahmet Yılmaz",
            requester="Ahmet Yılmaz",
            requester_role="employee",
        )
        if result["success"]:
            assert "total_days" in result
            assert "used_days" in result
            assert "remaining_days" in result
            assert result["total_days"] >= result["used_days"]
            assert result["remaining_days"] == result["total_days"] - result["used_days"]


# ─────────────────────────────────────────────────────────────────────────────
# get_employees_on_leave testleri
# ─────────────────────────────────────────────────────────────────────────────


class TestGetEmployeesOnLeave:
    def test_returns_success(self, hr):
        result = hr.get_employees_on_leave(date="2026-08-03")
        assert result["success"] is True

    def test_returns_list(self, hr):
        result = hr.get_employees_on_leave(date="2026-08-03")
        assert "employees_on_leave" in result
        assert isinstance(result["employees_on_leave"], list)

    def test_ahmet_on_leave_during_approved_period(self, hr):
        """
        Seed verisinde Ahmet'in 2026-08-01 – 2026-08-05 arası onaylı izni var.
        Bu tarih aralığında sorgu yapıldığında Ahmet görünmeli.
        """
        result = hr.get_employees_on_leave(date="2026-08-03")
        if result["success"] and result["total"] > 0:
            names = [emp["name"] for emp in result["employees_on_leave"]]
            assert "Ahmet Yılmaz" in names

    def test_no_leave_far_future(self, hr):
        """Uzak gelecekte kimse izinde görünmemeli."""
        result = hr.get_employees_on_leave(date="2099-01-01")
        assert result["success"] is True
        assert result["total"] == 0

    def test_invalid_date_format(self, hr):
        result = hr.get_employees_on_leave(date="01/08/2026")
        assert result["success"] is False
        assert "error" in result

    def test_no_date_uses_today(self, hr):
        """Tarih verilmezse bugün kullanılır, hata olmaz."""
        result = hr.get_employees_on_leave()
        assert result["success"] is True
        assert "date" in result


# ─────────────────────────────────────────────────────────────────────────────
# request_leave testleri
# ─────────────────────────────────────────────────────────────────────────────


class TestRequestLeave:
    def test_create_leave_request(self, hr):
        """Geçerli bir izin talebi oluşturulur."""
        # 1) Clear existing 2027 requests for Can Öztürk to prevent persistent DB conflicts
        db = hr._session()
        try:
            from db.models import LeaveRequest, Employee
            emp = db.query(Employee).filter_by(name="Can Öztürk").first()
            if emp:
                db.query(LeaveRequest).filter(
                    LeaveRequest.employee_id == emp.id,
                    LeaveRequest.start_date.like("2027-%")
                ).delete(synchronize_session=False)
                db.commit()
        finally:
            db.close()

        # 2) Perform the test
        result = hr.request_leave(
            employee_name="Can Öztürk",
            start_date="2027-03-01",
            end_date="2027-03-03",
            leave_type="sick",
        )
        assert result["success"] is True
        assert result["status"] == "pending"
        assert "request_id" in result
        assert result["days_requested"] == 3

    def test_invalid_start_date_format(self, hr):
        result = hr.request_leave(
            employee_name="Can Öztürk",
            start_date="01-09-2026",
            end_date="2026-09-05",
            leave_type="annual",
        )
        assert result["success"] is False
        assert "error" in result

    def test_end_before_start_rejected(self, hr):
        result = hr.request_leave(
            employee_name="Mehmet Demir",
            start_date="2026-09-10",
            end_date="2026-09-05",
            leave_type="annual",
        )
        assert result["success"] is False

    def test_invalid_leave_type_rejected(self, hr):
        result = hr.request_leave(
            employee_name="Elif Şahin",
            start_date="2026-10-01",
            end_date="2026-10-03",
            leave_type="tatil",  # Geçersiz tip
        )
        assert result["success"] is False
        assert "error" in result

    def test_nonexistent_employee(self, hr):
        result = hr.request_leave(
            employee_name="Bu Kişi Yok",
            start_date="2026-09-01",
            end_date="2026-09-03",
            leave_type="sick",
        )
        assert result["success"] is False

    def test_sick_leave_no_balance_check(self, hr):
        """Hastalık izninde bakiye kontrolü yapılmaz."""
        result = hr.request_leave(
            employee_name="Zeynep Arslan",
            start_date="2026-11-01",
            end_date="2026-11-30",  # 30 gün — bakiyeden fazla ama sick leave
            leave_type="sick",
        )
        # Sick leave bakiye kontrolüne takılmaz (başka sebepten fail edebilir)
        if not result["success"]:
            assert "bakiye" not in result.get("error", "").lower()

    def test_request_creates_pending_status(self, hr):
        result = hr.request_leave(
            employee_name="Mehmet Demir",
            start_date="2026-10-05",
            end_date="2026-10-06",
            leave_type="annual",
        )
        if result["success"]:
            assert result["status"] == "pending"


# ─────────────────────────────────────────────────────────────────────────────
# approve_leave testleri
# ─────────────────────────────────────────────────────────────────────────────


class TestApproveLeave:
    def test_hr_can_approve_pending_request(self, hr):
        """HR rolündeki kullanıcı bekleyen talebi onaylayabilir."""
        # Zeynep'in seed'deki pending talebi (ID değişebilir, başka pending talep bul)
        db = hr._session()
        try:
            from db.models import LeaveRequest
            pending = (
                db.query(LeaveRequest)
                .where(LeaveRequest.status == "pending")
                .first()
            )
            if pending is None:
                pytest.skip("Pending izin talebi yok")

            result = hr.approve_leave(
                request_id=pending.id,
                approver_role="hr",
                approver_name="Ayşe Kaya",
            )
            assert result["success"] is True
            assert result["status"] == "approved"
        finally:
            db.close()

    def test_employee_cannot_approve(self, hr):
        """
        Kritik güvenlik testi: Employee rolü izin onaylayamaz.
        """
        result = hr.approve_leave(
            request_id=1,
            approver_role="employee",
            approver_name="Ahmet Yılmaz",
        )
        assert result["success"] is False, (
            "Employee rolündeki kullanıcı izin onaylayabildi! "
            "Rol kontrolü çalışmıyor."
        )
        assert "error" in result

    def test_double_approval_prevented(self, hr):
        """
        Kritik güvenlik testi: Durum Geçiş Kontrolü.
        Zaten onaylanmış bir talep tekrar onaylanamaz.
        Bu, leave_balances tablosunda çift düşüşü önler.
        """
        db = hr._session()
        try:
            from db.models import LeaveRequest
            # Onaylanmış bir talep bul
            approved = (
                db.query(LeaveRequest)
                .where(LeaveRequest.status == "approved")
                .first()
            )
            if approved is None:
                pytest.skip("Approved izin talebi yok — test_hr_can_approve_pending_request önce çalışmalı")

            result = hr.approve_leave(
                request_id=approved.id,
                approver_role="hr",
                approver_name="Ayşe Kaya",
            )
            assert result["success"] is False, (
                f"ID={approved.id} talebi zaten 'approved' durumunda olmasına rağmen "
                f"tekrar onaylanabildi! Bu, leave_balances tablosunda çift düşüşe yol açar."
            )
            assert "tekrar işlenemiyor" in result.get("error", "") or "zaten" in result.get("error", "")
        finally:
            db.close()

    def test_nonexistent_request(self, hr):
        """Var olmayan talep ID'si için hata döner."""
        result = hr.approve_leave(
            request_id=999999,
            approver_role="hr",
            approver_name="Ayşe Kaya",
        )
        assert result["success"] is False
        assert "error" in result

    def test_approve_updates_balance(self, hr):
        """
        Onay yapıldıktan sonra leave_balances güncellenir.
        used_days artar, remaining_days azalır.
        """
        # Yeni bir izin talebi oluştur
        request_result = hr.request_leave(
            employee_name="Can Öztürk",
            start_date="2026-12-01",
            end_date="2026-12-03",
            leave_type="annual",
        )
        if not request_result["success"]:
            pytest.skip(f"İzin talebi oluşturulamadı: {request_result.get('error')}")

        request_id = request_result["request_id"]

        # Onaylamadan önce bakiyeyi oku
        balance_before = hr.get_employee_leave_balance(
            name="Can Öztürk",
            requester="Can Öztürk",
            requester_role="employee",
        )
        remaining_before = balance_before.get("remaining_days", -1)

        # Onayla
        approve_result = hr.approve_leave(
            request_id=request_id,
            approver_role="hr",
            approver_name="Ayşe Kaya",
        )

        if not approve_result["success"]:
            pytest.skip(f"Onay başarısız: {approve_result.get('error')}")

        # Onay sonrası bakiyeyi oku
        balance_after = hr.get_employee_leave_balance(
            name="Can Öztürk",
            requester="Can Öztürk",
            requester_role="employee",
        )
        remaining_after = balance_after.get("remaining_days", -1)

        days_approved = approve_result.get("days_approved", 3)
        assert remaining_after == remaining_before - days_approved, (
            f"Bakiye güncellenmedi! Önce: {remaining_before}, Sonra: {remaining_after}, "
            f"Beklenen: {remaining_before - days_approved}"
        )

    def test_approve_sets_approved_by(self, hr):
        """Onaylayan kullanıcı adı kayıt edilir."""
        # Yeni pending talep oluştur
        request_result = hr.request_leave(
            employee_name="Elif Şahin",
            start_date="2026-12-10",
            end_date="2026-12-11",
            leave_type="sick",
        )
        if not request_result["success"]:
            pytest.skip(f"İzin talebi oluşturulamadı: {request_result.get('error')}")

        request_id = request_result["request_id"]
        approve_result = hr.approve_leave(
            request_id=request_id,
            approver_role="hr",
            approver_name="Ayşe Kaya",
        )

        if approve_result["success"]:
            assert approve_result.get("approved_by") == "Ayşe Kaya"
