"""Tests for restart-safe crawl recovery helpers and resume route."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.routes import jobs


def _make_app(db):
    app = FastAPI()
    app.include_router(jobs.router, prefix='/api/jobs')
    app.state.db = db
    app.state.active_jobs = {}
    app.state.log_buffer = MagicMock()
    app.state.metrics = MagicMock()
    return app


def test_mark_running_crawls_interrupted(temp_db):
    cid = asyncio.run(temp_db.create_crawl('https://example.com'))
    count = asyncio.run(temp_db.mark_running_crawls_interrupted())
    assert count >= 1
    rows = asyncio.run(temp_db.get_crawl_stats())
    row = next(r for r in rows if str(r['id']) == cid)
    assert row['status'] == 'interrupted'


def test_resume_crawl_creates_new_job_from_previous_crawl(temp_db):
    asyncio.run(temp_db.create_crawl('https://example.com/seed'))
    rows = asyncio.run(temp_db.get_crawl_stats())
    original_id = str(rows[0]['id'])

    app = _make_app(temp_db)
    with TestClient(app, raise_server_exceptions=False) as client:
        with patch('server.routes.jobs.Crawler') as MockCrawler, patch('server.routes.jobs.asyncio.create_task'):
            inst = MagicMock()
            inst.stats = {'pages_crawled': 0}
            MockCrawler.return_value = inst
            resp = client.post(f'/api/jobs/resume/{original_id}', json={'depth': 2, 'concurrency': 3})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data['status'] == 'running'
        assert data['target_urls'] == ['https://example.com/seed']
