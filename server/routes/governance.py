"""Governance, profiles, UI preferences, and automation chaining APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from webreaper.database import RunProfile, UIPreference, AutomationRun
from webreaper.governance.policy import list_audit_logs, audit_log

router = APIRouter()


def _db(request: Request):
    db = getattr(request.app.state, 'db', None)
    if not db:
        raise HTTPException(status_code=503, detail='Database not available')
    return db


def _ser(v: Any):
    if isinstance(v, dict):
        return {k: _ser(val) for k, val in v.items()}
    if isinstance(v, list):
        return [_ser(i) for i in v]
    if isinstance(v, datetime):
        return v.isoformat()
    return v


class RunProfileRequest(BaseModel):
    workspace_id: str | None = None
    profile_type: str = Field(pattern='^(crawl|proxy|scan|intruder|automation)$')
    name: str
    description: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)


class UIPreferencePutRequest(BaseModel):
    workspace_id: str | None = None
    user_id: str = 'local'
    page: str
    key: str
    value: dict[str, Any] | list[Any] | str | int | float | bool | None = None


class AutomationRunRequest(BaseModel):
    workspace_id: str | None = None
    profile_id: str | None = None
    name: str | None = None
    chain: list[str] = Field(default_factory=lambda: ['crawl', 'scan', 'report'])
    inputs: dict[str, Any] = Field(default_factory=dict)
    wait: bool = True


@router.get('/audit')
async def audit_logs(request: Request, workspace_id: str | None = None, action: str | None = None, allowed: bool | None = None, limit: int = Query(default=200, le=1000), offset: int = 0):
    rows = await list_audit_logs(_db(request), workspace_id=workspace_id, action=action, allowed=allowed, limit=limit, offset=offset)
    return rows


@router.get('/profiles')
async def list_profiles(request: Request, workspace_id: str | None = None, profile_type: str | None = None):
    db = _db(request)
    async with db.get_session() as session:
        q = select(RunProfile).order_by(RunProfile.updated_at.desc(), RunProfile.created_at.desc())
        if workspace_id:
            q = q.where(RunProfile.workspace_id == workspace_id)
        if profile_type:
            q = q.where(RunProfile.profile_type == profile_type)
        rows = (await session.execute(q)).scalars().all()
        return [_ser({
            'id': str(r.id), 'workspace_id': str(r.workspace_id) if r.workspace_id else None,
            'profile_type': r.profile_type, 'name': r.name, 'description': r.description,
            'settings': r.settings or {}, 'created_at': r.created_at, 'updated_at': r.updated_at,
        }) for r in rows]


@router.post('/profiles')
async def create_profile(payload: RunProfileRequest, request: Request):
    db = _db(request)
    now = datetime.now(timezone.utc)
    async with db.get_session() as session:
        row = RunProfile(
            workspace_id=payload.workspace_id,
            profile_type=payload.profile_type,
            name=payload.name,
            description=payload.description,
            settings=payload.settings,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.flush()
        await audit_log(db, workspace_id=payload.workspace_id, action='profile.create', allowed=True, resource_type='run_profile', resource_id=str(row.id), details={'profile_type': payload.profile_type, 'name': payload.name})
        return _ser({'id': str(row.id), 'workspace_id': payload.workspace_id, 'profile_type': row.profile_type, 'name': row.name, 'description': row.description, 'settings': row.settings or {}, 'created_at': row.created_at, 'updated_at': row.updated_at})


@router.put('/profiles/{profile_id}')
async def update_profile(profile_id: str, payload: RunProfileRequest, request: Request):
    db = _db(request)
    async with db.get_session() as session:
        row = await session.get(RunProfile, profile_id)
        if not row:
            raise HTTPException(status_code=404, detail='Profile not found')
        row.workspace_id = payload.workspace_id
        row.profile_type = payload.profile_type
        row.name = payload.name
        row.description = payload.description
        row.settings = payload.settings
        row.updated_at = datetime.now(timezone.utc)
        await session.flush()
    await audit_log(db, workspace_id=payload.workspace_id, action='profile.update', allowed=True, resource_type='run_profile', resource_id=profile_id, details={'profile_type': payload.profile_type})
    return {'status': 'ok', 'id': profile_id}


@router.delete('/profiles/{profile_id}')
async def delete_profile(profile_id: str, request: Request):
    db = _db(request)
    async with db.get_session() as session:
        row = await session.get(RunProfile, profile_id)
        if not row:
            raise HTTPException(status_code=404, detail='Profile not found')
        wid = str(row.workspace_id) if row.workspace_id else None
        await session.delete(row)
    await audit_log(db, workspace_id=wid, action='profile.delete', allowed=True, resource_type='run_profile', resource_id=profile_id)
    return {'status': 'deleted', 'id': profile_id}


@router.get('/ui-preferences')
async def get_ui_preferences(request: Request, page: str, workspace_id: str | None = None, user_id: str = 'local'):
    db = _db(request)
    async with db.get_session() as session:
        q = select(UIPreference).where(UIPreference.page == page, UIPreference.user_id == user_id)
        if workspace_id:
            q = q.where(UIPreference.workspace_id == workspace_id)
        else:
            q = q.where(UIPreference.workspace_id.is_(None))
        rows = (await session.execute(q)).scalars().all()
        return {r.key: r.value for r in rows}


@router.put('/ui-preferences')
async def put_ui_preference(payload: UIPreferencePutRequest, request: Request):
    db = _db(request)
    now = datetime.now(timezone.utc)
    async with db.get_session() as session:
        q = select(UIPreference).where(
            UIPreference.workspace_id == payload.workspace_id,
            UIPreference.user_id == payload.user_id,
            UIPreference.page == payload.page,
            UIPreference.key == payload.key,
        )
        row = (await session.execute(q)).scalar_one_or_none()
        if not row:
            row = UIPreference(
                workspace_id=payload.workspace_id,
                user_id=payload.user_id,
                page=payload.page,
                key=payload.key,
                value=payload.value,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
        else:
            row.value = payload.value
            row.updated_at = now
        await session.flush()
    return {'status': 'ok', 'page': payload.page, 'key': payload.key}


@router.get('/automation/runs')
async def list_automation_runs(request: Request, workspace_id: str | None = None, limit: int = Query(default=100, le=1000)):
    db = _db(request)
    async with db.get_session() as session:
        q = select(AutomationRun).order_by(AutomationRun.created_at.desc()).limit(limit)
        if workspace_id:
            q = q.where(AutomationRun.workspace_id == workspace_id)
        rows = (await session.execute(q)).scalars().all()
        return [_ser({'id': str(r.id), 'workspace_id': str(r.workspace_id) if r.workspace_id else None, 'profile_id': str(r.profile_id) if r.profile_id else None, 'name': r.name, 'chain': r.chain or [], 'inputs': r.inputs or {}, 'outputs': r.outputs or {}, 'status': r.status, 'started_at': r.started_at, 'completed_at': r.completed_at, 'created_at': r.created_at, 'updated_at': r.updated_at}) for r in rows]


@router.post('/automation/run')
async def run_automation(payload: AutomationRunRequest, request: Request):
    db = _db(request)
    now = datetime.now(timezone.utc)
    async with db.get_session() as session:
        row = AutomationRun(
            workspace_id=payload.workspace_id,
            profile_id=payload.profile_id,
            name=payload.name or 'Automation Chain',
            chain=payload.chain,
            inputs=payload.inputs,
            outputs={},
            status='queued',
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.flush()
        run_id = str(row.id)

    if payload.wait:
        outputs: dict[str, Any] = {'steps': []}
        status = 'completed'
        started = datetime.now(timezone.utc)
        try:
            for step in payload.chain:
                step_lower = step.lower()
                if step_lower == 'crawl':
                    target_url = payload.inputs.get('target_url') or payload.inputs.get('url')
                    outputs['steps'].append({'step': 'crawl', 'status': 'simulated', 'target_url': target_url})
                elif step_lower in {'extract', 'endpoint_inventory'}:
                    crawl_id = payload.inputs.get('crawl_id')
                    outputs['steps'].append({'step': step_lower, 'status': 'simulated', 'crawl_id': crawl_id})
                elif step_lower == 'scan':
                    outputs['steps'].append({'step': 'scan', 'status': 'simulated', 'mode': payload.inputs.get('scan_mode', 'passive')})
                elif step_lower == 'report':
                    outputs['steps'].append({'step': 'report', 'status': 'ready', 'export_formats': ['json', 'markdown']})
                else:
                    outputs['steps'].append({'step': step_lower, 'status': 'skipped', 'reason': 'unknown step'})
            outputs['summary'] = {
                'completed_steps': sum(1 for s in outputs['steps'] if s.get('status') in {'simulated', 'ready'}),
                'total_steps': len(payload.chain),
            }
        except Exception as e:
            status = 'failed'
            outputs['error'] = str(e)
        async with db.get_session() as session:
            row = await session.get(AutomationRun, run_id)
            if row:
                row.status = status
                row.started_at = started
                row.completed_at = datetime.now(timezone.utc)
                row.updated_at = datetime.now(timezone.utc)
                row.outputs = outputs
                await session.flush()

    await audit_log(db, workspace_id=payload.workspace_id, action='automation.run', allowed=True, resource_type='automation_run', resource_id=run_id, details={'chain': payload.chain, 'wait': payload.wait})

    async with db.get_session() as session:
        row = await session.get(AutomationRun, run_id)
        return _ser({'id': str(row.id), 'workspace_id': str(row.workspace_id) if row.workspace_id else None, 'profile_id': str(row.profile_id) if row.profile_id else None, 'name': row.name, 'chain': row.chain or [], 'inputs': row.inputs or {}, 'outputs': row.outputs or {}, 'status': row.status, 'started_at': row.started_at, 'completed_at': row.completed_at, 'created_at': row.created_at, 'updated_at': row.updated_at})
