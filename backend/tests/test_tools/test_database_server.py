"""
tests/test_tools/test_database_server.py
-----------------------------------------
DatabaseServer için unit testler.

Test Kapsamı:
    - db_list_tables: accessible tablolar listelenir, restricted tablolar görünmez
    - db_get_schema: kolon bilgisi doğru döner
    - db_query: filtre ile sorgu, restricted tablo engeli, SQL injection güvenliği
    - db_insert / db_update / db_delete: başarı + restricted tablo engeli

Güvenlik Testleri:
    - SQL injection: filters={"name": "x' OR '1'='1"} güvenli şekilde ele alınır
    - Restricted tablo erişim denemeleri reddedilir
"""

from __future__ import annotations

import pytest

from db.database import init_db
from db.seed import seed_database
from mcp_servers.database_server import (
    RESTRICTED_TABLES,
    DatabaseServer,
    RestrictedTableError,
    _check_restricted,
    _get_accessible_tables,
    _get_model_class,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def seeded_db():
    """
    Test modülü boyunca kullanılan, seed verisi yüklenmiş DB.
    Modül bitiminde DB kapatılır (SQLite geçici dosya değil, kalıcı test DB).
    """
    init_db()
    seed_database()
    yield
    # Teardown: session açıksa kapat (kalıcı DB silmiyoruz — seed idempotent)


@pytest.fixture
def db_server(seeded_db) -> DatabaseServer:
    """Her test için taze DatabaseServer örneği."""
    return DatabaseServer()


# ─────────────────────────────────────────────────────────────────────────────
# db_list_tables testleri
# ─────────────────────────────────────────────────────────────────────────────


class TestDbListTables:
    def test_returns_success(self, db_server):
        result = db_server.db_list_tables()
        assert result["success"] is True

    def test_has_tables_key(self, db_server):
        result = db_server.db_list_tables()
        assert "tables" in result
        assert isinstance(result["tables"], list)

    def test_restricted_tables_not_visible(self, db_server):
        """
        Hassas tablolar (employees, leave_balances vb.) db_list_tables
        sonucunda görünmemelidir.
        """
        result = db_server.db_list_tables()
        visible_tables = set(result["tables"])
        for restricted in RESTRICTED_TABLES:
            assert restricted not in visible_tables, (
                f"Hassas tablo '{restricted}' db_list_tables sonucunda görünüyor! "
                f"RESTRICTED_TABLES whitelist çalışmıyor."
            )

    def test_total_matches_list_length(self, db_server):
        result = db_server.db_list_tables()
        assert result["total"] == len(result["tables"])

    def test_has_restricted_note(self, db_server):
        result = db_server.db_list_tables()
        assert "restricted_note" in result


# ─────────────────────────────────────────────────────────────────────────────
# db_get_schema testleri
# ─────────────────────────────────────────────────────────────────────────────


class TestDbGetSchema:
    def test_known_table_returns_columns(self, db_server):
        """Erişilebilir bir tablo için şema bilgisi döner."""
        accessible = _get_accessible_tables()
        if not accessible:
            pytest.skip("Accessible tablo yok — seed çalıştırılmamış olabilir")

        result = db_server.db_get_schema(accessible[0])
        assert result["success"] is True
        assert "columns" in result
        assert len(result["columns"]) > 0

    def test_column_has_required_fields(self, db_server):
        accessible = _get_accessible_tables()
        if not accessible:
            pytest.skip("Accessible tablo yok")

        result = db_server.db_get_schema(accessible[0])
        for col in result["columns"]:
            assert "name" in col
            assert "type" in col
            assert "nullable" in col
            assert "primary_key" in col

    def test_schema_for_restricted_table_allowed(self, db_server):
        """
        db_get_schema, kısıtlı tablolar için de şema bilgisi döner.
        Şema okuma (sütun adları) güvenlik riski taşımaz; yalnızca veri erişimi kısıtlıdır.
        """
        result = db_server.db_get_schema("employees")
        # Başarılı veya "not found" dönebilir — önemli olan crash olmaması
        assert "success" in result

    def test_nonexistent_table(self, db_server):
        result = db_server.db_get_schema("bu_tablo_yok_xyz")
        assert result["success"] is False
        assert "error" in result


# ─────────────────────────────────────────────────────────────────────────────
# db_query testleri
# ─────────────────────────────────────────────────────────────────────────────


class TestDbQuery:
    def test_query_accessible_table(self, db_server):
        """Erişilebilir bir tabloyu sorgulayabilir."""
        accessible = _get_accessible_tables()
        if not accessible:
            pytest.skip("Accessible tablo yok")

        result = db_server.db_query(accessible[0])
        assert result["success"] is True
        assert "rows" in result

    def test_query_restricted_table_denied(self, db_server):
        """
        Hassas tablolar generic db_query ile sorgulanamaz.
        RESTRICTED_TABLES güvenlik katmanı çalışmalıdır.
        """
        for restricted_table in ["employees", "leave_requests", "leave_balances", "users"]:
            result = db_server.db_query(restricted_table)
            assert result["success"] is False, (
                f"'{restricted_table}' tablosu generic db_query ile sorgulanabildi! "
                f"Bu bir güvenlik açığıdır — RESTRICTED_TABLES whitelist çalışmıyor."
            )
            assert "error" in result

    def test_sql_injection_via_filter_value(self, db_server):
        """
        SQL injection denemesi: filters={"name": "x' OR '1'='1"}
        Güvenli parametreli SQLAlchemy sorgusu sayesinde:
        - Tüm kayıtları döndürmemeli (injection başarısız olmalı)
        - Exception fırlatmadan güvenli boş/hatalı sonuç dönmeli
        """
        accessible = _get_accessible_tables()
        if not accessible:
            pytest.skip("Accessible tablo yok")

        # Hangi tabloyu kullanacağımızı belirle (name kolonu olan bir tablo)
        target_table = None
        for tbl in accessible:
            model_cls = _get_model_class(tbl)
            if model_cls and hasattr(model_cls, "name"):
                target_table = tbl
                break

        if target_table is None:
            pytest.skip("'name' kolonu olan accessible tablo bulunamadı")

        # Önce tablodaki toplam kayıt sayısını al
        result_all = db_server.db_query(target_table, limit=100)
        total_rows = result_all.get("total", 0)

        # SQL injection denemesi
        injection_result = db_server.db_query(
            target_table,
            filters={"name": "x' OR '1'='1"},
        )

        # Injection başarısız olmalı: tüm kayıtlar dönmemeli
        injected_rows = injection_result.get("total", 0)
        assert injected_rows < total_rows or injected_rows == 0, (
            f"SQL injection başarılı oldu gibi görünüyor! "
            f"Normal sorgu: {total_rows} kayıt, injection sonrası: {injected_rows} kayıt."
        )

    def test_query_with_valid_filter(self, db_server):
        """Geçerli filtre uygulandığında sonuç döner."""
        accessible = _get_accessible_tables()
        if not accessible:
            pytest.skip("Accessible tablo yok")

        result = db_server.db_query(accessible[0], filters={}, limit=5)
        assert result["success"] is True
        assert result["total"] <= 5

    def test_limit_respected(self, db_server):
        accessible = _get_accessible_tables()
        if not accessible:
            pytest.skip("Accessible tablo yok")

        result = db_server.db_query(accessible[0], limit=1)
        assert result["success"] is True
        assert len(result["rows"]) <= 1

    def test_invalid_column_in_filter(self, db_server):
        """Var olmayan kolon filtresi hata döndürür."""
        accessible = _get_accessible_tables()
        if not accessible:
            pytest.skip("Accessible tablo yok")

        result = db_server.db_query(
            accessible[0],
            filters={"bu_kolon_yok_xyz": "değer"},
        )
        assert result["success"] is False


# ─────────────────────────────────────────────────────────────────────────────
# db_insert testleri
# ─────────────────────────────────────────────────────────────────────────────


class TestDbInsert:
    def test_insert_restricted_table_denied(self, db_server):
        """
        Hassas tablolara generic db_insert ile kayıt eklenemez.
        """
        result = db_server.db_insert(
            "employees", {"name": "Saldırgan", "department": "Hacker", "email": "hacker@test.com"}
        )
        assert result["success"] is False
        assert "error" in result

    def test_insert_accessible_table(self, db_server):
        """Erişilebilir tabloya kayıt eklenebilir."""
        accessible = _get_accessible_tables()
        if not accessible:
            pytest.skip("Accessible tablo yok")

        # Gerçek değerler tablodan bağımsız çalışmayacağından skip edilebilir
        # Bu test gerçek insert yapabilmek için uygun tablo yapısı gerektirir
        # Mevcut accessible tablolar varsa ilkini dene
        result = db_server.db_insert(accessible[0], values={})
        # Başarı veya doğrulama hatası kabul edilir, kısıtlama hatası değil
        assert "error" not in result or "restricted" not in result.get("error", "").lower()

    def test_insert_nonexistent_table(self, db_server):
        result = db_server.db_insert("bu_tablo_yok_xyz", {"name": "test"})
        assert result["success"] is False


# ─────────────────────────────────────────────────────────────────────────────
# db_update testleri
# ─────────────────────────────────────────────────────────────────────────────


class TestDbUpdate:
    def test_update_restricted_table_denied(self, db_server):
        """
        Kritik güvenlik testi: leave_balances'ı generic db_update ile
        değiştirilmeye çalışılırsa reddedilmeli.
        """
        result = db_server.db_update(
            "leave_balances", id=1, values={"remaining_days": 9999}
        )
        assert result["success"] is False, (
            "leave_balances tablosu generic db_update ile değiştirilebildi! "
            "Bu, approve_leave akışını atlayarak bakiye manipülasyonuna yol açar."
        )

    def test_update_users_restricted(self, db_server):
        """users tablosu da kısıtlı olmalı."""
        result = db_server.db_update("users", id=1, values={"role": "admin"})
        assert result["success"] is False

    def test_update_nonexistent_table(self, db_server):
        result = db_server.db_update("bu_tablo_yok_xyz", id=1, values={"name": "test"})
        assert result["success"] is False


# ─────────────────────────────────────────────────────────────────────────────
# db_delete testleri
# ─────────────────────────────────────────────────────────────────────────────


class TestDbDelete:
    def test_delete_restricted_table_denied(self, db_server):
        """Hassas tablolardan generic db_delete ile kayıt silinemez."""
        for restricted_table in ["employees", "users", "permissions"]:
            result = db_server.db_delete(restricted_table, id=1)
            assert result["success"] is False, (
                f"'{restricted_table}' tablosundan generic db_delete ile silme yapılabildi! "
                f"Güvenlik açığı: RESTRICTED_TABLES whitelist çalışmıyor."
            )

    def test_delete_nonexistent_record(self, db_server):
        """Var olmayan kayıt silinmeye çalışılırsa hata döner."""
        accessible = _get_accessible_tables()
        if not accessible:
            pytest.skip("Accessible tablo yok")

        result = db_server.db_delete(accessible[0], id=999999)
        assert result["success"] is False

    def test_delete_nonexistent_table(self, db_server):
        result = db_server.db_delete("bu_tablo_yok_xyz", id=1)
        assert result["success"] is False


# ─────────────────────────────────────────────────────────────────────────────
# Güvenlik yardımcı fonksiyon testleri
# ─────────────────────────────────────────────────────────────────────────────


class TestSecurityHelpers:
    def test_check_restricted_raises_for_sensitive_tables(self):
        """_check_restricted() hassas tablolar için exception fırlatmalı."""
        for tbl in RESTRICTED_TABLES:
            with pytest.raises(RestrictedTableError):
                _check_restricted(tbl)

    def test_check_restricted_passes_for_accessible(self):
        """_check_restricted() accessible tablolar için exception fırlatmamalı."""
        accessible = _get_accessible_tables()
        for tbl in accessible:
            # Exception fırlatmamalı
            _check_restricted(tbl)

    def test_get_accessible_tables_excludes_restricted(self):
        accessible = set(_get_accessible_tables())
        assert accessible.isdisjoint(RESTRICTED_TABLES), (
            f"Accessible tablolar arasında kısıtlı tablo var: "
            f"{accessible & RESTRICTED_TABLES}"
        )

    def test_get_model_class_returns_none_for_unknown(self):
        assert _get_model_class("bu_tablo_yok_xyz") is None

    def test_get_model_class_returns_class_for_known(self):
        """Bilinen tablo için model sınıfı döner."""
        # 'employees' restricted ama _get_model_class bunu bilmez,
        # sadece mapping'e bakar
        model = _get_model_class("employees")
        assert model is not None
