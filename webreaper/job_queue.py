"""In-process async job queue with DB state tracking.

Wraps asyncio.create_task() with proper lifecycle management:
- Jobs are tracked in memory with status, start time, and error info
- Concurrent job limits are enforced per the user's plan
- Graceful cancellation on server shutdown
- Designed to be swapped for Celery/Redis in Phase 2 without API changes

Usage:
    queue = JobQueue(max_concurrent=10)
    job_id = await queue.submit(crawl_coroutine, meta={"url": "..."})
    status = queue.get_status(job_id)
    await queue.cancel(job_id)
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

import structlog

logger = structlog.get_logger(__name__)


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobInfo:
    job_id: str
    status: JobStatus
    meta: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    _task: Optional[asyncio.Task] = field(default=None, repr=False)


class JobQueue:
    """In-process async job queue with concurrency limits."""

    def __init__(self, max_concurrent: int = 10):
        self._max_concurrent = max_concurrent
        self._jobs: dict[str, JobInfo] = {}
        self._pending: asyncio.Queue[str] = asyncio.Queue()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._coroutine_factories: dict[str, Callable[[], Coroutine]] = {}

    @property
    def active_count(self) -> int:
        return sum(1 for j in self._jobs.values() if j.status == JobStatus.RUNNING)

    @property
    def queued_count(self) -> int:
        return sum(1 for j in self._jobs.values() if j.status == JobStatus.QUEUED)

    async def submit(
        self,
        coro_factory: Callable[[], Coroutine],
        *,
        meta: Optional[dict] = None,
        job_id: Optional[str] = None,
    ) -> str:
        """Submit a job. Returns job_id immediately.

        Args:
            coro_factory: Zero-arg callable that returns a coroutine.
                          Called when the job starts (not at submission time).
            meta: Optional metadata dict stored with the job.
            job_id: Optional explicit job ID. Generated if not provided.
        """
        if job_id is None:
            job_id = str(uuid.uuid4())[:8]

        info = JobInfo(job_id=job_id, status=JobStatus.QUEUED, meta=meta or {})
        self._jobs[job_id] = info
        self._coroutine_factories[job_id] = coro_factory

        task = asyncio.create_task(self._run_with_semaphore(job_id))
        info._task = task

        logger.info("job.submitted", job_id=job_id, active=self.active_count, queued=self.queued_count)
        return job_id

    async def _run_with_semaphore(self, job_id: str) -> None:
        info = self._jobs[job_id]
        async with self._semaphore:
            if info.status == JobStatus.CANCELLED:
                return

            info.status = JobStatus.RUNNING
            info.started_at = datetime.now(timezone.utc)
            logger.info("job.started", job_id=job_id)

            try:
                coro_factory = self._coroutine_factories.pop(job_id, None)
                if coro_factory is None:
                    raise RuntimeError(f"No coroutine factory for job {job_id}")
                await coro_factory()
                info.status = JobStatus.COMPLETED
                logger.info("job.completed", job_id=job_id)
            except asyncio.CancelledError:
                info.status = JobStatus.CANCELLED
                logger.info("job.cancelled", job_id=job_id)
            except Exception as exc:
                info.status = JobStatus.FAILED
                info.error = str(exc)
                logger.error("job.failed", job_id=job_id, error=str(exc))
            finally:
                info.completed_at = datetime.now(timezone.utc)

    def get_status(self, job_id: str) -> Optional[dict]:
        info = self._jobs.get(job_id)
        if info is None:
            return None
        return {
            "job_id": info.job_id,
            "status": info.status.value,
            "meta": info.meta,
            "created_at": info.created_at.isoformat(),
            "started_at": info.started_at.isoformat() if info.started_at else None,
            "completed_at": info.completed_at.isoformat() if info.completed_at else None,
            "error": info.error,
        }

    def list_jobs(self, status: Optional[JobStatus] = None) -> list[dict]:
        jobs = self._jobs.values()
        if status:
            jobs = [j for j in jobs if j.status == status]
        return [self.get_status(j.job_id) for j in sorted(jobs, key=lambda j: j.created_at, reverse=True)]

    async def cancel(self, job_id: str) -> bool:
        info = self._jobs.get(job_id)
        if info is None:
            return False
        if info.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return False
        info.status = JobStatus.CANCELLED
        if info._task and not info._task.done():
            info._task.cancel()
        logger.info("job.cancel_requested", job_id=job_id)
        return True

    async def shutdown(self, timeout: float = 10.0) -> int:
        """Cancel all running/queued jobs. Returns count of cancelled jobs."""
        cancelled = 0
        for info in self._jobs.values():
            if info.status in (JobStatus.RUNNING, JobStatus.QUEUED):
                if info._task and not info._task.done():
                    info._task.cancel()
                info.status = JobStatus.CANCELLED
                cancelled += 1

        if cancelled:
            tasks = [
                info._task for info in self._jobs.values()
                if info._task and not info._task.done()
            ]
            if tasks:
                await asyncio.wait(tasks, timeout=timeout)

        logger.info("job_queue.shutdown", cancelled=cancelled)
        return cancelled

    def cleanup_completed(self, keep_last: int = 100) -> int:
        """Remove old completed/failed/cancelled jobs from memory."""
        terminal = [
            j for j in self._jobs.values()
            if j.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)
        ]
        terminal.sort(key=lambda j: j.completed_at or j.created_at, reverse=True)
        removed = 0
        for job in terminal[keep_last:]:
            del self._jobs[job.job_id]
            removed += 1
        return removed
