"""Intruder APIs (payload fuzzing MVP)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from webreaper.governance.policy import evaluate_policy, audit_log

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class IntruderJobCreateRequest(BaseModel):
    workspace_id: str | None = None
    source_transaction_id: str | None = None
    name: str | None = None
    method: str = 'GET'
    url: str
    headers: dict[str, Any] = Field(default_factory=dict)
    body: str | None = None
    payloads: list[str] = Field(default_factory=list)
    rate_limit_rps: float | None = Field(default=None, gt=0)
    timeout_ms: int = Field(default=10000, ge=100, le=120000)
    follow_redirects: bool = True
    match_substring: str | None = None
    stop_on_statuses: list[int] = Field(default_factory=list)
    stop_on_first_match: bool = False


class IntruderJobStartRequest(BaseModel):
    wait: bool = False
    acknowledge_risk: bool = False


class SendToIntruderRequest(BaseModel):
    transaction_id: str
    payloads: list[str] = Field(default_factory=list)
    marker_target: str = 'url'  # url|body
    name: str | None = None


def _db(request: Request):
    db = getattr(request.app.state, 'db', None)
    if not db:
        raise HTTPException(status_code=503, detail='Database not available')
    return db


def _svc(request: Request):
    svc = getattr(request.app.state, 'intruder_service', None)
    if not svc:
        raise HTTPException(status_code=503, detail='Intruder service not available')
    return svc


def _ser(v: Any):
    if isinstance(v, dict):
        return {k: _ser(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_ser(i) for i in v]
    if isinstance(v, datetime):
        return v.isoformat()
    return v


@router.get('/jobs')
async def list_jobs(request: Request, workspace_id: str | None = None, limit: int = Query(default=200, le=1000)):
    rows = await _db(request).list_intruder_jobs(workspace_id=workspace_id, limit=limit)
    return [_ser(r) for r in rows]


@router.post('/jobs')
@limiter.limit("5/minute")
async def create_job(payload: IntruderJobCreateRequest, request: Request):
    db = _db(request)
    svc = _svc(request)
    try:
        job = await svc.create_job(db, **payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _ser(job)


@router.get('/jobs/{job_id}')
async def get_job(job_id: str, request: Request):
    job = await _db(request).get_intruder_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='Intruder job not found')
    return _ser(job)


@router.post('/jobs/{job_id}/start')
@limiter.limit("5/minute")
async def start_job(job_id: str, payload: IntruderJobStartRequest, request: Request):
    db = _db(request)
    svc = _svc(request)
    existing = await db.get_intruder_job(job_id)
    if not existing:
        raise HTTPException(status_code=404, detail='Intruder job not found')
    decision = await evaluate_policy(db, existing.get("workspace_id"), "intruder.start", acknowledge=payload.acknowledge_risk)
    await audit_log(
        db,
        workspace_id=existing.get("workspace_id"),
        action="intruder.start",
        allowed=decision.allowed,
        resource_type="intruder_job",
        resource_id=job_id,
        policy_rule=decision.rule,
        reason=decision.reason,
        details={"wait": payload.wait},
    )
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.reason)
    job = await svc.start_job(db, job_id, wait=payload.wait)
    return _ser(job)


@router.post('/jobs/{job_id}/cancel')
async def cancel_job(job_id: str, request: Request):
    db = _db(request)
    svc = _svc(request)
    job = await svc.cancel_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail='Intruder job not found')
    await audit_log(db, workspace_id=job.get("workspace_id"), action="intruder.cancel", allowed=True, resource_type="intruder_job", resource_id=job_id)
    return _ser(job)


@router.get('/jobs/{job_id}/results')
async def list_results(job_id: str, request: Request, limit: int = Query(default=500, le=5000), offset: int = 0):
    db = _db(request)
    job = await db.get_intruder_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='Intruder job not found')
    data = await db.list_intruder_results(job_id, limit=limit, offset=offset)
    rows = data['results']
    for row in rows:
        tx_id = row.get('transaction_id')
        if tx_id:
            tx = await db.get_http_transaction(str(tx_id))
            if tx:
                row['transaction'] = tx
    return _ser({'total': data['total'], 'offset': offset, 'limit': limit, 'results': rows})


@router.post('/send-to-intruder')
async def send_to_intruder(payload: SendToIntruderRequest, request: Request):
    db = _db(request)
    svc = _svc(request)
    tx = await db.get_http_transaction(payload.transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail='Source transaction not found')

    marker_target = payload.marker_target.lower()
    if marker_target not in {'url', 'body'}:
        raise HTTPException(status_code=400, detail='marker_target must be url or body')

    url = tx.get('url') or ''
    body = tx.get('request_body')
    if marker_target == 'url':
        if '?' in url:
            url = url + '§FUZZ§'
        else:
            url = url + '?q=§FUZZ§'
    else:
        body = (body or '') + '§FUZZ§'

    try:
        job = await svc.create_job(
            db,
            workspace_id=tx.get('workspace_id'),
            source_transaction_id=payload.transaction_id,
            name=payload.name or f"Intruder from {tx.get('source', 'tx')}",
            method=tx.get('method') or 'GET',
            url=url,
            headers=tx.get('request_headers') or {},
            body=body,
            payloads=payload.payloads,
            timeout_ms=10000,
            follow_redirects=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _ser(job)
