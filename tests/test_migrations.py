"""Tests for migration-aware startup helper behavior."""

import pytest
from sqlalchemy import inspect

from webreaper.database import DatabaseManager
from webreaper.migrations import ensure_database_schema


@pytest.mark.asyncio
async def test_ensure_database_schema_bootstraps_empty_db_without_alembic(tmp_path, monkeypatch):
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
async def test_ensure_database_schema_fails_on_existing_db_without_alembic(tmp_path):
    db_path = tmp_path / "existing.db"
    db = DatabaseManager(f"sqlite+aiosqlite:///{db_path}")
    await db.init_async()
    try:
        await db.create_tables()
        with pytest.raises(RuntimeError, match="Alembic migrations are unavailable"):
            await ensure_database_schema(db)
    finally:
        await db.close()
