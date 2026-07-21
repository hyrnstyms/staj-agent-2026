"""
tests/conftest.py
-----------------
Pytest fikstürleri — tüm testler tarafından paylaşılır.
"""

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Backend kök dizinini path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.models import Base, Permission, User
from db.seed import PERMISSION_MATRIX


@pytest.fixture(scope="session")
def test_engine():
    """Her test oturumu için in-memory SQLite engine."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db(test_engine):
    """Her test için temiz DB session'ı."""
    TestSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    session = TestSession()

    # Temiz başla
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()

    # Temel veri ekle
    users = [
        User(id=1, name="Çalışan",  email="employee@test.com", role="employee", is_active=True),
        User(id=2, name="İK",       email="hr@test.com",       role="hr",       is_active=True),
        User(id=3, name="Admin",    email="admin@test.com",    role="admin",    is_active=True),
        User(id=4, name="Pasif",    email="inactive@test.com", role="employee", is_active=False),
    ]
    session.add_all(users)

    permissions = [Permission(**p) for p in PERMISSION_MATRIX]
    session.add_all(permissions)
    session.commit()

    yield session
    session.close()


@pytest.fixture
def sandbox_dir(tmp_path):
    """Her test için geçici sandbox dizini."""
    return tmp_path / "sandbox"
