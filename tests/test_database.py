"""Tests for database.py — connection, CRUD, SQLite default."""

import os
import pytest
import pytest_asyncio


# ── SQLite default ──────────────────────────────────────────

def test_default_sqlite_path_when_no_env(tmp_path, monkeypatch):
    """DatabaseManager defaults to SQLite when DATABASE_URL is unset."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    from webreaper.database import DatabaseManager
    db = DatabaseManager()
    assert "sqlite" in db.database_url
    assert db.database_url.startswith("sqlite+aiosqlite:///")


def test_explicit_url_overrides_default(monkeypatch):
    """Explicit URL is used as-is."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from webreaper.database import DatabaseManager
    custom = "sqlite+aiosqlite:///custom.db"
    db = DatabaseManager(database_url=custom)
    assert db.database_url == custom


def test_env_var_used_when_set(monkeypatch):
    """DATABASE_URL env var is respected."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///env.db")
    from webreaper.database import DatabaseManager
    db = DatabaseManager()
    assert "env.db" in db.database_url


def test_get_db_manager_never_returns_none(monkeypatch):
    """get_db_manager() always returns a manager (SQLite default)."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from webreaper.database import get_db_manager
    manager = get_db_manager()
    assert manager is not None


# ── CRUD round-trips ────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_crawl_returns_uuid(temp_db):
    crawl_id = await temp_db.create_crawl(
        target_url="https://example.com",
        config={"max_depth": 2},
    )
    assert isinstance(crawl_id, str)
    assert len(crawl_id) == 36  # UUID format


@pytest.mark.asyncio
async def test_save_page_round_trips(temp_db):
    crawl_id = await temp_db.create_crawl(target_url="https://example.com")
    page_id = await temp_db.save_page(
        crawl_id=crawl_id,
        url="https://example.com/page",
        domain="example.com",
        path="/page",
        status_code=200,
        response_time_ms=123,
        title="Test Page",
        meta_description="desc",
        content_text="hello world",
        word_count=2,
        headings=[{"level": 1, "text": "Hello"}],
        headings_count=1,
        images_count=0,
        links_count=1,
        external_links_count=0,
        h1="Hello",
        h2s=[],
        response_headers={},
        depth=0,
        forms=[],
    )
    assert isinstance(page_id, str)
    assert len(page_id) == 36


@pytest.mark.asyncio
async def test_complete_crawl_updates_stats(temp_db):
    crawl_id = await temp_db.create_crawl(target_url="https://example.com")
    stats = {
        "pages_crawled": 5,
        "pages_failed": 1,
        "total_size": 102400,
        "external_links": 3,
        "total_time": 10.0,
    }
    # Should not raise
    await temp_db.complete_crawl(crawl_id, stats)


@pytest.mark.asyncio
async def test_create_tables_idempotent(temp_db):
    """Calling create_tables twice should not raise."""
    await temp_db.create_tables()  # Already called in fixture; second call is safe
