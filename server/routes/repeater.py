"""Repeater APIs (manual request replay + decoder utilities)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from webreaper.repeater.decoder import transform as decode_transform

router = APIRouter()


class RepeaterTabCreateRequest(BaseModel):
    workspace_id: str | None = None
    name: str | None = None
    method: str = "GET"
    url: str
    headers: dict[str, Any] = Field(default_factory=dict)
    body: str | None = None
    source_transaction_id: str | None = None


class RepeaterTabUpdateRequest(BaseModel):
    name: str | None = None
    method: str | None = None
    url: str | None = None
    headers: dict[str, Any] | None = None
    body: str | None = None


class SendToRepeaterRequest(BaseModel):
    transaction_id: str | None = None
    workspace_id: str | None = None
    name: str | None = None
    request: dict[str, Any] | None = None


class RepeaterExecuteRequest(BaseModel):
    timeout_ms: int = Field(default=15000, ge=100, le=120000)
    follow_redirects: bool = True


class DecoderRequest(BaseModel):
    operation: str
    input: str


class DecoderBatchRequest(BaseModel):
    operations: list[str]
    input: str


def _db(request: Request):
    db = getattr(request.app.state, "db", None)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    return db


def _service(request: Request):
    svc = getattr(request.app.state, "repeater_service", None)
    if not svc:
        raise HTTPException(status_code=503, detail="Repeater service not available")
    return svc


def _ser(v: Any):
    if isinstance(v, dict):
        return {k: _ser(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_ser(i) for i in v]
    if isinstance(v, datetime):
        return v.isoformat()
    return v


@router.get("/tabs")
async def list_tabs(request: Request, workspace_id: str | None = None, limit: int = Query(default=200, le=1000)):
    db = _db(request)
    rows = await db.list_repeater_tabs(workspace_id=workspace_id, limit=limit)
    return [_ser(r) for r in rows]


@router.post("/tabs")
async def create_tab(payload: RepeaterTabCreateRequest, request: Request):
    db = _db(request)
    svc = _service(request)
    tab = await svc.create_tab(db, **payload.model_dump())
    return _ser(tab)


@router.get("/tabs/{tab_id}")
async def get_tab(tab_id: str, request: Request):
    db = _db(request)
    tab = await db.get_repeater_tab(tab_id)
    if not tab:
        raise HTTPException(status_code=404, detail="Repeater tab not found")
    return _ser(tab)


@router.put("/tabs/{tab_id}")
async def update_tab(tab_id: str, payload: RepeaterTabUpdateRequest, request: Request):
    db = _db(request)
    svc = _service(request)
    tab = await svc.update_tab(db, tab_id, **payload.model_dump())
    if not tab:
        raise HTTPException(status_code=404, detail="Repeater tab not found")
    return _ser(tab)


@router.get("/tabs/{tab_id}/runs")
async def list_tab_runs(tab_id: str, request: Request, limit: int = Query(default=50, le=200)):
    db = _db(request)
    tab = await db.get_repeater_tab(tab_id)
    if not tab:
        raise HTTPException(status_code=404, detail="Repeater tab not found")
    runs = await db.list_repeater_runs(tab_id, limit=limit)
    out = []
    for run in runs:
        row = dict(run)
        tx_id = row.get("transaction_id")
        if tx_id:
            tx = await db.get_http_transaction(str(tx_id))
            if tx:
                row["transaction"] = tx
        out.append(_ser(row))
    return out


@router.post("/tabs/{tab_id}/send")
async def send_tab(tab_id: str, payload: RepeaterExecuteRequest, request: Request):
    db = _db(request)
    svc = _service(request)
    result = await svc.execute_tab(
        db,
        tab_id,
        timeout_ms=payload.timeout_ms,
        follow_redirects=payload.follow_redirects,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Repeater tab not found")
    return _ser(result)


@router.post("/send-to-repeater")
async def send_to_repeater(payload: SendToRepeaterRequest, request: Request):
    db = _db(request)
    svc = _service(request)
    if payload.transaction_id:
        tab = await svc.send_to_repeater_from_transaction(
            db,
            payload.transaction_id,
            workspace_id=payload.workspace_id,
            name=payload.name,
        )
        if not tab:
            raise HTTPException(status_code=404, detail="Source transaction not found")
        return _ser(tab)

    raw_req = payload.request or {}
    if not raw_req.get("url"):
        raise HTTPException(status_code=400, detail="request.url is required when transaction_id is not provided")
    tab = await svc.create_tab(
        db,
        workspace_id=payload.workspace_id,
        name=payload.name,
        method=raw_req.get("method") or "GET",
        url=raw_req.get("url"),
        headers=raw_req.get("headers") or {},
        body=raw_req.get("body"),
    )
    return _ser(tab)


@router.post("/decode")
async def decode_value(payload: DecoderRequest):
    return decode_transform(payload.operation, payload.input)


@router.post("/decode/batch")
async def decode_batch(payload: DecoderBatchRequest):
    return {
        "input": payload.input,
        "results": [decode_transform(op, payload.input) for op in payload.operations],
    }
