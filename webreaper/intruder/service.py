"""Intruder payload execution service (MVP)."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx


class IntruderService:
    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._cancelled: set[str] = set()

    async def create_job(self, db, **payload) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        method = str(payload.get('method') or 'GET').upper()
        url = str(payload.get('url') or '')
        headers = payload.get('headers') or {}
        body = payload.get('body')
        payloads = [str(p) for p in (payload.get('payloads') or [])]
        markers = self._detect_markers(url, headers, body)
        if not payloads:
            raise ValueError('At least one payload is required')
        if not markers:
            raise ValueError('No §marker§ positions found in url/headers/body')

        rec = {
            'workspace_id': payload.get('workspace_id'),
            'source_transaction_id': payload.get('source_transaction_id'),
            'name': payload.get('name') or f'Intruder {method} {url}',
            'method': method,
            'url': url,
            'headers': headers,
            'body': body,
            'payloads': payloads,
            'payload_markers': markers,
            'attack_type': 'sniper',
            'concurrency': 1,
            'rate_limit_rps': payload.get('rate_limit_rps'),
            'timeout_ms': int(payload.get('timeout_ms') or 10000),
            'follow_redirects': bool(payload.get('follow_redirects', True)),
            'match_substring': payload.get('match_substring'),
            'stop_on_statuses': payload.get('stop_on_statuses') or [],
            'stop_on_first_match': bool(payload.get('stop_on_first_match', False)),
            'status': 'queued',
            'total_attempts': len(payloads),
            'completed_attempts': 0,
            'matched_attempts': 0,
            'cancelled': False,
            'created_at': now,
            'updated_at': now,
        }
        job_id = await db.create_intruder_job(rec)
        return await db.get_intruder_job(job_id)

    async def start_job(self, db, job_id: str, *, wait: bool = False) -> dict[str, Any] | None:
        job = await db.get_intruder_job(job_id)
        if not job:
            return None
        if wait:
            await self._run_job(db, job_id)
            return await db.get_intruder_job(job_id)
        if job_id in self._tasks and not self._tasks[job_id].done():
            return job
        task = asyncio.create_task(self._run_job(db, job_id))
        self._tasks[job_id] = task
        return await db.get_intruder_job(job_id)

    async def cancel_job(self, db, job_id: str) -> dict[str, Any] | None:
        job = await db.get_intruder_job(job_id)
        if not job:
            return None
        self._cancelled.add(job_id)
        await db.update_intruder_job(job_id, cancelled=True, status='cancelled', updated_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc))
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
        return await db.get_intruder_job(job_id)

    async def _run_job(self, db, job_id: str) -> None:
        now = datetime.now(timezone.utc)
        await db.update_intruder_job(job_id, status='running', started_at=now, updated_at=now, cancelled=False)
        job = await db.get_intruder_job(job_id)
        if not job:
            return

        completed = int(job.get('completed_attempts') or 0)
        matched = int(job.get('matched_attempts') or 0)
        try:
            payloads = [str(p) for p in (job.get('payloads') or [])]
            for idx, payload in enumerate(payloads, start=1):
                if job_id in self._cancelled:
                    await db.update_intruder_job(job_id, status='cancelled', cancelled=True, completed_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
                    return
                rendered = self._apply_payload(job, payload)
                result = await self._execute_attempt(db, job, idx, payload, rendered)
                completed += 1
                if result.get('matched'):
                    matched += 1
                await db.update_intruder_job(
                    job_id,
                    completed_attempts=completed,
                    matched_attempts=matched,
                    updated_at=datetime.now(timezone.utc),
                )
                stop_statuses = {int(s) for s in (job.get('stop_on_statuses') or []) if s is not None}
                stop_first = bool(job.get('stop_on_first_match'))
                if (stop_first and result.get('matched')) or (result.get('response_status') in stop_statuses):
                    break
                rps = job.get('rate_limit_rps')
                if rps and float(rps) > 0:
                    await asyncio.sleep(1.0 / float(rps))
            final_status = 'cancelled' if job_id in self._cancelled else 'completed'
            await db.update_intruder_job(job_id, status=final_status, completed_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
        except asyncio.CancelledError:
            await db.update_intruder_job(job_id, status='cancelled', cancelled=True, completed_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
            raise
        except Exception as e:
            await db.update_intruder_job(job_id, status='error', last_error=str(e), completed_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
        finally:
            self._cancelled.discard(job_id)

    async def _execute_attempt(self, db, job: dict[str, Any], attempt_index: int, payload: str, rendered: dict[str, Any]) -> dict[str, Any]:
        method = str(job.get('method') or 'GET').upper()
        timeout_ms = int(job.get('timeout_ms') or 10000)
        follow_redirects = bool(job.get('follow_redirects', True))
        url = rendered['url']
        headers = rendered['headers']
        body = rendered.get('body')

        parsed = urlparse(url)
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
            raise ValueError('Intruder URL must be absolute http/https')

        start = time.perf_counter()
        tx_id = None
        response_status = None
        duration_ms = None
        matched = False
        match_reason = None
        err = None
        try:
            async with httpx.AsyncClient(timeout=timeout_ms / 1000.0, follow_redirects=follow_redirects) as client:
                resp = await client.request(method, url, headers=headers, content=body)
            duration_ms = int((time.perf_counter() - start) * 1000)
            response_status = int(resp.status_code)
            resp_text = resp.text
            match_sub = job.get('match_substring')
            if match_sub and str(match_sub) in resp_text:
                matched = True
                match_reason = f"body contains '{match_sub}'"

            tx_record = {
                'workspace_id': job.get('workspace_id'),
                'source': 'intruder',
                'method': method,
                'scheme': parsed.scheme,
                'host': parsed.netloc,
                'path': parsed.path or '/',
                'query': parsed.query or None,
                'url': url,
                'request_headers': headers,
                'request_body': body,
                'response_status': response_status,
                'response_headers': dict(resp.headers),
                'response_body': resp_text[: 512 * 1024],
                'duration_ms': duration_ms,
                'tags': ['intruder'],
                'intercept_state': 'none',
                'truncated': len(resp_text) > 512 * 1024,
            }
            tx_id = await db.save_http_transaction(tx_record)
        except Exception as e:  # network or execution error
            duration_ms = int((time.perf_counter() - start) * 1000)
            err = str(e)

        result_rec = {
            'job_id': job['id'],
            'attempt_index': attempt_index,
            'payload': payload,
            'request_url': url,
            'request_body': body,
            'transaction_id': tx_id,
            'response_status': response_status,
            'duration_ms': duration_ms,
            'matched': matched,
            'match_reason': match_reason,
            'error': err,
            'created_at': datetime.now(timezone.utc),
        }
        await db.create_intruder_result(result_rec)
        return result_rec

    @staticmethod
    def _detect_markers(url: str, headers: dict[str, Any], body: str | None) -> list[dict[str, Any]]:
        markers = []
        if '§' in (url or ''):
            markers.append({'location': 'url', 'count': (url or '').count('§') // 2})
        header_count = sum(str(v).count('§') // 2 for v in (headers or {}).values())
        if header_count:
            markers.append({'location': 'headers', 'count': header_count})
        if body and '§' in body:
            markers.append({'location': 'body', 'count': body.count('§') // 2})
        return markers

    @staticmethod
    def _apply_payload(job: dict[str, Any], payload: str) -> dict[str, Any]:
        def repl(text: str | None) -> str | None:
            if text is None:
                return None
            out = []
            i = 0
            while i < len(text):
                if text[i] == '§':
                    j = text.find('§', i + 1)
                    if j == -1:
                        out.append(text[i:])
                        break
                    out.append(payload)
                    i = j + 1
                else:
                    out.append(text[i])
                    i += 1
            return ''.join(out)

        headers = {str(k): (repl(str(v)) or '') for k, v in (job.get('headers') or {}).items()}
        return {
            'url': repl(job.get('url') or '') or '',
            'headers': headers,
            'body': repl(job.get('body')),
        }
