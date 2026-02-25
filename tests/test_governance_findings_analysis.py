"""Tests for governance/policy, findings triage/reporting, and added analysis endpoints."""

from __future__ import annotations

import asyncio

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.routes import workspaces, security, intruder, governance, analysis
from webreaper.intruder.service import IntruderService


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, method, url, headers=None, content=None):
        req = httpx.Request(method, url, headers=headers or {}, content=(content.encode() if isinstance(content, str) else content))
        return httpx.Response(200, request=req, headers={'content-type': 'text/plain'}, content=b'OK admin')


def _make_app(db):
    app = FastAPI()
    app.include_router(workspaces.router, prefix='/api/workspaces')
    app.include_router(security.router, prefix='/api/security')
    app.include_router(intruder.router, prefix='/api/intruder')
    app.include_router(governance.router, prefix='/api/governance')
    app.include_router(analysis.router, prefix='/api/analysis')
    app.state.db = db
    app.state.intruder_service = IntruderService()
    return app


def test_intruder_policy_ack_gate_and_audit_logs(temp_db, monkeypatch):
    monkeypatch.setattr('webreaper.intruder.service.httpx.AsyncClient', _FakeAsyncClient)
    app = _make_app(temp_db)
    with TestClient(app, raise_server_exceptions=False) as client:
        ws = client.post('/api/workspaces', json={
            'name': 'Acme',
            'scope_rules': [],
            'risk_policy': {
                'allow_intruder': True,
                'require_ack_intruder': True,
            },
        }).json()

        job = client.post('/api/intruder/jobs', json={
            'workspace_id': ws['id'],
            'url': 'https://example.com/search?q=§FUZZ§',
            'payloads': ['admin'],
        })
        assert job.status_code == 200, job.text
        job_id = job.json()['id']

        denied = client.post(f'/api/intruder/jobs/{job_id}/start', json={'wait': True, 'acknowledge_risk': False})
        assert denied.status_code == 403

        allowed = client.post(f'/api/intruder/jobs/{job_id}/start', json={'wait': True, 'acknowledge_risk': True})
        assert allowed.status_code == 200, allowed.text

        logs = client.get(f"/api/governance/audit?workspace_id={ws['id']}&action=intruder.start")
        assert logs.status_code == 200
        rows = logs.json()
        assert any(r['allowed'] is False for r in rows)
        assert any(r['allowed'] is True for r in rows)


def test_finding_triage_and_report_export(temp_db):
    # Seed crawl + page + finding
    crawl_id = asyncio.run(temp_db.create_crawl('https://example.com'))
    page_id = asyncio.run(temp_db.save_page(crawl_id, url='https://example.com', domain='example.com', path='/', status_code=200, title='Home'))
    asyncio.run(temp_db.save_finding(crawl_id, page_id, {
        'type': 'XSS',
        'severity': 'High',
        'evidence': '<script>alert(1)</script>',
        'description': 'Reflected value',
        'remediation': 'Escape output',
        'url': 'https://example.com/?q=<script>alert(1)</script>',
        'parameter': 'q',
    }))

    app = _make_app(temp_db)
    with TestClient(app, raise_server_exceptions=False) as client:
        findings = client.get('/api/security/findings')
        assert findings.status_code == 200
        finding = findings.json()[0]

        triage = client.patch(f"/api/security/findings/{finding['id']}/triage", json={
            'status': 'in_progress',
            'assignee': 'analyst',
            'tags': ['xss', 'p1'],
            'notes': 'Needs repro in staging',
            'reproduction_steps': ['Open URL', 'Observe alert'],
            'evidence_refs': [{'type': 'proxy_tx', 'id': 'abc'}],
        })
        assert triage.status_code == 200, triage.text

        triaged_list = client.get('/api/security/triage?status=in_progress')
        assert triaged_list.status_code == 200
        rows = triaged_list.json()
        assert rows and rows[0]['status'] == 'in_progress'

        report_json = client.get('/api/security/report/export?format=json')
        assert report_json.status_code == 200
        assert report_json.json()['total'] >= 1

        report_md = client.get('/api/security/report/export?format=markdown')
        assert report_md.status_code == 200
        assert 'content' in report_md.json()
        assert 'WebReaper Security Findings Report' in report_md.json()['content']


