"""Database configuration and session management for SQLite persistence."""

import os
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Configurable database path; default relative path avoids machine-specific absolute paths
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./network_monitoring.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency generator that yields an isolated database session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(target_engine=None) -> None:
    """Create all registered database tables and apply non-destructive column additions."""
    # Import models here to ensure they are registered with Base.metadata
    from app import models  # noqa: F401

    e = target_engine or engine
    Base.metadata.create_all(bind=e)

    # Lightweight idempotent schema upgrade for Phase 2 columns on existing devices table
    with e.connect() as conn:
        try:
            res = conn.execute(text("PRAGMA table_info(devices)")).fetchall()
            existing_cols = {row[1] for row in res}
            new_columns = [
                ("last_poll_at", "DATETIME"),
                ("last_poll_status", "VARCHAR(50)"),
                ("last_poll_error", "VARCHAR(255)"),
                ("reachability", "VARCHAR(50) DEFAULT 'configured'"),
                ("polling_enabled", "BOOLEAN DEFAULT 0"),
                ("polling_interval_seconds", "FLOAT DEFAULT 10.0"),
            ]
            for col_name, col_def in new_columns:
                if col_name not in existing_cols:
                    conn.execute(text(f"ALTER TABLE devices ADD COLUMN {col_name} {col_def}"))
            conn.commit()
        except Exception:
            pass
