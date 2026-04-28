import logging
import os
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv

# Konfiguracja loggingu
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Wczytanie zmiennych środowiskowych
load_dotenv()

# Konstrukcja URL bazy danych
DATABASE_URL: str = (
    f"postgresql://{os.getenv('POSTGRES_USER', 'fanumfraud')}:{os.getenv('POSTGRES_PASSWORD', 'fanumfraud')}"
    f"@{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'fanumfraud')}"
)

# Tworzenie engine i SessionLocal
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Bazowa klasa dla wszystkich modeli SQLAlchemy."""

    pass


_LIGHTWEIGHT_MIGRATIONS: tuple[tuple[str, str, str], ...] = (
    ("companies", "nip_registry_status", "VARCHAR(32)"),
    ("companies", "nip_registry_name", "VARCHAR(512)"),
    ("companies", "nip_registry_vat_status", "VARCHAR(64)"),
    ("companies", "nip_registry_source", "VARCHAR(64)"),
    ("companies", "nip_registry_checked_at", "TIMESTAMP"),
    ("companies", "nip_registry_reason", "VARCHAR(512)"),
)


def _apply_lightweight_migrations() -> None:
    """Add columns introduced after initial schema, idempotently."""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    for table, column, ddl_type in _LIGHTWEIGHT_MIGRATIONS:
        if not inspector.has_table(table):
            continue
        existing = {col["name"] for col in inspector.get_columns(table)}
        if column in existing:
            continue
        with engine.begin() as conn:
            conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {ddl_type}'))
        logger.info("✓ Added column %s.%s", table, column)


def init_db() -> None:
    """
    Inicjalizacja bazy danych - tworzenie wszystkich tabel.
    W przypadku błędu połączenia loguje informację ale nie przerywa aplikacji.
    """
    try:
        # Import modeli - musi być tutaj żeby były zarejestrowane w Base.metadata
        import models  # noqa: F401

        logger.info("Tworzenie tabel w bazie danych...")
        Base.metadata.create_all(bind=engine)
        _apply_lightweight_migrations()
        logger.info("✓ Baza danych zainicjalizowana pomyślnie")

    except OperationalError as e:
        logger.error(
            f"✗ Błąd połączenia z bazą danych PostgreSQL: {e}. "
            "Aplikacja będzie działać bez bazy danych do czasu przywrócenia połączenia."
        )
    except Exception as e:
        logger.error(
            f"✗ Nieoczekiwany błąd podczas inicjalizacji bazy danych: {e}. "
            "Aplikacja będzie działać bez bazy danych do czasu przywrócenia połączenia."
        )


def get_db() -> Generator[Session, None, None]:
    """
    Generator dostarczający sesję bazy danych dla FastAPI dependency injection.

    Yields:
        Session: Sesja SQLAlchemy

    Example:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    """
    Sprawdza połączenie z bazą danych.

    Returns:
        bool: True jeśli połączenie OK, False w przeciwnym wypadku
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except OperationalError:
        logger.warning("✗ Nie można połączyć się z bazą danych")
        return False
    except Exception as e:
        logger.warning(f"✗ Błąd przy sprawdzaniu bazy danych: {e}")
        return False
