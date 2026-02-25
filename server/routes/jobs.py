"""REST endpoints for crawl job management."""

import asyncio
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from webreaper.config import Config
from webreaper.crawler import Crawler
from webreaper.license import get_tier, get_page_limit, is_admin
from webreaper.usage import can_crawl, add_pages

router = APIRouter()


def _make_metrics_callback(metrics, active_jobs_ref):
    """Build a crawler metrics callback that updates MetricsService gauges/counters."""
    def _on_metrics(event: dict):
        if not metrics:
            return
        page_delta = int(event.get("page_delta", 0) or 0)
        fail_delta = int(event.get("fail_delta", 0) or 0)
        bytes_delta = int(event.get("bytes_delta", 0) or 0)
        if page_delta:
            metrics.increment("pages_crawled", page_delta)
        if fail_delta:
            metrics.increment("pages_failed", fail_delta)
        if bytes_delta:
            metrics.increment("bytes_downloaded", bytes_delta)

        status_code = event.get("status_code")
        if isinstance(status_code, int):
            metrics.increment_status(status_code)

        metrics.set_gauge("queue_depth", float(event.get("queue_size", 0) or 0))
        metrics.set_gauge("requests_per_second", float(event.get("requests_per_second", 0.0) or 0.0))
        if hasattr(metrics, "set_counter"):
            metrics.set_counter("active_jobs", len(active_jobs_ref))
    return _on_metrics


class CrawlJobRequest(BaseModel):
    urls: list[str]
    workspace_id: str | None = None
    depth: int = 3
    max_pages: int = 1000
    concurrency: int = 100
    stealth: bool = False
    tor: bool = False
    rate_limit: float = 10.0
    respect_robots: bool = False
    genre: str | None = None
    security_scan: bool = False
    browser_render: bool = False
    browser_fallback_to_http: bool = True


class SimpleJobRequest(BaseModel):
    """Single-URL form as sent by the frontend Jobs page."""
    url: str
    depth: int = 3
    concurrency: int = 10
    stealth: bool = False
    security_scan: bool = False
    workspace_id: str | None = None
    browser_render: bool = False


class JobResponse(BaseModel):
    job_id: str
    status: str
    target_urls: list[str]


@router.post("", response_model=JobResponse)
async def start_crawl_simple(req: SimpleJobRequest, request: Request):
    """Start a crawl from the frontend form (single URL)."""
    full = CrawlJobRequest(
        urls=[req.url], depth=req.depth, concurrency=req.concurrency,
        stealth=req.stealth, security_scan=req.security_scan,
        workspace_id=req.workspace_id, browser_render=req.browser_render,
    )
    return await start_crawl(full, request)


@router.post("/start", response_model=JobResponse)
async def start_crawl(req: CrawlJobRequest, request: Request):
    """Start a new crawl job."""
    effective_max = req.max_pages
    if not is_admin():
        tier = get_tier()
        page_limit = get_page_limit()
        allowed, reason = can_crawl(req.max_pages, page_limit)
        if not allowed:
            raise HTTPException(status_code=402, detail=f"License limit: {reason}")
        if page_limit is not None:
            from webreaper.usage import get_usage
            used = get_usage().get("pages_crawled", 0)
            remaining = page_limit - used
            effective_max = min(req.max_pages, remaining)

    effective_max = min(effective_max, 50_000)

    job_id = str(uuid.uuid4())[:8]
    config = Config()
    config.crawler.max_depth = req.depth
    config.crawler.max_pages = effective_max
    config.crawler.concurrency = req.concurrency
    config.crawler.rate_limit = req.rate_limit
    config.crawler.respect_robots = req.respect_robots
    config.stealth.enabled = req.stealth
    config.stealth.tor_enabled = req.tor
    config.browser.enabled = req.browser_render
    config.browser.fallback_to_http = req.browser_fallback_to_http
    if req.genre:
        config.__dict__['genre'] = req.genre

    db = request.app.state.db
    crawler = Crawler(config, db_manager=db)
    crawler._workspace_id = req.workspace_id
    crawler._metrics_callback = _make_metrics_callback(
        getattr(request.app.state, "metrics", None),
        request.app.state.active_jobs,
    )

    async def run_job():
        try:
            await crawler.crawl(req.urls, callback=None)
            add_pages(crawler.stats["pages_crawled"])
            # Optional post-crawl security scan
            if req.security_scan:
                await _run_post_crawl_scan(req.urls[0], db, job_id, request)
        except Exception as e:
            request.app.state.log_buffer.add("error", f"Job {job_id} failed: {e}")
            if db and getattr(crawler, "_crawl_id", None):
                try:
                    crawler.stats["total_time"] = 0
                    crawler.stats["crawl_status"] = "failed"
                    await db.complete_crawl(crawler._crawl_id, crawler.stats)
                except Exception:
                    pass
        finally:
            request.app.state.active_jobs.pop(job_id, None)
            metrics = getattr(request.app.state, "metrics", None)
            if metrics and hasattr(metrics, "set_counter"):
                metrics.set_counter("active_jobs", len(request.app.state.active_jobs))

    crawler._meta = {
        "url": req.urls[0] if req.urls else "",
        "depth": req.depth,
        "concurrency": req.concurrency,
        "stealth": req.stealth,
        "security_scan": req.security_scan,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "workspace_id": req.workspace_id,
        "browser_render": req.browser_render,
    }
    request.app.state.active_jobs[job_id] = crawler
    metrics = getattr(request.app.state, "metrics", None)
    if metrics and hasattr(metrics, "set_counter"):
        metrics.set_counter("active_jobs", len(request.app.state.active_jobs))
    asyncio.create_task(run_job())

    return JobResponse(job_id=job_id, status="running", target_urls=req.urls)


