"""Tests for FastAPI routes — jobs, results endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


def _make_app():
    """Create a test FastAPI app with mocked DB and state."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from server.routes import jobs, results, security

    app = FastAPI()
    app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
    app.include_router(results.router, prefix="/api/results", tags=["results"])
    app.include_router(security.router, prefix="/api/security", tags=["security"])

    # Minimal state that routes expect
    mock_db = AsyncMock()
    mock_db.create_crawl = AsyncMock(return_value="test-crawl-id")
    mock_db.get_crawl_stats = AsyncMock(return_value=[])

    app.state.db = mock_db
    app.state.active_jobs = {}
    app.state.log_buffer = MagicMock()
    app.state.log_buffer.add = MagicMock()
    app.state.metrics = MagicMock()

    return app


@pytest.fixture
def client():
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ── POST /api/jobs/start ─────────────────────────────────────

def test_start_job_valid_url(client):
    with patch("server.routes.jobs.Crawler") as MockCrawler, \
         patch("server.routes.jobs.asyncio.create_task"):
        mock_crawler_instance = MagicMock()
        mock_crawler_instance.stats = {"pages_crawled": 0}
        MockCrawler.return_value = mock_crawler_instance

        resp = client.post("/api/jobs/start", json={
            "urls": ["https://example.com"],
            "depth": 2,
            "max_pages": 100,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert data["status"] == "running"


def test_start_job_max_pages_capped(client):
    """Requesting >50k pages is silently capped at 50k."""
    with patch("server.routes.jobs.Crawler") as MockCrawler, \
         patch("server.routes.jobs.asyncio.create_task"), \
         patch("server.routes.jobs.is_admin", return_value=True):
        mock_crawler_instance = MagicMock()
        mock_crawler_instance.stats = {"pages_crawled": 0}
        MockCrawler.return_value = mock_crawler_instance

        resp = client.post("/api/jobs/start", json={
            "urls": ["https://example.com"],
            "max_pages": 999_999,
        })
        assert resp.status_code == 200
        # Check that the Crawler was created with max_pages <= 50_000
        call_args = MockCrawler.call_args
        config = call_args[0][0]  # positional arg
        assert config.crawler.max_pages <= 50_000


def test_start_job_missing_url(client):
    resp = client.post("/api/jobs/start", json={"urls": []})
    # Empty urls list should still get a response (validation happens inside the crawler)
    # This tests Pydantic validation passes at least
    assert resp.status_code in (200, 422)


# ── GET /api/jobs ────────────────────────────────────────────

def test_list_jobs_empty(client):
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert "active" in data
    assert "recent" in data


# ── DELETE /api/jobs/{job_id} ────────────────────────────────

def test_stop_nonexistent_job(client):
    resp = client.delete("/api/jobs/nonexistent-job")
    assert resp.status_code == 404
