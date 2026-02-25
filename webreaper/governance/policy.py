from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from webreaper.database import Workspace, AuditLog


@dataclass
class PolicyDecision:
    allowed: bool
    rule: str
    reason: str


DEFAULTS = {
    'allow_active_scan': True,
    'allow_intruder': True,
    'allow_intercept_edit': True,
    'require_ack_active_scan': False,
    'require_ack_intruder': False,
    'require_ack_intercept_edit': False,
}


ACTION_MAP = {
    'security.active_scan': ('allow_active_scan', 'require_ack_active_scan'),
    'intruder.start': ('allow_intruder', 'require_ack_intruder'),
    'proxy.intercept_edit': ('allow_intercept_edit', 'require_ack_intercept_edit'),
}


async def get_workspace_policy(db, workspace_id: str | None) -> dict[str, Any]:
    if not workspace_id:
        return dict(DEFAULTS)
    async with db.get_session() as session:
        ws = await session.get(Workspace, workspace_id)
        if not ws:
            return dict(DEFAULTS)
        policy = dict(DEFAULTS)
        policy.update(ws.risk_policy or {})
        return policy


async def evaluate_policy(db, workspace_id: str | None, action: str, *, acknowledge: bool = False) -> PolicyDecision:
    policy = await get_workspace_policy(db, workspace_id)
    allow_key, ack_key = ACTION_MAP.get(action, (None, None))
    if allow_key and not bool(policy.get(allow_key, DEFAULTS.get(allow_key, True))):
        return PolicyDecision(False, allow_key, f'Policy blocks {action}')
    if ack_key and bool(policy.get(ack_key, False)) and not acknowledge:
        return PolicyDecision(False, ack_key, f'Explicit acknowledgment required for {action}')
    return PolicyDecision(True, 'allow', 'Allowed by policy')


async def audit_log(
    db,
    *,
    workspace_id: str | None,
    action: str,
    allowed: bool,
    resource_type: str | None = None,
    resource_id: str | None = None,
    actor: str = 'api',
    policy_rule: str | None = None,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
) -> str:
    if not db.async_session_maker:
        await db.init_async()
    async with db.get_session() as session:
        row = AuditLog(
            workspace_id=workspace_id,
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            allowed=allowed,
            policy_rule=policy_rule,
            reason=reason,
            details=details or {},
            created_at=datetime.now(timezone.utc),
        )
        session.add(row)
        await session.flush()
        return str(row.id)


async def list_audit_logs(db, *, workspace_id: str | None = None, action: str | None = None, allowed: bool | None = None, limit: int = 200, offset: int = 0):
    async with db.get_session() as session:
        q = select(AuditLog).order_by(AuditLog.created_at.desc())
        if workspace_id:
            q = q.where(AuditLog.workspace_id == workspace_id)
        if action:
            q = q.where(AuditLog.action == action)
        if allowed is not None:
            q = q.where(AuditLog.allowed.is_(allowed))
        q = q.offset(offset).limit(limit)
        rows = (await session.execute(q)).scalars().all()
        return [
            {
                'id': str(r.id),
                'workspace_id': str(r.workspace_id) if r.workspace_id else None,
                'actor': r.actor,
                'action': r.action,
                'resource_type': r.resource_type,
                'resource_id': r.resource_id,
                'allowed': bool(r.allowed),
                'policy_rule': r.policy_rule,
                'reason': r.reason,
                'details': r.details or {},
                'created_at': r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
