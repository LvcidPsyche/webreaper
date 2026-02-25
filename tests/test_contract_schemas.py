"""Contract schema tests for representative REST/SSE/WS payloads."""

from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.routes import data, security, stream
from server.routes.stream import _sse_event
from server.schemas.contracts import DataCrawlContract, SecurityFindingContract, SSEEnvelope, WebSocketEnvelope
from server.services.metrics import MetricsService
from server.services.log_buffer import LogBuffer


def _make_app(db):
    app = FastAPI()
    app.include_router(data.router, prefix='/api/data')
    app.include_router(security.router, prefix='/api/security')
    app.include_router(stream.router, prefix='/stream')
    app.state.db = db
    app.state.metrics = MetricsService()
    app.state.log_buffer = LogBuffer(max_size=10)
    app.state.active_jobs = {}
    return app


def _first_sse_payload(raw: str):
    for line in raw.splitlines():
        if line.startswith('data: '):
            return json.loads(line[len('data: '):])
    raise AssertionError('No SSE data line found')


def test_contract_schemas_rest_sse_ws(temp_db):
    crawl_id = asyncio.run(temp_db.create_crawl('https://example.com'))
    page_id = asyncio.run(temp_db.save_page(crawl_id, url='https://example.com', domain='example.com', path='/', status_code=200, title='Home'))
    asyncio.run(temp_db.save_finding(crawl_id, page_id, {
        'type': 'Missing Security Header',
        'severity': 'Low',
        'url': 'https://example.com',
        'evidence': 'Strict-Transport-Security missing',
        'remediation': 'Add HSTS',
    }))

    app = _make_app(temp_db)
    with TestClient(app, raise_server_exceptions=False) as client:
        crawls_resp = client.get('/api/data/crawls')
        assert crawls_resp.status_code == 200
        crawls = crawls_resp.json()
        assert crawls
        DataCrawlContract.model_validate(crawls[0])

        findings_resp = client.get('/api/security/findings')
        assert findings_resp.status_code == 200
        findings = findings_resp.json()
        assert findings
        SecurityFindingContract.model_validate(findings[0])

        # Representative SSE envelope contract (route helper emits this shape)
        env = SSEEnvelope.model_validate(json.loads(_sse_event('metrics', {'pages_crawled': 1})['data']))
        assert env.type == 'metrics'

        # Representative WS event contract shape (translated chat/tool event envelope)
        WebSocketEnvelope.model_validate({'type': 'message', 'payload': {'id': 'm1', 'role': 'assistant', 'content': 'hi'}})
        WebSocketEnvelope.model_validate({'type': 'tool_call', 'payload': {'id': 't1', 'name': 'fetch', 'status': 'pending'}})
