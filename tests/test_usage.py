"""Tests for webreaper/usage.py — both file-based and DB-based usage tracking."""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock

from webreaper.usage import (
    get_usage,
    add_pages,
    _current_month,
    _current_period_start,
    USAGE_FILE,
    WEBREAPER_DIR,
)


class TestFileBasedUsage:
    """Tests for the CLI/standalone file-based usage tracker."""

    def test_get_usage_no_file(self, tmp_path, monkeypatch):
        fake_file = tmp_path / "usage.json"
        monkeypatch.setattr("webreaper.usage.USAGE_FILE", fake_file)
        result = get_usage()
        assert result["pages_crawled"] == 0
        assert result["month"] == _current_month()

    def test_get_usage_current_month(self, tmp_path, monkeypatch):
        fake_file = tmp_path / "usage.json"
        data = {"month": _current_month(), "pages_crawled": 42}
        fake_file.write_text(json.dumps(data))
        monkeypatch.setattr("webreaper.usage.USAGE_FILE", fake_file)
        result = get_usage()
        assert result["pages_crawled"] == 42

    def test_get_usage_stale_month_resets(self, tmp_path, monkeypatch):
        fake_file = tmp_path / "usage.json"
        data = {"month": "1999-01", "pages_crawled": 9999}
        fake_file.write_text(json.dumps(data))
        monkeypatch.setattr("webreaper.usage.USAGE_FILE", fake_file)
        result = get_usage()
        assert result["pages_crawled"] == 0

    def test_add_pages(self, tmp_path, monkeypatch):
        fake_dir = tmp_path / ".webreaper"
        fake_file = fake_dir / "usage.json"
        monkeypatch.setattr("webreaper.usage.WEBREAPER_DIR", fake_dir)
        monkeypatch.setattr("webreaper.usage.USAGE_FILE", fake_file)
        add_pages(100)
        add_pages(50)
        result = json.loads(fake_file.read_text())
        assert result["pages_crawled"] == 150

    def test_add_pages_creates_dir(self, tmp_path, monkeypatch):
        fake_dir = tmp_path / "new_dir"
        fake_file = fake_dir / "usage.json"
        monkeypatch.setattr("webreaper.usage.WEBREAPER_DIR", fake_dir)
        monkeypatch.setattr("webreaper.usage.USAGE_FILE", fake_file)
        add_pages(10)
        assert fake_dir.exists()
        assert fake_file.exists()

    def test_get_usage_corrupt_json(self, tmp_path, monkeypatch):
        fake_file = tmp_path / "usage.json"
        fake_file.write_text("not json{{{")
        monkeypatch.setattr("webreaper.usage.USAGE_FILE", fake_file)
        result = get_usage()
        assert result["pages_crawled"] == 0


class TestCurrentPeriodStart:
    def test_returns_first_of_month(self):
        result = _current_period_start()
        assert result.day == 1
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0
        assert result.tzinfo == timezone.utc


class TestCheckPageBudget:
    @pytest.mark.asyncio
    async def test_unlimited_plan_never_blocks(self):
        from webreaper.usage import check_page_budget
        mock_db = AsyncMock()
        # agency plan has unlimited pages — should never raise
        await check_page_budget(mock_db, "user1", "agency", pages_requested=999999)

    @pytest.mark.asyncio
    async def test_over_limit_raises_429(self):
        from webreaper.usage import check_page_budget
        from fastapi import HTTPException

        mock_db = AsyncMock()
        # Mock get_usage_this_period to return near-limit usage
        with patch("webreaper.usage.get_usage_this_period", return_value=4999):
            with pytest.raises(HTTPException) as exc_info:
                await check_page_budget(mock_db, "user1", "starter", pages_requested=100)
            assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_under_limit_passes(self):
        from webreaper.usage import check_page_budget

        mock_db = AsyncMock()
        with patch("webreaper.usage.get_usage_this_period", return_value=0):
            await check_page_budget(mock_db, "user1", "starter", pages_requested=1)


class TestCheckScraperLimit:
    @pytest.mark.asyncio
    async def test_unlimited_plan_never_blocks(self):
        from webreaper.usage import check_scraper_limit
        mock_db = AsyncMock()
        await check_scraper_limit(mock_db, "user1", "agency")

    @pytest.mark.asyncio
    async def test_over_limit_raises_403(self):
        from webreaper.usage import check_scraper_limit
        from fastapi import HTTPException

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5  # at starter limit
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await check_scraper_limit(mock_db, "user1", "starter")
        assert exc_info.value.status_code == 403
