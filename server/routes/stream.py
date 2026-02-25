"""SSE endpoints for real-time log and metric streaming."""

import asyncio
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

router = APIRouter()


def _sse_event(event: str, payload: dict):
    """Return a consistent SSE event payload envelope.

    Keeps named SSE events (metrics/log/progress/error) while standardizing the
    JSON body so frontend hooks can parse one shape across streams.
    """
    return {
        "event": event,
        "data": json.dumps(
            {
                "type": event,
                "ts": datetime.now(timezone.utc).isoformat(),
                "payload": payload,
            }
        ),
    }


@router.get("/logs")
async def stream_logs(request: Request):
    """Stream real-time logs via SSE."""
    log_buffer = request.app.state.log_buffer

    async def event_generator():
        last_index = log_buffer.size()
        while True:
            if await request.is_disconnected():
                break
            new_logs = log_buffer.get_since(last_index)
            if new_logs:
                last_index += len(new_logs)
                for log_entry in new_logs:
                    yield _sse_event("log", log_entry)
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())


@router.get("/metrics")
async def stream_metrics(request: Request):
    """Stream real-time metrics via SSE (2s interval)."""
    metrics = request.app.state.metrics

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            snapshot = metrics.snapshot()
            yield _sse_event("metrics", snapshot)
            await asyncio.sleep(2)

    return EventSourceResponse(event_generator())


@router.get("/job/{job_id}")
async def stream_job(request: Request, job_id: str):
    """Stream crawl job progress via SSE."""
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            job = request.app.state.active_jobs.get(job_id)
            if not job:
                yield _sse_event("error", {"error": "Job not found", "job_id": job_id})
                break
            stats = getattr(job, "stats", {}) if isinstance(getattr(job, "stats", None), dict) else {}
            yield _sse_event(
                "progress",
                {
                    "job_id": job_id,
                    "pages_crawled": stats.get("pages_crawled", 0),
                    "pages_failed": stats.get("pages_failed", 0),
                    "queue_size": stats.get("queue_size", 0),
                    "current_url": stats.get("current_url", ""),
                },
            )
            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())