def test_analysis_duplicate_link_health_and_manual_seeds(temp_db):
    crawl_id = asyncio.run(temp_db.create_crawl('https://example.com'))
    page1 = asyncio.run(temp_db.save_page(crawl_id, url='https://example.com/', domain='example.com', path='/', status_code=200, title='Home', content_hash='abcd1234', depth=0, links_count=2))
    page2 = asyncio.run(temp_db.save_page(crawl_id, url='https://example.com/index', domain='example.com', path='/index', status_code=200, title='Home', content_hash='abcd1234', depth=2, links_count=0))
    page3 = asyncio.run(temp_db.save_page(crawl_id, url='https://example.com/deep', domain='example.com', path='/deep', status_code=200, title='Deep', content_hash='efgh5678', depth=7, links_count=0))
    asyncio.run(temp_db.save_links(crawl_id, page1, [
        {'url': 'https://bad.example.com/x', 'is_external': True, 'status_code': 404},
        {'url': 'https://redir.example.com/y', 'is_external': True, 'status_code': 302},
    ]))
    # mark broken on one link via direct SQL helper
    async def _mark_broken():
        async with temp_db.get_session() as s:
            await s.execute(__import__('sqlalchemy').text('UPDATE links SET is_broken = 1 WHERE target_url = :u'), {'u': 'https://bad.example.com/x'})
    asyncio.run(_mark_broken())
    asyncio.run(temp_db.upsert_endpoints(crawl_id, page1, [
        {'host': 'example.com', 'scheme': 'https', 'method': 'GET', 'path': '/search', 'query_params': ['q'], 'body_param_names': [], 'content_types': [], 'sources': ['crawl_link']},
        {'host': 'example.com', 'scheme': 'https', 'method': 'POST', 'path': '/login', 'query_params': [], 'body_param_names': ['user', 'pass'], 'content_types': ['application/x-www-form-urlencoded'], 'sources': ['crawl_form']},
    ]))

    app = _make_app(temp_db)
    with TestClient(app, raise_server_exceptions=False) as client:
        dup = client.get(f'/api/analysis/duplicates/{crawl_id}')
        assert dup.status_code == 200
        assert dup.json()['exact_duplicates']

        lh = client.get(f'/api/analysis/link-health/{crawl_id}')
        assert lh.status_code == 200
        body = lh.json()
        assert body['broken_links']
        assert body['redirect_links']
        assert body['depth_outliers']

        seeds = client.get(f'/api/analysis/manual-seeds/{crawl_id}')
        assert seeds.status_code == 200
        s = seeds.json()
        assert s['repeater'] and s['intruder'] and s['passive_scan']


def test_profiles_ui_preferences_and_automation(temp_db):
    app = _make_app(temp_db)
    with TestClient(app, raise_server_exceptions=False) as client:
        profile = client.post('/api/governance/profiles', json={
            'profile_type': 'scan',
            'name': 'Passive Scan Default',
            'settings': {'auto_attack': False, 'timeout_ms': 10000},
        })
        assert profile.status_code == 200, profile.text
        pid = profile.json()['id']

        listed = client.get('/api/governance/profiles?profile_type=scan')
        assert listed.status_code == 200
        assert any(p['id'] == pid for p in listed.json())

        pref_put = client.put('/api/governance/ui-preferences', json={
            'page': 'proxy',
            'key': 'saved_view.default',
            'value': {'columns': ['method', 'host', 'status'], 'filters': {'queuedOnly': True}},
        })
        assert pref_put.status_code == 200

        pref_get = client.get('/api/governance/ui-preferences?page=proxy')
        assert pref_get.status_code == 200
        assert 'saved_view.default' in pref_get.json()

        auto = client.post('/api/governance/automation/run', json={
            'name': 'Crawl-Scan-Report',
            'chain': ['crawl', 'scan', 'report'],
            'inputs': {'target_url': 'https://example.com', 'scan_mode': 'passive'},
            'wait': True,
        })
        assert auto.status_code == 200, auto.text
        body = auto.json()
        assert body['status'] == 'completed'
        assert body['outputs']['summary']['total_steps'] == 3

        runs = client.get('/api/governance/automation/runs')
        assert runs.status_code == 200
        assert any(r['id'] == body['id'] for r in runs.json())
