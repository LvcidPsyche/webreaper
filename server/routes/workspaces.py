"""Workspace CRUD and scope utilities."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from webreaper.database import Workspace
from webreaper.workspaces.scope import evaluate_scope

router = APIRouter()


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    scope_rules: list[dict] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    risk_policy: dict = Field(default_factory=dict)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    scope_rules: list[dict] | None = None
    tags: list[str] | None = None
    risk_policy: dict | None = None
    archived: bool | None = None


class ScopeCheckRequest(BaseModel):
    url: str


def _serialize_workspace(ws: Workspace) -> dict:
    return {
        "id": str(ws.id),
        "name": ws.name,
        "description": ws.description,
        "scope_rules": ws.scope_rules or [],
        "tags": ws.tags or [],
        "risk_policy": ws.risk_policy or {},
        "archived": bool(ws.archived),
        "created_at": ws.created_at.isoformat() if ws.created_at else None,
        "updated_at": ws.updated_at.isoformat() if ws.updated_at else None,
    }


def _db(request: Request):
    db = getattr(request.app.state, "db", None)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    return db


@router.get("")
async def list_workspaces(request: Request, include_archived: bool = False):
    db = _db(request)
    async with db.get_session() as session:
        q = select(Workspace).order_by(Workspace.created_at.desc())
        if not include_archived:
            q = q.where(Workspace.archived.is_(False))
        rows = (await session.execute(q)).scalars().all()
        return [_serialize_workspace(w) for w in rows]


@router.post("")
async def create_workspace(payload: WorkspaceCreate, request: Request):
    db = _db(request)
    async with db.get_session() as session:
        ws = Workspace(
            name=payload.name,
            description=payload.description,
            scope_rules=payload.scope_rules,
            tags=payload.tags,
            risk_policy=payload.risk_policy,
            archived=False,
            updated_at=datetime.now(timezone.utc),
        )
        session.add(ws)
        await session.flush()
        return _serialize_workspace(ws)


@router.get("/{workspace_id}")
async def get_workspace(workspace_id: str, request: Request):
    db = _db(request)
    async with db.get_session() as session:
        ws = await session.get(Workspace, workspace_id)
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return _serialize_workspace(ws)


@router.put("/{workspace_id}")
async def update_workspace(workspace_id: str, payload: WorkspaceUpdate, request: Request):
    db = _db(request)
    async with db.get_session() as session:
        ws = await session.get(Workspace, workspace_id)
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")

        updates = payload.model_dump(exclude_unset=True)
        for k, v in updates.items():
            setattr(ws, k, v)
        ws.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return _serialize_workspace(ws)


@router.delete("/{workspace_id}")
async def archive_workspace(workspace_id: str, request: Request):
    db = _db(request)
    async with db.get_session() as session:
        ws = await session.get(Workspace, workspace_id)
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")
        ws.archived = True
        ws.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return {"status": "archived", "id": workspace_id}


@router.post("/{workspace_id}/scope/check")
async def scope_check(workspace_id: str, payload: ScopeCheckRequest, request: Request):
    db = _db(request)
    async with db.get_session() as session:
        ws = await session.get(Workspace, workspace_id)
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")
        decision = evaluate_scope(payload.url, ws.scope_rules or [])
        return {
            "workspace_id": workspace_id,
            "url": payload.url,
            "allowed": decision.allowed,
            "reason": decision.reason,
            "matched_rule_id": decision.matched_rule_id,
        }

