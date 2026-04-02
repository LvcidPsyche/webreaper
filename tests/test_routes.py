"""Tests for FastAPI routes — jobs, results endpoints."""

import os
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
         patch("server.routes.jobs.asyncio.create_task") as mock_create_task:
        mock_crawler_instance = MagicMock()
        mock_crawler_instance.stats = {"pages_crawled": 0}
        MockCrawler.return_value = mock_crawler_instance
        mock_create_task.side_effect = lambda coro: coro.close()

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
         patch("server.routes.jobs.asyncio.create_task") as mock_create_task, \
         patch("server.routes.jobs.is_admin", return_value=True):
        mock_crawler_instance = MagicMock()
        mock_crawler_instance.stats = {"pages_crawled": 0}
        MockCrawler.return_value = mock_crawler_instance
        mock_create_task.side_effect = lambda coro: coro.close()

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
    assert resp.status_code == 422


def test_start_job_requires_license_when_enforcement_enabled(client):
    with patch.dict(os.environ, {"WEBREAPER_REQUIRE_LICENSE": "1"}, clear=False):
        resp = client.post("/api/jobs/start", json={
            "urls": ["https://example.com"],
            "max_pages": 1,
        })

    assert resp.status_code == 402
    assert "License limit" in resp.json()["detail"]


# ── GET /api/jobs ────────────────────────────────────────────

def test_list_jobs_empty(client):
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


# ── DELETE /api/jobs/{job_id} ────────────────────────────────

def test_stop_nonexistent_job(client):
    resp = client.delete("/api/jobs/nonexistent-job")
    assert resp.status_code == 404


def test_jobs_metrics_callback_updates_metrics_service():
    from server.routes.jobs import _make_metrics_callback
    from server.services.metrics import MetricsService

    metrics = MetricsService()
    active_jobs = {"a": object(), "b": object()}
    cb = _make_metrics_callback(metrics, active_jobs)

    cb({
        "page_delta": 2,
        "fail_delta": 1,
        "bytes_delta": 128,
        "status_code": 200,
        "queue_size": 7,
        "requests_per_second": 4.5,
    })

    snap = metrics.snapshot()
    assert snap["pages_crawled"] == 2
    assert snap["error_rate"] > 0
    assert snap["active_jobs"] == 2
    assert snap["queue_depth"] == 7
    assert snap["requests_per_second"] == 4.5
    assert snap["status_codes"]["2xx"] == 1


def test_list_jobs_uses_target_url_from_db_rows(client):
    client.app.state.db.get_crawl_stats = AsyncMock(return_value=[
        {
            "id": "crawl-1",
            "target_url": "https://example.com",
            "status": "completed",
            "pages_crawled": 10,
            "started_at": "2026-02-25T00:00:00Z",
            "completed_at": "2026-02-25T00:01:00Z",
        }
    ])
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert any(row["url"] == "https://example.com" for row in data)


def test_security_scan_auto_attack_invokes_active_scan(client):
    called = {"active": False}
    client.app.state.db = None

    class DummyFetcher:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def fetch(self, url):
            return 200, {"Content-Type": "text/html"}, "<html><body><form method='POST'><input name='q'></form></body></html>"

    class DummyDeepExtractor:
        def extract(self, **kwargs):
            return type("Deep", (), {"forms": [{"method": "POST", "fields": [{"name": "q", "type": "text"}]}]})()

    class DummyScanner:
        def __init__(self, auto_attack=False):
            self.auto_attack = auto_attack

        def scan(self, url, headers, body, forms):
            return [{"type": "Passive", "severity": "Low", "url": url}]

        async def active_scan(self, url, forms, session, aggressive=False):
            called["active"] = aggressive is True
            return [{"type": "SQL Injection", "severity": "Critical", "url": url}]

        def fingerprint_tech(self, url, headers, body):
            return {"Framework": ["Next.js"]}

    with patch("webreaper.fetcher.StealthFetcher", DummyFetcher), \
         patch("webreaper.deep_extractor.DeepExtractor", DummyDeepExtractor), \
         patch("webreaper.modules.security.SecurityScanner", DummyScanner):
        resp = client.post("/api/security/scan", json={"url": "https://example.com/test", "auto_attack": True})

    assert resp.status_code == 200
    data = resp.json()
    assert called["active"] is True
    assert data["findings_count"] == 2
