"""
db/database.py
--------------
SQLAlchemy engine ve session fabrikası.

Kullanım:
    from db.database import get_db, init_db

    # FastAPI dependency injection ile:
    @app.get("/example")
    def example(db: Session = Depends(get_db)):
        ...

    # Uygulama başlatılırken:
    init_db()
"""

from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from config import settings
from db.models import Base


def _get_engine():
    """
    Yapılandırmaya göre SQLAlchemy engine oluşturur.

    SQLite için özel ayarlar:
        - check_same_thread=False : FastAPI'nin çoklu thread ortamında gerekli
        - WAL modu               : Eşzamanlı okuma/yazma performansı için
        - Foreign key zorlama    : SQLite varsayılan olarak FK'yi kontrol etmez
    """
    connect_args = {}
    if settings.DATABASE_URL.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        settings.DATABASE_URL,
        connect_args=connect_args,
        echo=settings.DEBUG,  # DEBUG=True iken SQL sorgularını loglar
    )

    # SQLite'a özel pragma'lar
    if settings.DATABASE_URL.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def set_sqlite_pragmas(dbapi_connection, connection_record):  # type: ignore[unused-ignore]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


engine = _get_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def init_db() -> None:
    """
    Tüm tabloları oluşturur (yoksa).

    Üretim ortamında Alembic migration'ları kullanılmalıdır.
    Bu fonksiyon yalnızca geliştirme ve test ortamları içindir.
    """
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency injection için veritabanı session üreteci.

    Her HTTP isteği için yeni bir session açar, istek bitince kapatır.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    """
    Dependency injection dışındaki kullanımlar için (örn: seed, test) doğrudan session döner.
    Kullanıcı `with` bloğu veya manuel `.close()` ile kapatmaktan sorumludur.
    """
    return SessionLocal()
