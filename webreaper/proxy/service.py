"""Proxy service lifecycle and transaction persistence (MVP foundation)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse
from uuid import uuid4


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ProxyRuntimeSession:
    id: str
    workspace_id: Optional[str]
    name: str
    host: str = "127.0.0.1"
    port: int = 8080
    intercept_enabled: bool = False
    tls_intercept_enabled: bool = False
    body_capture_limit_kb: int = 512
    include_hosts: list[str] = field(default_factory=list)
    exclude_hosts: list[str] = field(default_factory=list)
    status: str = "stopped"
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProxyService:
    """In-process proxy session manager (adapter-ready for mitmproxy integration)."""

    def __init__(self):
        self._sessions: dict[str, ProxyRuntimeSession] = {}
        self._intercept_queues: dict[str, list[str]] = {}

    async def start_session(self, db, *, workspace_id: str | None = None, name: str | None = None, **config) -> ProxyRuntimeSession:
        session_name = name or f"Proxy {len(self._sessions)+1}"
        started_at_dt = _now_dt()
        started_at = started_at_dt.isoformat()
        sid = await db.create_proxy_session(
            workspace_id=workspace_id,
            name=session_name,
            host=config.get("host", "127.0.0.1"),
            port=config.get("port", 8080),
            intercept_enabled=bool(config.get("intercept_enabled", False)),
            tls_intercept_enabled=bool(config.get("tls_intercept_enabled", False)),
            body_capture_limit_kb=int(config.get("body_capture_limit_kb", 512)),
            include_hosts=config.get("include_hosts", []),
            exclude_hosts=config.get("exclude_hosts", []),
            status="running",
            started_at=started_at_dt,
            updated_at=started_at_dt,
        )
        runtime = ProxyRuntimeSession(
            id=sid,
            workspace_id=workspace_id,
            name=session_name,
            host=config.get("host", "127.0.0.1"),
            port=int(config.get("port", 8080)),
            intercept_enabled=bool(config.get("intercept_enabled", False)),
            tls_intercept_enabled=bool(config.get("tls_intercept_enabled", False)),
            body_capture_limit_kb=int(config.get("body_capture_limit_kb", 512)),
            include_hosts=list(config.get("include_hosts", [])),
            exclude_hosts=list(config.get("exclude_hosts", [])),
            status="running",
            started_at=started_at,
            updated_at=started_at,
        )
        self._sessions[sid] = runtime
        self._intercept_queues.setdefault(sid, [])
        return runtime

    async def stop_session(self, db, session_id: str) -> Optional[ProxyRuntimeSession]:
        runtime = self._sessions.get(session_id)
        stopped_at_dt = _now_dt()
        stopped_at = stopped_at_dt.isoformat()
        if runtime:
            runtime.status = "stopped"
            runtime.stopped_at = stopped_at
            runtime.updated_at = stopped_at
        self._intercept_queues.pop(session_id, None)
        await db.update_proxy_session(session_id, status="stopped", stopped_at=stopped_at_dt, updated_at=stopped_at_dt)
        return runtime or await self._load_runtime_from_db(db, session_id)

    async def set_intercept(self, db, session_id: str, enabled: bool) -> Optional[ProxyRuntimeSession]:
        runtime = self._sessions.get(session_id)
        updated_at_dt = _now_dt()
        updated_at = updated_at_dt.isoformat()
        if runtime:
            runtime.intercept_enabled = enabled
            runtime.updated_at = updated_at
        ok = await db.update_proxy_session(session_id, intercept_enabled=enabled, updated_at=updated_at_dt)
        if not ok:
            return None
        return runtime or await self._load_runtime_from_db(db, session_id)

    async def get_status(self, db, session_id: str) -> Optional[ProxyRuntimeSession]:
        return self._sessions.get(session_id) or await self._load_runtime_from_db(db, session_id)

    async def list_sessions(self, db, workspace_id: str | None = None) -> list[dict]:
        rows = await db.list_proxy_sessions(workspace_id=workspace_id)
        for row in rows:
            sid = str(row.get("id"))
            if sid in self._sessions:
                rt = self._sessions[sid]
                row["status"] = rt.status
                row["intercept_enabled"] = rt.intercept_enabled
                row["updated_at"] = rt.updated_at or row.get("updated_at")
        return rows

    async def record_flow(self, db, *, session_id: str | None = None, workspace_id: str | None = None, source: str = "proxy", request: Dict[str, Any], response: Dict[str, Any] | None = None, tags: list[str] | None = None, intercept_state: str = "none") -> str:
        """Persist a captured flow into transaction storage."""
        url = request.get("url") or ""
        parsed = urlparse(url)
        body_capture_limit_kb = 512
        if session_id and session_id in self._sessions:
            body_capture_limit_kb = self._sessions[session_id].body_capture_limit_kb
            workspace_id = workspace_id or self._sessions[session_id].workspace_id

        request_body = request.get("body")
        response_body = (response or {}).get("body")
        truncated = False
        max_chars = body_capture_limit_kb * 1024

        def _truncate(v):
            nonlocal truncated
            if v is None:
                return None
            s = v if isinstance(v, str) else str(v)
            if len(s) > max_chars:
                truncated = True
                return s[:max_chars]
            return s

        queue_for_intercept = False
        effective_intercept_state = intercept_state
        if session_id:
            runtime = self._sessions.get(session_id) or await self._load_runtime_from_db(db, session_id)
            if runtime and runtime.intercept_enabled and self._host_allowed(runtime, parsed.hostname or parsed.netloc):
                queue_for_intercept = True
                effective_intercept_state = "queued"

        tx_id = await db.save_http_transaction(
            {
                "workspace_id": workspace_id,
                "proxy_session_id": session_id,
                "source": source,
                "method": (request.get("method") or "GET").upper(),
                "scheme": parsed.scheme or "http",
                "host": parsed.netloc,
                "path": parsed.path or "/",
                "query": parsed.query or None,
                "url": url,
                "request_headers": request.get("headers") or {},
                "request_body": _truncate(request_body),
                "response_status": (response or {}).get("status"),
                "response_headers": (response or {}).get("headers") or {},
                "response_body": _truncate(response_body),
                "duration_ms": (response or {}).get("duration_ms"),
                "tags": tags or [],
                "intercept_state": effective_intercept_state,
                "truncated": truncated,
            }
        )
        if queue_for_intercept and session_id:
            self._intercept_queues.setdefault(session_id, []).append(tx_id)
        return tx_id

    async def list_intercept_queue(self, db, session_id: str | None = None, limit: int = 200) -> list[dict]:
        """Return queued intercept transactions, optionally filtered by session."""
        data = await db.list_http_transactions(
            proxy_session_id=session_id,
            intercept_state="queued",
            limit=limit,
            offset=0,
        )
        return data["transactions"]

    async def forward_intercept(self, db, transaction_id: str) -> dict | None:
        return await self._set_intercept_state(db, transaction_id, "forwarded")

    async def drop_intercept(self, db, transaction_id: str) -> dict | None:
        return await self._set_intercept_state(db, transaction_id, "dropped")

    async def edit_intercept(
        self,
        db,
        transaction_id: str,
        *,
        request_patch: dict | None = None,
        response_patch: dict | None = None,
        tags: list[str] | None = None,
    ) -> dict | None:
        tx = await db.get_http_transaction(transaction_id)
        if not tx:
            return None
        updates: dict[str, Any] = {"intercept_state": "edited"}
        if request_patch:
            if "headers" in request_patch:
                updates["request_headers"] = request_patch.get("headers") or {}
            if "body" in request_patch:
                updates["request_body"] = request_patch.get("body")
            if "method" in request_patch and request_patch.get("method"):
                updates["method"] = str(request_patch["method"]).upper()
            if "url" in request_patch and request_patch.get("url"):
                new_url = str(request_patch["url"])
                parsed = urlparse(new_url)
                if parsed.scheme in {"http", "https"} and parsed.netloc:
                    updates["url"] = new_url
                    updates["scheme"] = parsed.scheme
                    updates["host"] = parsed.netloc
                    updates["path"] = parsed.path or "/"
                    updates["query"] = parsed.query or None
        if response_patch:
            if "headers" in response_patch:
                updates["response_headers"] = response_patch.get("headers") or {}
            if "body" in response_patch:
                updates["response_body"] = response_patch.get("body")
            if "status" in response_patch and response_patch.get("status") is not None:
                updates["response_status"] = int(response_patch["status"])

        if tags:
            existing_tags = [str(t) for t in (tx.get("tags") or []) if t]
            updates["tags"] = sorted({*existing_tags, *[str(t) for t in tags if t]})

        ok = await db.update_http_transaction(transaction_id, **updates)
        if not ok:
            return None
        self._remove_from_intercept_queues(transaction_id)
        return await db.get_http_transaction(transaction_id)

    async def _load_runtime_from_db(self, db, session_id: str) -> Optional[ProxyRuntimeSession]:
        row = await db.get_proxy_session(session_id)
        if not row:
            return None
        return ProxyRuntimeSession(
            id=str(row["id"]),
            workspace_id=row.get("workspace_id"),
            name=row.get("name") or "Proxy",
            host=row.get("host") or "127.0.0.1",
            port=int(row.get("port") or 8080),
            intercept_enabled=bool(row.get("intercept_enabled")),
            tls_intercept_enabled=bool(row.get("tls_intercept_enabled")),
            body_capture_limit_kb=int(row.get("body_capture_limit_kb") or 512),
            include_hosts=row.get("include_hosts") or [],
            exclude_hosts=row.get("exclude_hosts") or [],
            status=row.get("status") or "stopped",
            started_at=row.get("started_at").isoformat() if getattr(row.get("started_at"), "isoformat", None) else row.get("started_at"),
            stopped_at=row.get("stopped_at").isoformat() if getattr(row.get("stopped_at"), "isoformat", None) else row.get("stopped_at"),
            updated_at=row.get("updated_at").isoformat() if getattr(row.get("updated_at"), "isoformat", None) else row.get("updated_at"),
        )

    async def _set_intercept_state(self, db, transaction_id: str, state: str) -> dict | None:
        ok = await db.update_http_transaction(transaction_id, intercept_state=state)
        if not ok:
            return None
        self._remove_from_intercept_queues(transaction_id)
        return await db.get_http_transaction(transaction_id)

    def _remove_from_intercept_queues(self, transaction_id: str) -> None:
        for sid, q in self._intercept_queues.items():
            if transaction_id in q:
                self._intercept_queues[sid] = [tid for tid in q if tid != transaction_id]

    @staticmethod
    def _host_allowed(runtime: ProxyRuntimeSession, host: str) -> bool:
        host = (host or "").lower()
        include = [h.lower() for h in (runtime.include_hosts or []) if h]
        exclude = [h.lower() for h in (runtime.exclude_hosts or []) if h]
        if include and not any(host == pat or host.endswith("." + pat) for pat in include):
            return False
        if any(host == pat or host.endswith("." + pat) for pat in exclude):
            return False
        return True
