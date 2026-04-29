from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path
import sqlite3

SQLALCHEMY_DATABASE_URL = "sqlite:///./the_bridge.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def _sqlite_db_path() -> Path:
    """
    Resolve the SQLite path used by SQLALCHEMY_DATABASE_URL.
    Keep this conservative: current project uses a relative ./the_bridge.db.
    """
    return (Path(__file__).resolve().parent / "the_bridge.db")

def migrate_sqlite_schema() -> None:
    """
    Lightweight migration for existing local SQLite databases.

    SQLAlchemy's create_all() does not add columns to existing tables, so older
    databases can be missing fields newer code depends on.
    """
    db_path = _sqlite_db_path()
    if not db_path.exists():
        return

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()

        def has_column(table: str, column: str) -> bool:
            cols = cur.execute(f"PRAGMA table_info({table})").fetchall()
            return any(row[1] == column for row in cols)

        # users.password_hash (required for admin/freelancer login)
        if not has_column("users", "password_hash"):
            cur.execute("ALTER TABLE users ADD COLUMN password_hash VARCHAR")

        # leads.created_at (required for finance monthly aggregation)
        if not has_column("leads", "created_at"):
            cur.execute("ALTER TABLE leads ADD COLUMN created_at DATETIME")

        conn.commit()
    finally:
        conn.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
