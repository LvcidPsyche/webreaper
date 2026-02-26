#!/usr/bin/env python3
"""Seed a local WebReaper DB with demo data for screenshots/manual demos."""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import delete, select

from webreaper.database import (
    DatabaseManager,
    Workspace,
    Crawl,
    Page,
    Link,
    Endpoint,
    SecurityFinding,
    FindingTriage,
    ProxySession,
    HttpTransaction,
    RepeaterTab,
    RepeaterRun,
    IntruderJob,
    IntruderResult,
)
from webreaper.migrations import ensure_database_schema


def uid() -> str:
    return str(uuid.uuid4())


async def main() -> None:
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise SystemExit('DATABASE_URL is required')
    db = DatabaseManager(db_url)
    await db.init_async()
    await ensure_database_schema(db)

    now = datetime.now(timezone.utc)

    async with db.get_session() as session:
        # Clear demo-ish rows (simple reset for local demo DB)
        for model in [
            IntruderResult, IntruderJob, RepeaterRun, RepeaterTab,
            HttpTransaction, ProxySession, FindingTriage, SecurityFinding,
            Endpoint, Link, Page, Crawl, Workspace,
        ]:
            await session.execute(delete(model))

        ws_id = uid()
        ws = Workspace(
            id=ws_id,
            name='Demo Workspace',
            description='Local demo workspace for screenshots',
            scope_rules=[{"id": "rule1", "type": "host", "value": "example.com"}],
            tags=['demo', 'webreaper'],
            risk_policy={
                'allow_active_scan': True,
                'allow_intruder': True,
                'allow_intercept_edit': True,
                'require_ack_active_scan': False,
                'require_ack_intruder': False,
            },
            created_at=now,
            updated_at=now,
        )
        session.add(ws)

        crawl_id = uid()
        crawl = Crawl(
            id=crawl_id,
            target_url='https://example.com',
            status='completed',
            workspace_id=ws_id,
            pages_crawled=3,
            pages_failed=0,
            total_bytes=128000,
            external_links=2,
            requests_per_sec=12.5,
            started_at=now - timedelta(minutes=5),
            completed_at=now - timedelta(minutes=4),
            created_at=now - timedelta(minutes=5),
            config={'crawler': {'max_depth': 3, 'concurrency': 10}},
        )
        session.add(crawl)

        p1 = Page(
            id=uid(), crawl_id=crawl_id, workspace_id=ws_id, url='https://example.com/', final_url='https://example.com/',
            domain='example.com', path='/', status_code=200, title='Example Home', h1='Example Home',
            word_count=540, depth=0, seo_score=86, readability_score=63.2, language='en',
            content_hash='abcd1234', links_count=4, external_links_count=1, fetch_mode='browser',
            browser_observed_requests=[{'url':'https://example.com/api/menu','method':'GET','source':'browser'}],
            scraped_at=now - timedelta(minutes=5)
        )
        p2 = Page(
            id=uid(), crawl_id=crawl_id, workspace_id=ws_id, url='https://example.com/login', final_url='https://example.com/login',
            domain='example.com', path='/login', status_code=200, title='Login', h1='Login',
            word_count=220, depth=1, seo_score=71, readability_score=55.0, language='en',
            content_hash='efgh5678', links_count=2, external_links_count=0, fetch_mode='http',
            forms_count=1, scraped_at=now - timedelta(minutes=4, seconds=30)
        )
        p3 = Page(
            id=uid(), crawl_id=crawl_id, workspace_id=ws_id, url='https://example.com/account', final_url='https://example.com/account',
            domain='example.com', path='/account', status_code=403, title='Account', h1='Account',
            word_count=110, depth=2, seo_score=48, readability_score=50.0, language='en',
            content_hash='efgh5678', links_count=0, external_links_count=0, fetch_mode='http',
            scraped_at=now - timedelta(minutes=4)
        )
        session.add_all([p1, p2, p3])

        session.add_all([
            Link(id=uid(), crawl_id=crawl_id, source_page_id=p1.id, target_url='https://example.com/login', target_domain='example.com', anchor_text='Login', is_external=False, status_code=200, link_type='text'),
            Link(id=uid(), crawl_id=crawl_id, source_page_id=p1.id, target_url='https://bad.example.net/dead', target_domain='bad.example.net', anchor_text='Dead', is_external=True, is_broken=True, status_code=404, link_type='text'),
            Link(id=uid(), crawl_id=crawl_id, source_page_id=p1.id, target_url='https://redir.example.net/go', target_domain='redir.example.net', anchor_text='Redirect', is_external=True, status_code=302, link_type='text'),
        ])

        session.add_all([
            Endpoint(id=uid(), crawl_id=crawl_id, workspace_id=ws_id, page_id=p1.id, host='example.com', scheme='https', method='GET', path='/search', query_params=['q'], body_param_names=[], content_types=[], sources=['crawl_link'], first_seen_at=now, last_seen_at=now),
            Endpoint(id=uid(), crawl_id=crawl_id, workspace_id=ws_id, page_id=p2.id, host='example.com', scheme='https', method='POST', path='/api/login', query_params=[], body_param_names=['email','password'], content_types=['application/json'], sources=['crawl_form'], first_seen_at=now, last_seen_at=now),
        ])

        f1 = SecurityFinding(
            id=uid(), crawl_id=crawl_id, page_id=p2.id, workspace_id=ws_id,
            finding_type='Missing Security Header', severity='Low', confidence='high',
            url='https://example.com/login', title='Missing Security Header',
            evidence='Strict-Transport-Security header not present', remediation='Add HSTS',
            discovered_at=now - timedelta(minutes=3), verified=False, false_positive=False,
        )
        f2 = SecurityFinding(
            id=uid(), crawl_id=crawl_id, page_id=p2.id, workspace_id=ws_id,
            finding_type='Potential SSRF Vector', severity='Medium', confidence='medium',
            url='https://example.com/fetch?url=https://example.org', title='Potential SSRF Vector',
            parameter='url', evidence="Parameter 'url' may accept URLs", remediation='Allowlist outbound targets',
            discovered_at=now - timedelta(minutes=2), verified=False, false_positive=False,
        )
        session.add_all([f1, f2])
        session.add_all([
            FindingTriage(id=uid(), finding_id=f1.id, workspace_id=ws_id, status='open', tags=['headers'], notes='Check reverse proxy config', triaged_at=now - timedelta(minutes=3), updated_at=now - timedelta(minutes=3)),
            FindingTriage(id=uid(), finding_id=f2.id, workspace_id=ws_id, status='in_progress', assignee='analyst', tags=['ssrf','p1'], notes='Need exploitability validation', reproduction_steps=['Call /fetch with attacker URL'], evidence_refs=[{'type':'proxy_tx'}], triaged_at=now - timedelta(minutes=2), updated_at=now - timedelta(minutes=2)),
        ])

        proxy_session_id = uid()
        session.add(ProxySession(
            id=proxy_session_id, workspace_id=ws_id, name='Demo Proxy', host='127.0.0.1', port=8080,
            intercept_enabled=True, tls_intercept_enabled=False, body_capture_limit_kb=512,
            include_hosts=['example.com'], exclude_hosts=[], status='running',
            started_at=now - timedelta(minutes=10), created_at=now - timedelta(minutes=10), updated_at=now - timedelta(minutes=1)
        ))

        tx1 = HttpTransaction(
            id=uid(), workspace_id=ws_id, proxy_session_id=proxy_session_id, source='proxy', method='POST', scheme='https', host='example.com',
            path='/api/login', query=None, url='https://example.com/api/login',
            request_headers={'content-type': 'application/json'}, request_body='{"email":"demo@example.com","password":"***"}',
            response_status=200, response_headers={'content-type':'application/json'}, response_body='{"ok":true,"token":"redacted"}',
            duration_ms=122, tags=['auth','login'], intercept_state='queued', truncated=False, created_at=now - timedelta(minutes=1)
        )
        tx2 = HttpTransaction(
            id=uid(), workspace_id=ws_id, proxy_session_id=proxy_session_id, source='proxy', method='GET', scheme='https', host='example.com',
            path='/api/me', query='verbose=1', url='https://example.com/api/me?verbose=1',
            request_headers={'accept': 'application/json'}, request_body=None,
            response_status=200, response_headers={'content-type':'application/json'}, response_body='{"id":1,"role":"user"}',
            duration_ms=88, tags=['api'], intercept_state='forwarded', truncated=False, created_at=now - timedelta(minutes=1, seconds=15)
        )
        session.add_all([tx1, tx2])

        rep_tab_id = uid()
        session.add(RepeaterTab(
            id=rep_tab_id, workspace_id=ws_id, source_transaction_id=tx1.id, name='Replay Login', method='POST',
            url='https://example.com/api/login', headers={'content-type':'application/json'}, body='{"email":"demo@example.com","password":"test"}',
            created_at=now - timedelta(minutes=20), updated_at=now - timedelta(minutes=1), last_run_at=now - timedelta(minutes=1)
        ))
        rep_tx = HttpTransaction(
            id=uid(), workspace_id=ws_id, source='repeater', method='POST', scheme='https', host='example.com', path='/api/login', query=None, url='https://example.com/api/login',
            request_headers={'content-type':'application/json'}, request_body='{"email":"demo@example.com","password":"test"}',
            response_status=401, response_headers={'content-type':'application/json'}, response_body='{"ok":false,"error":"invalid creds"}',
            duration_ms=141, tags=['repeater'], intercept_state='none', truncated=False, created_at=now - timedelta(minutes=1)
        )
        session.add(rep_tx)
        session.add(RepeaterRun(
            id=uid(), repeater_tab_id=rep_tab_id, workspace_id=ws_id, transaction_id=rep_tx.id,
            status='success', response_status=401, duration_ms=141, timeout_ms=3000, follow_redirects=True,
            diff_summary={'baseline': False, 'changed': True, 'status_changed': True, 'status_before': 200, 'status_after': 401},
            created_at=now - timedelta(minutes=1)
        ))

        intr_job_id = uid()
        session.add(IntruderJob(
            id=intr_job_id, workspace_id=ws_id, source_transaction_id=tx2.id,
            name='Intruder /api/me param fuzz', method='GET', url='https://example.com/api/me?id=§FUZZ§', headers={'accept':'application/json'}, body=None,
            payloads=['1','2','admin'], payload_markers=[{'location':'url','count':1}], attack_type='sniper',
            concurrency=1, rate_limit_rps=5.0, timeout_ms=10000, follow_redirects=True,
            match_substring='admin', stop_on_statuses=[], stop_on_first_match=True,
            status='completed', total_attempts=3, completed_attempts=3, matched_attempts=1, cancelled=False,
            started_at=now - timedelta(minutes=6), completed_at=now - timedelta(minutes=5, seconds=30),
            created_at=now - timedelta(minutes=6), updated_at=now - timedelta(minutes=5, seconds=30),
        ))
        intr_tx = HttpTransaction(
            id=uid(), workspace_id=ws_id, source='intruder', method='GET', scheme='https', host='example.com', path='/api/me', query='id=admin', url='https://example.com/api/me?id=admin',
            request_headers={'accept':'application/json'}, request_body=None,
            response_status=200, response_headers={'content-type':'application/json'}, response_body='{"role":"admin","debug":true}',
            duration_ms=97, tags=['intruder'], intercept_state='none', truncated=False, created_at=now - timedelta(minutes=5, seconds=40)
        )
        session.add(intr_tx)
        session.add_all([
            IntruderResult(id=uid(), job_id=intr_job_id, attempt_index=1, payload='1', request_url='https://example.com/api/me?id=1', request_body=None, response_status=404, duration_ms=80, matched=False, created_at=now - timedelta(minutes=5, seconds=55)),
            IntruderResult(id=uid(), job_id=intr_job_id, attempt_index=2, payload='2', request_url='https://example.com/api/me?id=2', request_body=None, response_status=404, duration_ms=83, matched=False, created_at=now - timedelta(minutes=5, seconds=50)),
            IntruderResult(id=uid(), job_id=intr_job_id, attempt_index=3, payload='admin', request_url='https://example.com/api/me?id=admin', request_body=None, transaction_id=intr_tx.id, response_status=200, duration_ms=97, matched=True, match_reason="body contains 'admin'", created_at=now - timedelta(minutes=5, seconds=40)),
        ])

    await db.close()
    print('Seeded demo data into', db_url)


if __name__ == '__main__':
    asyncio.run(main())
