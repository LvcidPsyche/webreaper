"""Repeater request replay service (MVP)."""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx


class RepeaterService:
    def __init__(self):
        self.default_timeout_ms = 15000
        self.default_follow_redirects = True
        self.max_body_capture_kb = 512

    async def create_tab(
        self,
        db,
        *,
        workspace_id: str | None = None,
        name: str | None = None,
        method: str = "GET",
        url: str,
        headers: dict[str, Any] | None = None,
        body: str | None = None,
        source_transaction_id: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        tab_id = await db.create_repeater_tab(
            {
                "workspace_id": workspace_id,
                "source_transaction_id": source_transaction_id,
                "name": name or f"{method.upper()} {url}",
                "method": method.upper(),
                "url": url,
                "headers": headers or {},
                "body": body,
                "created_at": now,
                "updated_at": now,
            }
        )
        return await db.get_repeater_tab(tab_id)

    async def send_to_repeater_from_transaction(
        self,
        db,
        transaction_id: str,
        *,
        workspace_id: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any] | None:
        tx = await db.get_http_transaction(transaction_id)
        if not tx:
            return None
        return await self.create_tab(
            db,
            workspace_id=workspace_id or tx.get("workspace_id"),
            name=name or f"From {tx.get('source', 'tx')} {tx.get('method', 'GET')} {tx.get('host', '')}",
            method=(tx.get("method") or "GET"),
            url=tx.get("url") or self._rebuild_url(tx),
            headers=tx.get("request_headers") or {},
            body=tx.get("request_body"),
            source_transaction_id=transaction_id,
        )

    async def update_tab(self, db, tab_id: str, **updates) -> dict[str, Any] | None:
        updates = {k: v for k, v in updates.items() if v is not None}
        if not updates:
            return await db.get_repeater_tab(tab_id)
        updates["updated_at"] = datetime.now(timezone.utc)
        if "method" in updates and isinstance(updates["method"], str):
            updates["method"] = updates["method"].upper()
        ok = await db.update_repeater_tab(tab_id, **updates)
        if not ok:
            return None
        return await db.get_repeater_tab(tab_id)

    async def execute_tab(
        self,
        db,
        tab_id: str,
        *,
        timeout_ms: int | None = None,
        follow_redirects: bool | None = None,
    ) -> dict[str, Any] | None:
        tab = await db.get_repeater_tab(tab_id)
        if not tab:
            return None

        timeout_ms = int(timeout_ms or self.default_timeout_ms)
        follow_redirects = self.default_follow_redirects if follow_redirects is None else bool(follow_redirects)
        now = datetime.now(timezone.utc)

        try:
            tx_id, tx_record = await self._perform_request_and_store(
                db,
                workspace_id=tab.get("workspace_id"),
                method=(tab.get("method") or "GET"),
                url=tab.get("url") or "",
                headers=tab.get("headers") or {},
                body=tab.get("body"),
                timeout_ms=timeout_ms,
                follow_redirects=follow_redirects,
            )
            previous = await self._latest_success_run_transaction(db, tab_id)
            diff_summary = self._build_diff(previous, tx_record)
            run_id = await db.create_repeater_run(
                {
                    "repeater_tab_id": tab_id,
                    "workspace_id": tab.get("workspace_id"),
                    "transaction_id": tx_id,
                    "status": "success",
                    "response_status": tx_record.get("response_status"),
                    "duration_ms": tx_record.get("duration_ms"),
                    "timeout_ms": timeout_ms,
                    "follow_redirects": follow_redirects,
                    "diff_summary": diff_summary,
                    "created_at": now,
                }
            )
            await db.update_repeater_tab(tab_id, last_run_at=now, updated_at=now)
            run = await db.get_repeater_run(run_id)
            return {"tab": await db.get_repeater_tab(tab_id), "run": run, "transaction": tx_record}
        except Exception as e:
            run_id = await db.create_repeater_run(
                {
                    "repeater_tab_id": tab_id,
                    "workspace_id": tab.get("workspace_id"),
                    "status": "error",
                    "timeout_ms": timeout_ms,
                    "follow_redirects": follow_redirects,
                    "error": str(e),
                    "created_at": now,
                    "diff_summary": {"baseline": False, "changed": False, "error": True},
                }
            )
            await db.update_repeater_tab(tab_id, last_run_at=now, updated_at=now)
            run = await db.get_repeater_run(run_id)
            return {"tab": await db.get_repeater_tab(tab_id), "run": run, "transaction": None}

    async def _perform_request_and_store(
        self,
        db,
        *,
        workspace_id: str | None,
        method: str,
        url: str,
        headers: dict[str, Any],
        body: str | None,
        timeout_ms: int,
        follow_redirects: bool,
    ) -> tuple[str, dict[str, Any]]:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Repeater URL must be an absolute http/https URL")

        request_headers = {str(k): str(v) for k, v in (headers or {}).items()}
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=timeout_ms / 1000.0, follow_redirects=follow_redirects) as client:
            response = await client.request(method.upper(), url, headers=request_headers, content=body)
        duration_ms = int((time.perf_counter() - start) * 1000)

        truncated = False
        max_chars = self.max_body_capture_kb * 1024

        def _clip(v: Any) -> str | None:
            nonlocal truncated
            if v is None:
                return None
            s = v if isinstance(v, str) else str(v)
            if len(s) > max_chars:
                truncated = True
                return s[:max_chars]
            return s

        tx_record = {
            "workspace_id": workspace_id,
            "source": "repeater",
            "method": method.upper(),
            "scheme": parsed.scheme,
            "host": parsed.netloc,
            "path": parsed.path or "/",
            "query": parsed.query or None,
            "url": url,
            "request_headers": request_headers,
            "request_body": _clip(body),
            "response_status": int(response.status_code),
            "response_headers": dict(response.headers),
            "response_body": _clip(response.text),
            "duration_ms": duration_ms,
            "tags": ["repeater"],
            "intercept_state": "none",
            "truncated": truncated,
        }
        tx_id = await db.save_http_transaction(tx_record)
        tx = await db.get_http_transaction(tx_id) or {"id": tx_id, **tx_record}
        return tx_id, tx

    async def _latest_success_run_transaction(self, db, tab_id: str) -> dict[str, Any] | None:
        runs = await db.list_repeater_runs(tab_id, limit=10)
        for run in runs:
            if (run.get("status") == "success") and run.get("transaction_id"):
                tx = await db.get_http_transaction(str(run["transaction_id"]))
                if tx:
                    return tx
        return None

    def _build_diff(self, previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
        if not previous:
            return {
                "baseline": True,
                "changed": False,
                "status_before": None,
                "status_after": current.get("response_status"),
            }

        prev_body = previous.get("response_body") or ""
        curr_body = current.get("response_body") or ""
        prev_headers = {str(k).lower() for k in ((previous.get("response_headers") or {}).keys())}
        curr_headers = {str(k).lower() for k in ((current.get("response_headers") or {}).keys())}

        prev_hash = hashlib.sha256(prev_body.encode("utf-8", errors="replace")).hexdigest()
        curr_hash = hashlib.sha256(curr_body.encode("utf-8", errors="replace")).hexdigest()
        status_before = previous.get("response_status")
        status_after = current.get("response_status")

        changed = any(
            [
                status_before != status_after,
                prev_hash != curr_hash,
                prev_headers != curr_headers,
            ]
        )
        return {
            "baseline": False,
            "changed": changed,
            "status_changed": status_before != status_after,
            "status_before": status_before,
            "status_after": status_after,
            "body_length_before": len(prev_body),
            "body_length_after": len(curr_body),
            "body_length_delta": len(curr_body) - len(prev_body),
            "response_hash_changed": prev_hash != curr_hash,
            "header_keys_added": sorted(curr_headers - prev_headers),
            "header_keys_removed": sorted(prev_headers - curr_headers),
        }

    @staticmethod
    def _rebuild_url(tx: dict[str, Any]) -> str:
        scheme = tx.get("scheme") or "http"
        host = tx.get("host") or ""
        path = tx.get("path") or "/"
        query = tx.get("query")
        return f"{scheme}://{host}{path}{'?' + query if query else ''}"
