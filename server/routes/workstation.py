"""REST endpoints for workstation data and intelligence briefs."""

import json
from fastapi import APIRouter, Request, Query
from pydantic import BaseModel

router = APIRouter()


def _page_row(p) -> dict:
    return {
        "id": str(p.id),
        "url": p.url,
        "status_code": p.status_code or 0,
        "content_type": p.content_type or "",
        "title": p.title or "",
        "response_time_ms": p.response_time_ms or 0,
        "links_found": p.links_count or 0,
        "crawl_job_id": str(p.crawl_id) if p.crawl_id else "",
        "crawled_at": p.scraped_at.isoformat() if p.scraped_at else "",
    }


@router.get("/briefs")
async def get_briefs(request: Request):
    """Generate intelligence briefs from crawl + security data. Returns IntelligenceBrief[]."""
    db = request.app.state.db
    if not db:
        return []

    briefs = []

    try:
        async with db.get_session() as session:
            from sqlalchemy import text, select
            from webreaper.database import SecurityFinding, Page

            # Brief 1: Security findings summary per crawl
            result = await session.execute(text("""
                SELECT crawl_id, COUNT(*) as total,
                       SUM(CASE WHEN severity = 'Critical' THEN 1 ELSE 0 END) as critical,
                       SUM(CASE WHEN severity = 'High' THEN 1 ELSE 0 END) as high,
                       MIN(discovered_at) as first_seen
                FROM security_findings
                WHERE crawl_id IS NOT NULL
                GROUP BY crawl_id
                ORDER BY first_seen DESC
                LIMIT 10
            """))
            for row in result.fetchall():
                crawl_id = str(row.crawl_id)
                severity_label = "Critical" if row.critical > 0 else "High" if row.high > 0 else "Medium"
                briefs.append({
                    "id": f"sec-{crawl_id[:8]}",
                    "title": f"Security Scan: {row.total} finding(s)",
                    "summary": f"{row.total} security findings — {row.critical} critical, {row.high} high severity.",
                    "content": json.dumps({"crawl_id": crawl_id, "total": row.total, "critical": row.critical, "high": row.high}),
                    "sources": [],
                    "tags": ["security", severity_label.lower()],
                    "created_at": str(row.first_seen),
                })

            # Brief 2: Crawl summary briefs
            result = await session.execute(text("""
                SELECT c.id, c.start_url, c.pages_crawled, c.started_at, c.completed_at,
                       COUNT(DISTINCT p.id) as pages_in_db
                FROM crawls c
                LEFT JOIN pages p ON p.crawl_id = c.id
                GROUP BY c.id
                ORDER BY c.started_at DESC
                LIMIT 10
            """))
            for row in result.fetchall():
                if not row.start_url:
                    continue
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(row.start_url).netloc
                except Exception:
                    domain = row.start_url
                briefs.append({
                    "id": f"crawl-{str(row.id)[:8]}",
                    "title": f"Crawl: {domain}",
                    "summary": f"Crawled {row.pages_crawled or row.pages_in_db} pages from {row.start_url}.",
                    "content": json.dumps({"crawl_id": str(row.id), "start_url": row.start_url, "pages": row.pages_in_db}),
                    "sources": [row.start_url],
                    "tags": ["crawl", domain],
                    "created_at": str(row.started_at),
                })

            # Brief 3: Articles from blogwatcher (if any)
            try:
                result = await session.execute(text("""
                    SELECT id, title, url, genre, published_at, content_text
                    FROM articles
                    ORDER BY published_at DESC
                    LIMIT 10
                """))
                for row in result.fetchall():
                    briefs.append({
                        "id": f"article-{str(row.id)[:8]}",
                        "title": row.title or "Untitled Article",
                        "summary": (row.content_text or "")[:300],
                        "content": row.content_text or "",
                        "sources": [row.url] if row.url else [],
                        "tags": ["article", row.genre] if row.genre else ["article"],
                        "created_at": str(row.published_at) if row.published_at else "",
                    })
            except Exception:
                pass

    except Exception:
        pass

    # Sort by created_at descending
    briefs.sort(key=lambda b: b.get("created_at") or "", reverse=True)
    return briefs[:20]


@router.get("/results")
async def get_results(
    request: Request,
    limit: int = Query(default=100, le=500),
    crawl_id: str | None = None,
):
    """Recent crawl results for the workstation data table."""
    db = request.app.state.db
    if not db:
        return []

    try:
        async with db.get_session() as session:
            from sqlalchemy import select
            from webreaper.database import Page
            query = select(Page)
            if crawl_id:
                query = query.where(Page.crawl_id == crawl_id)
            query = query.order_by(Page.scraped_at.desc()).limit(limit)
            result = await session.execute(query)
            pages = result.scalars().all()
            return [_page_row(p) for p in pages]
    except Exception:
        return []
