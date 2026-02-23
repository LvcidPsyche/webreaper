"""REST endpoints for crawl job management."""

import asyncio
import uuid
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from webreaper.config import Config
from webreaper.crawler import Crawler
from webreaper.license import get_tier, get_page_limit, is_admin
from webreaper.usage import can_crawl, add_pages

router = APIRouter()


class CrawlJobRequest(BaseModel):
    urls: list[str]
    depth: int = 3
    max_pages: int = 1000
    concurrency: int = 100
    stealth: bool = False
    tor: bool = False
    rate_limit: float = 10.0
    respect_robots: bool = False
    genre: str | None = None


class JobResponse(BaseModel):
    job_id: str
    status: str
    target_urls: list[str]


@router.post("/start", response_model=JobResponse)
async def start_crawl(req: CrawlJobRequest, request: Request):
    """Start a new crawl job."""
    # --- License enforcement (skipped in admin mode) ---
    effective_max = req.max_pages
    if not is_admin():
        tier = get_tier()
        page_limit = get_page_limit()
        allowed, reason = can_crawl(req.max_pages, page_limit)
        if not allowed:
            raise HTTPException(
                status_code=402,
                detail=f"License limit: {reason}",
            )
        # Cap max_pages at remaining allowance (LITE tier)
        if page_limit is not None:
            from webreaper.usage import get_usage
            used = get_usage().get("pages_crawled", 0)
            remaining = page_limit - used
            effective_max = min(req.max_pages, remaining)

    job_id = str(uuid.uuid4())[:8]
    config = Config()
    config.crawler.max_depth = req.depth
    config.crawler.max_pages = effective_max
    config.crawler.concurrency = req.concurrency
    config.crawler.rate_limit = req.rate_limit
    config.crawler.respect_robots = req.respect_robots
    config.stealth.enabled = req.stealth
    config.stealth.tor_enabled = req.tor
    if req.genre:
        config.__dict__['genre'] = req.genre

    db = request.app.state.db
    crawler = Crawler(config, db_manager=db)

    async def run_job():
        try:
            results = await crawler.crawl(req.urls, callback=None)
            # Track usage after crawl completes
            add_pages(len(results))
        except Exception as e:
            request.app.state.log_buffer.add("error", f"Job {job_id} failed: {e}")
        finally:
            request.app.state.active_jobs.pop(job_id, None)

    request.app.state.active_jobs[job_id] = crawler
    asyncio.create_task(run_job())

    return JobResponse(job_id=job_id, status="running", target_urls=req.urls)


@router.get("", include_in_schema=True)
async def list_jobs(request: Request):
    """List active and recent jobs."""
    active = [
        {"job_id": jid, "status": "running"}
        for jid in request.app.state.active_jobs
    ]
    db = request.app.state.db
    recent = []
    if db:
        try:
            recent = await db.get_crawl_stats()
        except Exception:
            pass
    return {"active": active, "recent": recent}


@router.delete("/{job_id}")
async def stop_job(job_id: str, request: Request):
    """Stop a running crawl job."""
    job = request.app.state.active_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job._stop_flag = True
    return {"status": "stopping", "job_id": job_id}
