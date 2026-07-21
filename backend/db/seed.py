"""
db/seed.py
----------
Geliştirme ve demo için örnek veri yükleyici.

Çalıştırmak için:
    cd backend
    python -m db.seed

Yüklenenler:
    - 3 kullanıcı (employee, hr, admin rolleri)
    - 5 çalışan
    - İzin bakiyeleri (her çalışan için 2026)
    - Örnek izin talepleri
    - Rol × tool permission matrisi
    - Demo sandbox dosyaları
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Windows cp1254 locale sorunu için stdout'u UTF-8'e zorla
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Backend kök dizinini sys.path'e ekle (modül import'ları için)
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from db.database import get_db_session, init_db
from db.models import Employee, LeaveBalance, LeaveRequest, Permission, User

# ─────────────────────────────────────────────────────────────────────────────
# Permission matrisi — rol × tool
# ─────────────────────────────────────────────────────────────────────────────
PERMISSION_MATRIX: list[dict] = [
    # ── dosya ────────────────────────────────────────────────────────────────
    {"role": "employee", "tool_name": "file_read",   "allowed": True,  "requires_approval": False},
    {"role": "employee", "tool_name": "file_write",  "allowed": True,  "requires_approval": True},
    {"role": "employee", "tool_name": "file_delete", "allowed": False, "requires_approval": False},
    {"role": "employee", "tool_name": "file_list",   "allowed": True,  "requires_approval": False},
    {"role": "employee", "tool_name": "file_move",   "allowed": True,  "requires_approval": True},

    {"role": "hr",       "tool_name": "file_read",   "allowed": True,  "requires_approval": False},
    {"role": "hr",       "tool_name": "file_write",  "allowed": True,  "requires_approval": True},
    {"role": "hr",       "tool_name": "file_delete", "allowed": True,  "requires_approval": True},
    {"role": "hr",       "tool_name": "file_list",   "allowed": True,  "requires_approval": False},
    {"role": "hr",       "tool_name": "file_move",   "allowed": True,  "requires_approval": True},

    {"role": "admin",    "tool_name": "file_read",   "allowed": True,  "requires_approval": False},
    {"role": "admin",    "tool_name": "file_write",  "allowed": True,  "requires_approval": False},
    {"role": "admin",    "tool_name": "file_delete", "allowed": True,  "requires_approval": True},
    {"role": "admin",    "tool_name": "file_list",   "allowed": True,  "requires_approval": False},
    {"role": "admin",    "tool_name": "file_move",   "allowed": True,  "requires_approval": False},

    # ── veritabani ────────────────────────────────────────────────────────────
    {"role": "employee", "tool_name": "db_list_tables",   "allowed": False, "requires_approval": False},
    {"role": "employee", "tool_name": "db_get_schema",    "allowed": False, "requires_approval": False},
    {"role": "employee", "tool_name": "db_query",         "allowed": False, "requires_approval": False},
    {"role": "employee", "tool_name": "db_insert",        "allowed": False, "requires_approval": False},
    {"role": "employee", "tool_name": "db_update",        "allowed": False, "requires_approval": False},
    {"role": "employee", "tool_name": "db_delete",        "allowed": False, "requires_approval": False},

    {"role": "hr",       "tool_name": "db_list_tables",   "allowed": True,  "requires_approval": False},
    {"role": "hr",       "tool_name": "db_get_schema",    "allowed": True,  "requires_approval": False},
    {"role": "hr",       "tool_name": "db_query",         "allowed": True,  "requires_approval": False},
    {"role": "hr",       "tool_name": "db_insert",        "allowed": True,  "requires_approval": True},
    {"role": "hr",       "tool_name": "db_update",        "allowed": True,  "requires_approval": True},
    {"role": "hr",       "tool_name": "db_delete",        "allowed": False, "requires_approval": False},

    {"role": "admin",    "tool_name": "db_list_tables",   "allowed": True,  "requires_approval": False},
    {"role": "admin",    "tool_name": "db_get_schema",    "allowed": True,  "requires_approval": False},
    {"role": "admin",    "tool_name": "db_query",         "allowed": True,  "requires_approval": False},
    {"role": "admin",    "tool_name": "db_insert",        "allowed": True,  "requires_approval": False},
    {"role": "admin",    "tool_name": "db_update",        "allowed": True,  "requires_approval": True},
    {"role": "admin",    "tool_name": "db_delete",        "allowed": True,  "requires_approval": True},

    # ── HR araçları ──────────────────────────────────────────────────────────
    {"role": "employee", "tool_name": "get_employee_leave_balance", "allowed": True,  "requires_approval": False},
    {"role": "employee", "tool_name": "get_employees_on_leave",     "allowed": True,  "requires_approval": False},
    {"role": "employee", "tool_name": "request_leave",              "allowed": True,  "requires_approval": True},
    {"role": "employee", "tool_name": "approve_leave",              "allowed": False, "requires_approval": False},

    {"role": "hr",       "tool_name": "get_employee_leave_balance", "allowed": True,  "requires_approval": False},
    {"role": "hr",       "tool_name": "get_employees_on_leave",     "allowed": True,  "requires_approval": False},
    {"role": "hr",       "tool_name": "request_leave",              "allowed": True,  "requires_approval": True},
    {"role": "hr",       "tool_name": "approve_leave",              "allowed": True,  "requires_approval": True},

    {"role": "admin",    "tool_name": "get_employee_leave_balance", "allowed": True,  "requires_approval": False},
    {"role": "admin",    "tool_name": "get_employees_on_leave",     "allowed": True,  "requires_approval": False},
    {"role": "admin",    "tool_name": "request_leave",              "allowed": True,  "requires_approval": True},
    {"role": "admin",    "tool_name": "approve_leave",              "allowed": True,  "requires_approval": True},

    # ── kod_git ───────────────────────────────────────────────────────────────
    {"role": "employee", "tool_name": "code_run",                "allowed": True,  "requires_approval": False},
    {"role": "employee", "tool_name": "code_lint",               "allowed": True,  "requires_approval": False},
    {"role": "employee", "tool_name": "git_status",              "allowed": True,  "requires_approval": False},
    {"role": "employee", "tool_name": "git_diff_preview",        "allowed": True,  "requires_approval": False},
    {"role": "employee", "tool_name": "git_create_branch",       "allowed": True,  "requires_approval": False},
    {"role": "employee", "tool_name": "git_commit_and_push",     "allowed": True,  "requires_approval": True},
    {"role": "employee", "tool_name": "github_create_pull_request", "allowed": True, "requires_approval": True},

    {"role": "hr",       "tool_name": "code_run",                "allowed": False, "requires_approval": False},
    {"role": "hr",       "tool_name": "code_lint",               "allowed": False, "requires_approval": False},
    {"role": "hr",       "tool_name": "git_status",              "allowed": False, "requires_approval": False},
    {"role": "hr",       "tool_name": "git_diff_preview",        "allowed": False, "requires_approval": False},
    {"role": "hr",       "tool_name": "git_create_branch",       "allowed": False, "requires_approval": False},
    {"role": "hr",       "tool_name": "git_commit_and_push",     "allowed": False, "requires_approval": False},
    {"role": "hr",       "tool_name": "github_create_pull_request", "allowed": False, "requires_approval": False},

    {"role": "admin",    "tool_name": "code_run",                "allowed": True,  "requires_approval": False},
    {"role": "admin",    "tool_name": "code_lint",               "allowed": True,  "requires_approval": False},
    {"role": "admin",    "tool_name": "git_status",              "allowed": True,  "requires_approval": False},
    {"role": "admin",    "tool_name": "git_diff_preview",        "allowed": True,  "requires_approval": False},
    {"role": "admin",    "tool_name": "git_create_branch",       "allowed": True,  "requires_approval": False},
    {"role": "admin",    "tool_name": "git_commit_and_push",     "allowed": True,  "requires_approval": True},
    {"role": "admin",    "tool_name": "github_create_pull_request", "allowed": True, "requires_approval": True},

    # ── mail_takvim ───────────────────────────────────────────────────────────
    {"role": "employee", "tool_name": "mail_read_inbox",      "allowed": True,  "requires_approval": False},
    {"role": "employee", "tool_name": "mail_send",            "allowed": True,  "requires_approval": True},
    {"role": "employee", "tool_name": "mail_extract_meeting", "allowed": True,  "requires_approval": False},
    {"role": "employee", "tool_name": "calendar_list_events", "allowed": True,  "requires_approval": False},
    {"role": "employee", "tool_name": "calendar_add_event",   "allowed": True,  "requires_approval": True},
    {"role": "employee", "tool_name": "calendar_delete_event","allowed": True,  "requires_approval": True},

    {"role": "hr",       "tool_name": "mail_read_inbox",      "allowed": True,  "requires_approval": False},
    {"role": "hr",       "tool_name": "mail_send",            "allowed": True,  "requires_approval": True},
    {"role": "hr",       "tool_name": "mail_extract_meeting", "allowed": True,  "requires_approval": False},
    {"role": "hr",       "tool_name": "calendar_list_events", "allowed": True,  "requires_approval": False},
    {"role": "hr",       "tool_name": "calendar_add_event",   "allowed": True,  "requires_approval": True},
    {"role": "hr",       "tool_name": "calendar_delete_event","allowed": True,  "requires_approval": True},

    {"role": "admin",    "tool_name": "mail_read_inbox",      "allowed": True,  "requires_approval": False},
    {"role": "admin",    "tool_name": "mail_send",            "allowed": True,  "requires_approval": True},
    {"role": "admin",    "tool_name": "mail_extract_meeting", "allowed": True,  "requires_approval": False},
    {"role": "admin",    "tool_name": "calendar_list_events", "allowed": True,  "requires_approval": False},
    {"role": "admin",    "tool_name": "calendar_add_event",   "allowed": True,  "requires_approval": False},
    {"role": "admin",    "tool_name": "calendar_delete_event","allowed": True,  "requires_approval": True},

    # ── uygulama ─────────────────────────────────────────────────────────────
    {"role": "employee", "tool_name": "app_open",         "allowed": True,  "requires_approval": False},
    {"role": "employee", "tool_name": "app_close",        "allowed": True,  "requires_approval": False},
    {"role": "employee", "tool_name": "app_list_running", "allowed": True,  "requires_approval": False},

    {"role": "hr",       "tool_name": "app_open",         "allowed": True,  "requires_approval": False},
    {"role": "hr",       "tool_name": "app_close",        "allowed": True,  "requires_approval": False},
    {"role": "hr",       "tool_name": "app_list_running", "allowed": True,  "requires_approval": False},

    {"role": "admin",    "tool_name": "app_open",         "allowed": True,  "requires_approval": False},
    {"role": "admin",    "tool_name": "app_close",        "allowed": True,  "requires_approval": False},
    {"role": "admin",    "tool_name": "app_list_running", "allowed": True,  "requires_approval": False},
]


def seed_database() -> None:
    """Demo verilerini veritabanına yükler (idempotent: tekrar çalıştırılabilir)."""
    init_db()
    db = get_db_session()

    try:
        # ── Kullanıcılar ─────────────────────────────────────────────────────
        existing_users = db.query(User).count()
        if existing_users == 0:
            users = [
                User(name="Ahmet Yılmaz",  email="ahmet@sirket.com",   role="employee"),
                User(name="Ayşe Kaya",     email="ayse@sirket.com",    role="hr"),
                User(name="Admin User",    email="admin@sirket.com",   role="admin"),
            ]
            db.add_all(users)
            db.flush()
            print(f"✓ {len(users)} kullanıcı eklendi")
        else:
            print(f"⊙ Kullanıcılar zaten mevcut ({existing_users} kayıt), atlanıyor")

        # ── Çalışanlar ───────────────────────────────────────────────────────
        existing_employees = db.query(Employee).count()
        if existing_employees == 0:
            employees = [
                Employee(name="Ahmet Yılmaz",   department="Mühendislik",    email="ahmet@sirket.com"),
                Employee(name="Zeynep Arslan",  department="Mühendislik",    email="zeynep@sirket.com"),
                Employee(name="Mehmet Demir",   department="Pazarlama",       email="mehmet@sirket.com"),
                Employee(name="Elif Şahin",     department="İnsan Kaynakları",email="elif@sirket.com"),
                Employee(name="Can Öztürk",     department="Finans",          email="can@sirket.com"),
            ]
            db.add_all(employees)
            db.flush()
            print(f"✓ {len(employees)} çalışan eklendi")

            # ── İzin Bakiyeleri (2026) ───────────────────────────────────────
            balances = []
            for emp in employees:
                balances.append(
                    LeaveBalance(
                        employee_id=emp.id,
                        year=2026,
                        total_days=20,
                        used_days=0,
                        remaining_days=20,
                    )
                )
            db.add_all(balances)
            print(f"✓ {len(balances)} izin bakiyesi eklendi")

            # ── Örnek İzin Talepleri ─────────────────────────────────────────
            ahmet = employees[0]
            zeynep = employees[1]
            leave_requests = [
                LeaveRequest(
                    employee_id=ahmet.id,
                    leave_type="annual",
                    start_date="2026-08-01",
                    end_date="2026-08-05",
                    status="approved",
                    approved_by="Ayşe Kaya",
                    notes="Yaz tatili",
                ),
                LeaveRequest(
                    employee_id=zeynep.id,
                    leave_type="sick",
                    start_date="2026-07-20",
                    end_date="2026-07-21",
                    status="pending",
                    notes="Doktor raporu eklenecek",
                ),
            ]
            db.add_all(leave_requests)
            print(f"✓ {len(leave_requests)} izin talebi eklendi")
        else:
            print(f"⊙ Çalışanlar zaten mevcut ({existing_employees} kayıt), atlanıyor")

        # ── Permission Matrisi ───────────────────────────────────────────────
        existing_perms = db.query(Permission).count()
        if existing_perms == 0:
            permissions = [Permission(**p) for p in PERMISSION_MATRIX]
            db.add_all(permissions)
            print(f"✓ {len(permissions)} izin kuralı eklendi")
        else:
            print(f"⊙ İzin kuralları zaten mevcut ({existing_perms} kayıt), atlanıyor")

        db.commit()

        # ── Demo Sandbox Dosyaları ────────────────────────────────────────────
        sandbox = settings.SANDBOX_ROOT
        sandbox.mkdir(parents=True, exist_ok=True)

        readme = sandbox / "README.md"
        if not readme.exists():
            readme.write_text(
                "# Asistan Demo Sandbox\n\n"
                "Bu dizin dosya sistemi tool'larının test edeceği güvenli alan.\n"
                "Tüm dosya işlemleri yalnızca bu dizin altında çalışır.\n\n"
                "## Örnek Dosyalar\n"
                "- `notlar.txt` — düzenlenebilir metin\n"
                "- `veri.json` — yapılandırılmış veri örneği\n",
                encoding="utf-8",
            )
            print(f"✓ {readme} oluşturuldu")

        notes = sandbox / "notlar.txt"
        if not notes.exists():
            notes.write_text(
                "Bu bir demo not dosyasıdır.\n"
                "Asistan bu dosyayı okuyabilir ve düzenleyebilir (onay ile).\n",
                encoding="utf-8",
            )
            print(f"✓ {notes} oluşturuldu")

        data_file = sandbox / "veri.json"
        if not data_file.exists():
            data_file.write_text(
                json.dumps(
                    {"proje": "local-agent", "faz": 1, "durum": "geliştirme"},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(f"✓ {data_file} oluşturuldu")

        print("\n✅ Seed tamamlandı.")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Seed hatası: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
