"""Tests for migration-aware startup helper behavior."""

import pytest
from sqlalchemy import inspect

from webreaper.database import DatabaseManager
from webreaper.migrations import ensure_database_schema


@pytest.mark.asyncio
async def test_ensure_database_schema_bootstraps_empty_db_legacy_mode(tmp_path, monkeypatch):
    """With WEBREAPER_DISABLE_MIGRATIONS=1, empty DB gets bootstrapped via create_tables()."""
    monkeypatch.setenv("WEBREAPER_DISABLE_MIGRATIONS", "1")
    db_path = tmp_path / "empty.db"
    db = DatabaseManager(f"sqlite+aiosqlite:///{db_path}")
    await db.init_async()
    try:
        await ensure_database_schema(db)
        db.init_sync()
        assert "crawls" in set(inspect(db.sync_engine).get_table_names())
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_ensure_database_schema_fails_on_existing_db_without_alembic(tmp_path, monkeypatch):
    """With alembic unavailable and tables present, should raise with guidance."""
    # Hide alembic so the code falls into the "alembic unavailable" branch
    import webreaper.migrations as mig
    monkeypatch.setattr(mig, "_alembic_ini_path", lambda: tmp_path / "nonexistent.ini")

    db_path = tmp_path / "existing.db"
    db = DatabaseManager(f"sqlite+aiosqlite:///{db_path}")
    await db.init_async()
    try:
        await db.create_tables()
        with pytest.raises(RuntimeError, match="Alembic migrations are unavailable"):
            await ensure_database_schema(db)
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_legacy_mode_skips_existing_tables(tmp_path, monkeypatch):
    """With WEBREAPER_DISABLE_MIGRATIONS=1, existing tables are left alone."""
    monkeypatch.setenv("WEBREAPER_DISABLE_MIGRATIONS", "1")
    db_path = tmp_path / "has_tables.db"
    db = DatabaseManager(f"sqlite+aiosqlite:///{db_path}")
    await db.init_async()
    try:
        await db.create_tables()
        db.init_sync()
        tables_before = set(inspect(db.sync_engine).get_table_names())
        await ensure_database_schema(db)
        tables_after = set(inspect(db.sync_engine).get_table_names())
        assert tables_before == tables_after
    finally:
        await db.close()
