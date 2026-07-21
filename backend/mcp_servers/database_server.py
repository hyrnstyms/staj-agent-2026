"""
mcp_servers/database_server.py
-------------------------------
Veritabanı MCP Server — Faz 2 tam implementasyon.

Güvenlik Modeli:
    ✅  RESTRICTED_TABLES: Hassas tablolara (employees, leave_requests,
        leave_balances, users, permissions, tool_call_logs) generic
        tool'larla erişilemez — bu tablolara yalnızca hr_server.py
        üzerinden, kendi rol kontrolüne sahip fonksiyonlarla erişilir.
    ✅  Tüm filtre değerleri SQLAlchemy ORM parametreli sorgularla
        (.where(col == value)) uygulanır; hiçbir yerde f-string/
        .format() ile SQL birleştirme yapılmaz.
    ✅  Yalnızca Base alt sınıfları (uygulama tabloları) erişilebilir;
        SQLite sistem tabloları (sqlite_master vb.) erişilemez.
    ✅  Geri döndürülemez işlemler (db_insert, db_update, db_delete)
        onay mekanizmasını tool_executor.py üzerinden tetikler.

Tool'lar:
    - db_list_tables()                          → dict
    - db_get_schema(table)                      → dict
    - db_query(table, filters, limit)           → dict
    - db_insert(table, values)                  → dict
    - db_update(table, id, values)              → dict
    - db_delete(table, id)                      → dict

Kullanım:
    from mcp_servers.database_server import DatabaseServer

    db_srv = DatabaseServer()
    result = db_srv.db_list_tables()
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import DeclarativeBase, Session

from core.logger import get_logger
from db.database import SessionLocal
from db.models import Base

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Güvenlik sabitleri
# ─────────────────────────────────────────────────────────────────────────────

# Generic tool'larla erişilemeyen hassas tablolar.
# Bu tablolara yalnızca hr_server.py içindeki, kendi rol kontrolüne
# sahip fonksiyonlar üzerinden erişilebilir.
RESTRICTED_TABLES: frozenset[str] = frozenset(
    {
        "employees",
        "leave_requests",
        "leave_balances",
        "users",
        "permissions",
        "tool_call_logs",
    }
)


class RestrictedTableError(PermissionError):
    """
    Generic DB tool'u hassas bir tabloya erişmeye çalışırsa fırlatılır.

    Çözüm: İlgili HR tool'unu (get_employee_leave_balance vb.) kullanın.
    """


# ─────────────────────────────────────────────────────────────────────────────
# Yardımcı fonksiyonlar
# ─────────────────────────────────────────────────────────────────────────────


def _get_model_class(table_name: str) -> type[DeclarativeBase] | None:
    """
    Tablo adından SQLAlchemy model sınıfını döner.

    Yalnızca Base alt sınıflarına erişim sağlar; SQLite sistem tabloları
    (sqlite_master vb.) bu yolla erişilemez.

    Args:
        table_name: Aranacak tablo adı

    Returns:
        Model sınıfı veya None (bulunamazsa)
    """
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        if hasattr(cls, "__tablename__") and cls.__tablename__ == table_name:
            return cls
    return None


def _get_accessible_tables() -> list[str]:
    """
    Generic DB tool'larının erişebildiği tablo adlarını döner.
    RESTRICTED_TABLES bu listede yer almaz.
    """
    all_tables = [
        mapper.class_.__tablename__
        for mapper in Base.registry.mappers
        if hasattr(mapper.class_, "__tablename__")
    ]
    return sorted(t for t in all_tables if t not in RESTRICTED_TABLES)


def _check_restricted(table: str) -> None:
    """
    Tablo kısıtlamasını kontrol eder; hassas tablo ise hata fırlatır.

    Bu fonksiyon her zaman try/except (RestrictedTableError) bloğu
    içinde çağrılmalıdır ki hata success:False'a dönüştürülebilsin.

    Args:
        table: Kontrol edilecek tablo adı

    Raises:
        RestrictedTableError: Tablo RESTRICTED_TABLES içindeyse
    """
    if table in RESTRICTED_TABLES:
        raise RestrictedTableError(
            f"Erisim Reddedildi: '{table}' tablosu hassas veriler icerdigi icin "
            f"generic DB tool'lariyla erisilemez. "
            f"Bu tabloya erismek icin ilgili HR fonksiyonunu kullanin "
            f"(get_employee_leave_balance, get_employees_on_leave vb.)."
        )


def _apply_filters(query, model_cls: type, filters: dict[str, Any]):
    """
    Filtre dict'ini SQLAlchemy ORM parametreli sorguya dönüştürür.

    Güvenlik: Hiçbir yerde f-string veya .format() ile SQL birleştirme
    yapılmaz. Tüm değerler SQLAlchemy'nin bind parametreleri üzerinden
    geçer — bu SQL injection saldırılarına karşı korur.

    Args:
        query     : Mevcut SQLAlchemy query nesnesi
        model_cls : Model sınıfı
        filters   : {"kolon_adı": değer} sözlüğü

    Returns:
        Filtrelenmiş query nesnesi

    Raises:
        ValueError: Filtre kolonunun modelde karşılığı yoksa
    """
    if not filters:
        return query

    for col_name, value in filters.items():
        if not hasattr(model_cls, col_name):
            raise ValueError(
                f"'{model_cls.__tablename__}' tablosunda '{col_name}' kolonu bulunamadı."
            )
        # SQLAlchemy ORM parametreli bind — SQL injection güvenli
        col_attr = getattr(model_cls, col_name)
        query = query.where(col_attr == value)

    return query


def _row_to_dict(row: Any) -> dict[str, Any]:
    """
    SQLAlchemy ORM nesnesini serileştirilebilir dict'e çevirir.

    __dict__ kullanır, SQLAlchemy dahili '_sa_instance_state' anahtarını çıkarır.
    """
    return {
        k: v
        for k, v in vars(row).items()
        if not k.startswith("_")
    }


# ─────────────────────────────────────────────────────────────────────────────
# DatabaseServer
# ─────────────────────────────────────────────────────────────────────────────


class DatabaseServer:
    """
    Generic veritabanı tool koleksiyonu.

    Yalnızca hassas olmayan (RESTRICTED_TABLES dışındaki) tablolara
    erişim sağlar. Tüm filtre değerleri parametreli SQLAlchemy ORM
    sorguları üzerinden geçer.

    Her metod kendi DB session'ını açıp kapatır (context-manager).
    """

    def _session(self) -> Session:
        """Yeni bir DB session açar. Çağıran taraf kapatmakla sorumludur."""
        return SessionLocal()

    # ── Okuma tool'ları ──────────────────────────────────────────────────────

    def db_list_tables(self) -> dict[str, Any]:
        """
        Generic DB tool'larının erişebildiği tablo listesini döner.

        Not: RESTRICTED_TABLES bu listede görünmez.

        Returns:
            {
                "success": True,
                "tables": ["tablo1", "tablo2", ...],
                "restricted_note": str,
                "total": int
            }
        """
        accessible = _get_accessible_tables()
        logger.info("db_list_tables", extra={"count": len(accessible)})
        return {
            "success": True,
            "tables": accessible,
            "restricted_note": (
                "Hassas tablolar (employees, leave_requests, leave_balances, "
                "users, permissions, tool_call_logs) bu listede gosterilmez; "
                "bunlara HR tool'lari uzerinden erisilir."
            ),
            "total": len(accessible),
        }

    def db_get_schema(self, table: str) -> dict[str, Any]:
        """
        Belirtilen tablonun şemasını (kolon adları, tipler, nullable) döner.

        RESTRICTED_TABLES dahil tüm tablolar için şema bilgisi döner
        (şema okuma güvenlik riski taşımaz; yalnızca veri erişimi kısıtlıdır).

        Args:
            table: Şeması alınacak tablo adı

        Returns:
            {
                "success": True,
                "table": str,
                "columns": [{"name": str, "type": str, "nullable": bool, "primary_key": bool}, ...]
            }
        """
        db = self._session()
        try:
            inspector = sa_inspect(db.bind)
            available_tables = inspector.get_table_names()

            if table not in available_tables:
                return {
                    "success": False,
                    "error": f"'{table}' tablosu bulunamadı. Mevcut tablolar: {available_tables}",
                }

            columns_info = inspector.get_columns(table)

            # SQLite'ta get_pk_constraint() farklı formatlar dönebilir — güvenli parse
            pk_constraint = inspector.get_pk_constraint(table)
            constrained_cols = pk_constraint.get("constrained_columns", [])
            pk_info: set[str] = set()
            for col in constrained_cols:
                if isinstance(col, dict):
                    pk_info.add(col.get("name", ""))
                elif isinstance(col, str):
                    pk_info.add(col)

            columns = [
                {
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col.get("nullable", True),
                    "primary_key": col["name"] in pk_info,
                }
                for col in columns_info
            ]

            logger.info("db_get_schema", extra={"table": table, "col_count": len(columns)})
            return {
                "success": True,
                "table": table,
                "columns": columns,
                "total_columns": len(columns),
            }
        finally:
            db.close()

    def db_query(
        self,
        table: str,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """
        Filtre ile tablo sorgusu yapar.

        Güvenlik:
            - RESTRICTED_TABLES reddedilir (success: False döner).
            - Filtreler SQLAlchemy ORM parametreli bağlama ile uygulanır
              (f-string/SQL birleştirme yok — SQL injection korumalı).

        Args:
            table  : Sorgulanacak tablo adı
            filters: {"kolon": değer} filtre sözlüğü (None = filtre yok)
            limit  : Maksimum döndürülecek satır sayısı (maks. 100)

        Returns:
            {"success": True, "table": str, "rows": list[dict], "total": int}
        """
        model_cls = _get_model_class(table)

        limit = min(max(1, limit), 100)
        filters = filters or {}

        db = self._session()
        try:
            _check_restricted(table)  # RestrictedTableError → except bloğunda yakalanır

            if model_cls is None:
                return {
                    "success": False,
                    "error": f"'{table}' tablosu bulunamadı veya erişilemiyor.",
                }

            query = db.query(model_cls)
            query = _apply_filters(query, model_cls, filters)
            rows = query.limit(limit).all()
            result_rows = [_row_to_dict(r) for r in rows]

            logger.info(
                "db_query",
                extra={"table": table, "filters": filters, "returned": len(result_rows)},
            )
            return {
                "success": True,
                "table": table,
                "filters_applied": filters,
                "rows": result_rows,
                "total": len(result_rows),
            }
        except (RestrictedTableError, ValueError) as exc:
            logger.warning(f"db_query reddedildi: {exc}", extra={"table": table})
            return {"success": False, "error": str(exc)}
        finally:
            db.close()

    # ── Yazma tool'ları ──────────────────────────────────────────────────────

    def db_insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        """
        Tabloya yeni kayıt ekler.

        Bu işlem onay gerektirir (tool_executor.py tarafından kontrol edilir).
        RESTRICTED_TABLES reddedilir.

        Args:
            table : Kayıt eklenecek tablo adı
            values: {"kolon": değer} sözlüğü

        Returns:
            {"success": True, "table": str, "inserted_id": int}
        """
        db = self._session()
        try:
            _check_restricted(table)  # RestrictedTableError → except bloğunda yakalanır

            model_cls = _get_model_class(table)
            if model_cls is None:
                return {
                    "success": False,
                    "error": f"'{table}' tablosu bulunamadı veya erişilemiyor.",
                }

            valid_cols = {c.key for c in sa_inspect(model_cls).mapper.columns}
            safe_values = {k: v for k, v in values.items() if k in valid_cols}

            new_row = model_cls(**safe_values)
            db.add(new_row)
            db.commit()
            db.refresh(new_row)

            inserted_id = getattr(new_row, "id", None)
            logger.info("db_insert", extra={"table": table, "id": inserted_id})
            return {
                "success": True,
                "table": table,
                "inserted_id": inserted_id,
                "data": _row_to_dict(new_row),
            }
        except (RestrictedTableError, ValueError) as exc:
            db.rollback()
            logger.warning(f"db_insert reddedildi: {exc}", extra={"table": table})
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            db.rollback()
            logger.error(f"db_insert hatası: {exc}", extra={"table": table})
            return {"success": False, "error": str(exc)}
        finally:
            db.close()

    def db_update(self, table: str, id: int, values: dict[str, Any]) -> dict[str, Any]:
        """
        ID ile kayıt günceller.

        Bu işlem onay gerektirir (tool_executor.py tarafından kontrol edilir).
        RESTRICTED_TABLES reddedilir.
        Filtre değerleri SQLAlchemy ORM parametreli bağlama ile uygulanır.

        Args:
            table : Güncellenecek tablo adı
            id    : Güncellenecek kaydın primary key değeri
            values: {"kolon": yeni_değer} sözlüğü

        Returns:
            {"success": True, "table": str, "updated_id": int, "changes": dict}
        """
        db = self._session()
        try:
            _check_restricted(table)  # RestrictedTableError → except bloğunda yakalanır

            model_cls = _get_model_class(table)
            if model_cls is None:
                return {
                    "success": False,
                    "error": f"'{table}' tablosu bulunamadı veya erişilemiyor.",
                }

            # Kaydı ORM üzerinden çek (parametreli — SQL injection güvenli)
            row = db.query(model_cls).where(model_cls.id == id).first()
            if row is None:
                return {"success": False, "error": f"'{table}' tablosunda id={id} kaydı bulunamadı."}

            valid_cols = {c.key for c in sa_inspect(model_cls).mapper.columns}
            protected_cols = {"id", "created_at"}
            changes: dict[str, Any] = {}

            for col, new_val in values.items():
                if col in protected_cols:
                    continue
                if col not in valid_cols:
                    continue
                setattr(row, col, new_val)
                changes[col] = new_val

            db.commit()
            db.refresh(row)

            logger.info(
                "db_update",
                extra={"table": table, "id": id, "changes": list(changes.keys())},
            )
            return {
                "success": True,
                "table": table,
                "updated_id": id,
                "changes": changes,
                "data": _row_to_dict(row),
            }
        except (RestrictedTableError, ValueError) as exc:
            db.rollback()
            logger.warning(f"db_update reddedildi: {exc}", extra={"table": table})
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            db.rollback()
            logger.error(f"db_update hatası: {exc}", extra={"table": table})
            return {"success": False, "error": str(exc)}
        finally:
            db.close()

    def db_delete(self, table: str, id: int) -> dict[str, Any]:
        """
        ID ile kayıt siler.

        Bu işlem onay gerektirir (tool_executor.py tarafından kontrol edilir).
        RESTRICTED_TABLES reddedilir.
        Silme geri alınamaz.

        Args:
            table: Silinecek kaydın bulunduğu tablo
            id   : Silinecek kaydın primary key değeri

        Returns:
            {"success": True, "table": str, "deleted_id": int}
        """
        db = self._session()
        try:
            _check_restricted(table)  # RestrictedTableError → except bloğunda yakalanır

            model_cls = _get_model_class(table)
            if model_cls is None:
                return {
                    "success": False,
                    "error": f"'{table}' tablosu bulunamadı veya erişilemiyor.",
                }

            # ORM üzerinden çek (parametreli — SQL injection güvenli)
            row = db.query(model_cls).where(model_cls.id == id).first()
            if row is None:
                return {"success": False, "error": f"'{table}' tablosunda id={id} kaydı bulunamadı."}

            db.delete(row)
            db.commit()

            logger.warning(
                "db_delete — kayıt silindi",
                extra={"table": table, "id": id},
            )
            return {
                "success": True,
                "table": table,
                "deleted_id": id,
            }
        except (RestrictedTableError, ValueError) as exc:
            db.rollback()
            logger.warning(f"db_delete reddedildi: {exc}", extra={"table": table})
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            db.rollback()
            logger.error(f"db_delete hatası: {exc}", extra={"table": table})
            return {"success": False, "error": str(exc)}
        finally:
            db.close()


# Modül genelinde kullanılan tekil server örneği
database_server = DatabaseServer()
