"""Database migration helpers (Alembic + safe startup checks)."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

from sqlalchemy import inspect, text

from .logging_config import get_logger

logger = get_logger("webreaper.migrations")


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _alembic_ini_path() -> Path:
    return _project_root() / "alembic.ini"


def _to_sync_url(async_url: str) -> str:
    if async_url.startswith("sqlite+aiosqlite"):
        return async_url.replace("sqlite+aiosqlite", "sqlite", 1)
    if async_url.startswith("postgresql+asyncpg"):
        # Alembic runs sync migrations in-process.
        return async_url.replace("postgresql+asyncpg", "postgresql+psycopg2", 1)
    return async_url


def _has_tables(sync_engine) -> bool:
    inspector = inspect(sync_engine)
    return len(inspector.get_table_names()) > 0


def _has_alembic_version_table(sync_engine) -> bool:
    inspector = inspect(sync_engine)
    return "alembic_version" in inspector.get_table_names()


def _current_alembic_revision(sync_engine) -> Optional[str]:
    if not _has_alembic_version_table(sync_engine):
        return None
    with sync_engine.connect() as conn:
        try:
            row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
            return row[0] if row else None
        except Exception:
            return None


def _run_alembic_upgrade(sync_url: str) -> None:
    from alembic import command
    from alembic.config import Config

    ini_path = _alembic_ini_path()
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(cfg, "head")


async def ensure_database_schema(db_manager) -> None:
    """Ensure database schema is ready using migrations when available.

    Behavior:
    - If Alembic is installed + config exists: run `upgrade head`.
    - If Alembic is unavailable and DB is empty: legacy bootstrap with create_tables().
    - If Alembic is unavailable and DB has tables: fail with actionable guidance.
    """
    if not getattr(db_manager, "engine", None):
        await db_manager.init_async()
    if not getattr(db_manager, "sync_engine", None):
        db_manager.init_sync()

    sync_engine = db_manager.sync_engine
    sync_url = _to_sync_url(db_manager.database_url)
    has_tables = _has_tables(sync_engine)

    alembic_ini = _alembic_ini_path()
    alembic_disabled = os.getenv("WEBREAPER_DISABLE_MIGRATIONS", "").lower() in {"1", "true", "yes"}

    try:
        from alembic import command  # noqa: F401
        from alembic.config import Config  # noqa: F401
        alembic_available = True
    except Exception:
        alembic_available = False

    if alembic_disabled:
        logger.warning("Migrations explicitly disabled by WEBREAPER_DISABLE_MIGRATIONS")
        if not has_tables:
            await db_manager.create_tables()
        return

    if not alembic_available or not alembic_ini.exists():
        if has_tables:
            raise RuntimeError(
                "Database has existing tables but Alembic migrations are unavailable. "
                "Install 'alembic' and run migrations (or set WEBREAPER_DISABLE_MIGRATIONS=1 for legacy mode)."
            )
        logger.warning("Alembic unavailable; bootstrapping empty DB with create_tables() (legacy mode)")
        await db_manager.create_tables()
        return

    logger.info(
        "Running database migrations (current revision=%s)",
        _current_alembic_revision(sync_engine) or "none",
    )
    try:
        await asyncio.to_thread(_run_alembic_upgrade, sync_url)
    except Exception as exc:
        raise RuntimeError(
            f"Database migration failed: {exc}. Back up your DB and inspect Alembic revisions before retrying."
        ) from exc
