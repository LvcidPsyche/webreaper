"""Proxy service control and history APIs (MVP foundation)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from webreaper.proxy.certs import cert_status
from webreaper.governance.policy import evaluate_policy, audit_log

router = APIRouter()


class ProxyStartRequest(BaseModel):
    workspace_id: str | None = None
    name: str | None = None
    host: str = "127.0.0.1"
    port: int = Field(default=8080, ge=1, le=65535)
    intercept_enabled: bool = False
    tls_intercept_enabled: bool = False
    body_capture_limit_kb: int = Field(default=512, ge=1, le=8192)
    include_hosts: list[str] = Field(default_factory=list)
    exclude_hosts: list[str] = Field(default_factory=list)


class ProxyInterceptRequest(BaseModel):
    enabled: bool


class ProxyCaptureRequest(BaseModel):
    session_id: str | None = None
    workspace_id: str | None = None
    source: str = "proxy"
    request: dict
    response: dict | None = None
    tags: list[str] = Field(default_factory=list)
    intercept_state: str = "none"


class ProxyInterceptEditRequest(BaseModel):
    request: dict | None = None
    response: dict | None = None
    tags: list[str] = Field(default_factory=list)
    acknowledge_risk: bool = False


class ProxyCertVerifyRequest(BaseModel):
    ca_cert_path: str | None = None


def _db(request: Request):
    db = getattr(request.app.state, "db", None)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    return db


def _service(request: Request):
    svc = getattr(request.app.state, "proxy_service", None)
    if not svc:
        raise HTTPException(status_code=503, detail="Proxy service not available")
    return svc


def _serialize_runtime(runtime) -> dict:
    return {
        "id": runtime.id,
        "workspace_id": runtime.workspace_id,
        "name": runtime.name,
        "host": runtime.host,
        "port": runtime.port,
        "intercept_enabled": runtime.intercept_enabled,
        "tls_intercept_enabled": runtime.tls_intercept_enabled,
        "body_capture_limit_kb": runtime.body_capture_limit_kb,
        "include_hosts": runtime.include_hosts,
        "exclude_hosts": runtime.exclude_hosts,
        "status": runtime.status,
        "started_at": runtime.started_at,
        "stopped_at": runtime.stopped_at,
        "updated_at": runtime.updated_at,
    }


@router.post("/sessions")
async def start_proxy_session(payload: ProxyStartRequest, request: Request):
    db = _db(request)
    svc = _service(request)
    runtime = await svc.start_session(db, **payload.model_dump())
    return _serialize_runtime(runtime)


@router.get("/sessions")
async def list_proxy_sessions(request: Request, workspace_id: str | None = None):
    db = _db(request)
    svc = _service(request)
    rows = await svc.list_sessions(db, workspace_id=workspace_id)
    for row in rows:
        for k in ("created_at", "updated_at", "started_at", "stopped_at"):
            v = row.get(k)
            if v is not None and not isinstance(v, str):
                row[k] = v.isoformat()
    return rows


@router.get("/sessions/{session_id}")
async def proxy_session_status(session_id: str, request: Request):
    db = _db(request)
    svc = _service(request)
    runtime = await svc.get_status(db, session_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="Proxy session not found")
    return _serialize_runtime(runtime)


@router.post("/sessions/{session_id}/intercept")
async def set_proxy_intercept(session_id: str, payload: ProxyInterceptRequest, request: Request):
    db = _db(request)
    svc = _service(request)
    runtime = await svc.set_intercept(db, session_id, payload.enabled)
    if not runtime:
        raise HTTPException(status_code=404, detail="Proxy session not found")
    return _serialize_runtime(runtime)


@router.post("/sessions/{session_id}/stop")
async def stop_proxy_session(session_id: str, request: Request):
    db = _db(request)
    svc = _service(request)
    runtime = await svc.stop_session(db, session_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="Proxy session not found")
    return _serialize_runtime(runtime)


@router.post("/capture")
async def capture_flow(payload: ProxyCaptureRequest, request: Request):
    """MVP ingestion endpoint for captured flows (future mitmproxy adapter hooks here)."""
    db = _db(request)
    svc = _service(request)
    tx_id = await svc.record_flow(
        db,
        session_id=payload.session_id,
        workspace_id=payload.workspace_id,
        source=payload.source,
        request=payload.request,
        response=payload.response,
        tags=payload.tags,
        intercept_state=payload.intercept_state,
    )
    return {"id": tx_id, "status": "stored"}


@router.get("/cert-status")
async def proxy_cert_status():
    return cert_status()


@router.post("/cert-status/verify")
async def proxy_cert_verify(payload: ProxyCertVerifyRequest):
    return cert_status(payload.ca_cert_path)


@router.get("/history")
async def proxy_history(
    request: Request,
    workspace_id: str | None = None,
    session_id: str | None = None,
    source: str | None = None,
    method: str | None = None,
    host: str | None = None,
    intercept_state: str | None = None,
    limit: int = Query(default=200, le=1000),
    offset: int = 0,
):
    db = _db(request)
    data = await db.list_http_transactions(
        workspace_id=workspace_id,
        proxy_session_id=session_id,
        source=source,
        method=method,
        host=host,
        intercept_state=intercept_state,
        limit=limit,
        offset=offset,
    )
    rows = data["transactions"]
    for row in rows:
        for k in ("created_at",):
            v = row.get(k)
            if v is not None and not isinstance(v, str):
                row[k] = v.isoformat()
    return {"total": data["total"], "offset": offset, "limit": limit, "transactions": rows}


@router.get("/intercept/queue")
async def get_intercept_queue(
    request: Request,
    session_id: str | None = None,
    limit: int = Query(default=200, le=1000),
):
    db = _db(request)
    svc = _service(request)
    rows = await svc.list_intercept_queue(db, session_id=session_id, limit=limit)
    for row in rows:
        v = row.get("created_at")
        if v is not None and not isinstance(v, str):
            row["created_at"] = v.isoformat()
    return {"count": len(rows), "items": rows}


@router.post("/intercept/{transaction_id}/forward")
async def forward_intercept(transaction_id: str, request: Request):
    db = _db(request)
    svc = _service(request)
    tx = await svc.forward_intercept(db, transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Intercept transaction not found")
    await audit_log(db, workspace_id=tx.get("workspace_id"), action="proxy.intercept_forward", allowed=True, resource_type="http_transaction", resource_id=transaction_id)
    return tx


@router.post("/intercept/{transaction_id}/drop")
async def drop_intercept(transaction_id: str, request: Request):
    db = _db(request)
    svc = _service(request)
    tx = await svc.drop_intercept(db, transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Intercept transaction not found")
    await audit_log(db, workspace_id=tx.get("workspace_id"), action="proxy.intercept_drop", allowed=True, resource_type="http_transaction", resource_id=transaction_id)
    return tx


@router.post("/intercept/{transaction_id}/edit")
async def edit_intercept(transaction_id: str, payload: ProxyInterceptEditRequest, request: Request):
    db = _db(request)
    svc = _service(request)
    existing = await db.get_http_transaction(transaction_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Intercept transaction not found")
    decision = await evaluate_policy(db, existing.get("workspace_id"), "proxy.intercept_edit", acknowledge=payload.acknowledge_risk)
    await audit_log(
        db,
        workspace_id=existing.get("workspace_id"),
        action="proxy.intercept_edit",
        allowed=decision.allowed,
        resource_type="http_transaction",
        resource_id=transaction_id,
        policy_rule=decision.rule,
        reason=decision.reason,
        details={"has_request_patch": bool(payload.request), "has_response_patch": bool(payload.response)},
    )
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.reason)
    tx = await svc.edit_intercept(
        db,
        transaction_id,
        request_patch=payload.request,
        response_patch=payload.response,
        tags=payload.tags,
    )
    return tx
