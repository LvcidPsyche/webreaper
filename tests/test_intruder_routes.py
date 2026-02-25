"""Tests for Intruder APIs (MVP)."""

from __future__ import annotations

import asyncio

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.routes import intruder
from webreaper.intruder.service import IntruderService


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, method, url, headers=None, content=None):
        text = ''
        status = 200
        if 'admin' in url or (isinstance(content, str) and 'admin' in content):
            text = 'welcome admin panel'
            status = 200
        elif 'slow' in url or (isinstance(content, str) and 'slow' in content):
            text = 'slow result'
            status = 202
        else:
            text = 'no match'
            status = 404
        req = httpx.Request(method, url, headers=headers or {}, content=(content.encode() if isinstance(content, str) else content))
        return httpx.Response(status, request=req, headers={'content-type': 'text/plain'}, content=text.encode())


def _make_app(db):
    app = FastAPI()
    app.include_router(intruder.router, prefix='/api/intruder')
    app.state.db = db
    app.state.intruder_service = IntruderService()
    return app


def test_intruder_create_start_results_and_stop_on_match(temp_db, monkeypatch):
    monkeypatch.setattr('webreaper.intruder.service.httpx.AsyncClient', _FakeAsyncClient)

    sleep_calls: list[float] = []

    async def fake_sleep(delay: float):
        sleep_calls.append(delay)
        return None

    monkeypatch.setattr('webreaper.intruder.service.asyncio.sleep', fake_sleep)

    app = _make_app(temp_db)
    with TestClient(app, raise_server_exceptions=False) as client:
        create = client.post('/api/intruder/jobs', json={
            'name': 'Fuzz user id',
            'method': 'GET',
            'url': 'https://example.com/search?q=§FUZZ§',
            'payloads': ['guest', 'admin', 'slow'],
            'rate_limit_rps': 5,
            'match_substring': 'admin panel',
            'stop_on_first_match': True,
        })
        assert create.status_code == 200, create.text
        job = create.json()
        job_id = job['id']
        assert job['total_attempts'] == 3
        assert job['status'] == 'queued'

        start = client.post(f'/api/intruder/jobs/{job_id}/start', json={'wait': True})
        assert start.status_code == 200, start.text
        started = start.json()
        assert started['status'] == 'completed'
        assert started['completed_attempts'] == 2  # stops after admin match
        assert started['matched_attempts'] == 1

        results = client.get(f'/api/intruder/jobs/{job_id}/results')
        assert results.status_code == 200
        data = results.json()
        assert data['total'] == 2
        assert data['results'][0]['attempt_index'] == 1
        assert data['results'][1]['matched'] in (True, 1)
        assert data['results'][1]['transaction']['source'] == 'intruder'
        # one delay inserted between first and second attempts
        assert sleep_calls and abs(sleep_calls[0] - 0.2) < 1e-6


def test_send_to_intruder_from_transaction_and_cancel(temp_db):
    tx_id = asyncio.run(temp_db.save_http_transaction({
        'workspace_id': None,
        'source': 'proxy',
        'method': 'POST',
        'scheme': 'https',
        'host': 'example.com',
        'path': '/login',
        'query': None,
        'url': 'https://example.com/login',
        'request_headers': {'content-type': 'application/x-www-form-urlencoded'},
        'request_body': 'username=alice&password=secret',
        'response_status': 200,
        'response_headers': {'content-type': 'text/html'},
        'response_body': 'ok',
        'duration_ms': 10,
        'tags': ['proxy'],
        'intercept_state': 'none',
        'truncated': False,
    }))

    app = _make_app(temp_db)
    with TestClient(app, raise_server_exceptions=False) as client:
        seed = client.post('/api/intruder/send-to-intruder', json={
            'transaction_id': tx_id,
            'payloads': ['admin', 'bob'],
            'marker_target': 'body',
        })
        assert seed.status_code == 200, seed.text
        job = seed.json()
        assert '§FUZZ§' in (job['body'] or '')

        cancel = client.post(f"/api/intruder/jobs/{job['id']}/cancel")
        assert cancel.status_code == 200
        body = cancel.json()
        assert body['status'] == 'cancelled'
        assert body['cancelled'] in (True, 1)


def test_intruder_rejects_missing_markers(temp_db):
    app = _make_app(temp_db)
    with TestClient(app, raise_server_exceptions=False) as client:
        res = client.post('/api/intruder/jobs', json={
            'url': 'https://example.com/no-markers',
            'payloads': ['x'],
        })
        assert res.status_code == 400
        assert 'marker' in res.text.lower()


def test_intruder_async_start_then_cancel(temp_db, monkeypatch):
    async def fake_run_job(self, db, job_id: str):  # pragma: no cover - test helper
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            return

    monkeypatch.setattr('webreaper.intruder.service.IntruderService._run_job', fake_run_job)

    app = _make_app(temp_db)
    with TestClient(app, raise_server_exceptions=False) as client:
        create = client.post('/api/intruder/jobs', json={
            'url': 'https://example.com/q?x=§FUZZ§',
            'payloads': ['a', 'b', 'c', 'd', 'e'],
            'rate_limit_rps': 1,
        })
        assert create.status_code == 200
        job_id = create.json()['id']

        start = client.post(f'/api/intruder/jobs/{job_id}/start', json={'wait': False})
        assert start.status_code == 200

        cancel = client.post(f'/api/intruder/jobs/{job_id}/cancel')
        assert cancel.status_code == 200
        body = cancel.json()
        assert body['cancelled'] in (True, 1)
        assert body['status'] == 'cancelled'