async def _run_post_crawl_scan(url: str, db, job_id: str, request) -> None:
    """Run security scan against crawled URL and persist findings."""
    try:
        from webreaper.fetcher import StealthFetcher
        from webreaper.config import StealthConfig
        from webreaper.modules.security import SecurityScanner
        from webreaper.database import SecurityFinding

        request.app.state.log_buffer.add("info", f"Job {job_id}: running post-crawl security scan on {url}")
        fetcher_config = StealthConfig()
        async with StealthFetcher(fetcher_config) as fetcher:
            status, headers, body = await fetcher.fetch(url)

        scanner = SecurityScanner(auto_attack=False)
        findings = scanner.scan(url, headers, body, [])

        if db and findings:
            async with db.get_session() as session:
                from datetime import datetime, timezone
                for f in findings:
                    sf = SecurityFinding(
                        id=uuid.uuid4(),
                        url=url,
                        finding_type=f.get("type", "unknown"),
                        severity=f.get("severity", "info").capitalize(),
                        title=f.get("title", ""),
                        evidence=f.get("evidence", ""),
                        parameter=f.get("parameter"),
                        remediation=f.get("remediation"),
                        discovered_at=datetime.now(timezone.utc),
                    )
                    session.add(sf)
                await session.commit()
        request.app.state.log_buffer.add(
            "info", f"Job {job_id}: security scan complete — {len(findings)} finding(s)"
        )
    except Exception as e:
        request.app.state.log_buffer.add("warning", f"Job {job_id}: security scan failed: {e}")


@router.get("", include_in_schema=True)
async def list_jobs(request: Request):
    """List active and recent jobs as a flat CrawlJob list."""
    now = datetime.now(timezone.utc).isoformat()
    result = []

    for jid, crawler in request.app.state.active_jobs.items():
        stats = getattr(crawler, 'stats', {}) or {}
        meta = getattr(crawler, '_meta', {}) or {}
        result.append({
            "id": jid,
            "url": meta.get("url", ""),
            "status": "running",
            "depth": meta.get("depth", 3),
            "concurrency": meta.get("concurrency", 10),
            "stealth": meta.get("stealth", False),
            "security_scan": meta.get("security_scan", False),
            "browser_render": meta.get("browser_render", False),
            "pages_crawled": stats.get("pages_crawled", 0),
            "queue_size": stats.get("queue_size", 0),
            "current_url": stats.get("current_url", ""),
            "workspace_id": meta.get("workspace_id"),
            "pages_total": None,
            "started_at": meta.get("started_at"),
            "completed_at": None,
            "error": None,
            "created_at": meta.get("started_at", now),
        })

    db = request.app.state.db
    if db:
        try:
            rows = await db.get_crawl_stats()
            active_ids = {j["id"] for j in result}
            for r in rows:
                rid = str(r.get("id", ""))
                if rid in active_ids:
                    continue
                result.append({
                    "id": rid,
                    # compatibility with DB helper returning target_url
                    "url": r.get("target_url", r.get("start_url", "")),
                    "status": r.get("status", "completed"),
                    "depth": r.get("max_depth", 3),
                    "concurrency": 10,
                    "stealth": False,
                    "security_scan": False,
                    "browser_render": False,
                    "pages_crawled": r.get("pages_crawled", 0),
                    "workspace_id": r.get("workspace_id"),
                    "pages_total": r.get("pages_total"),
                    "started_at": r.get("started_at"),
                    "completed_at": r.get("completed_at"),
                    "error": r.get("error"),
                    "created_at": r.get("started_at"),
                })
        except Exception:
            pass

    return result


@router.delete("/{job_id}")
async def stop_job(job_id: str, request: Request):
    """Stop a running crawl job."""
    job = request.app.state.active_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job._stop_flag = True
    return {"status": "stopping", "job_id": job_id}


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, request: Request):
    """Cancel a running job (POST alias for DELETE)."""
    return await stop_job(job_id, request)
