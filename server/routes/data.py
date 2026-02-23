"""Data Explorer API — browse crawl results, pages, and export."""

import csv
import io
import json
import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text

router = APIRouter()
logger = logging.getLogger("webreaper.data")


def _db(request: Request):
    db = getattr(request.app.state, "db", None)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    return db


# ── Crawl list ───────────────────────────────────────────────


@router.get("/crawls")
async def list_crawls(request: Request):
    """List all crawls with summary stats, newest first."""
    db = _db(request)
    async with db.get_session() as session:
        result = await session.execute(text("""
            SELECT
                id, target_url, status, genre,
                pages_crawled, pages_failed, total_bytes,
                external_links, requests_per_sec,
                started_at, completed_at
            FROM crawls
            ORDER BY started_at DESC
            LIMIT 100
        """))
        rows = [dict(r._mapping) for r in result.fetchall()]

    # Coerce datetime objects to ISO strings for JSON serialisation
    for r in rows:
        for k in ("started_at", "completed_at"):
            v = r.get(k)
            if v is not None and not isinstance(v, str):
                r[k] = v.isoformat()
    return rows


# ── Page list ────────────────────────────────────────────────


@router.get("/pages")
async def list_pages(
    request: Request,
    crawl_id: str = Query(..., description="Crawl UUID to scope results"),
    search: Optional[str] = Query(None, description="Filter by URL or title substring"),
    status_code: Optional[int] = Query(None, description="Filter by HTTP status code"),
    sort: str = Query("scraped_at", description="Column to sort by"),
    order: str = Query("desc", description="asc or desc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """Return paginated, filterable pages for a crawl."""
    db = _db(request)

    allowed_sort = {
        "url", "status_code", "title", "response_time_ms",
        "word_count", "links_count", "external_links_count",
        "depth", "scraped_at",
    }
    sort_col = sort if sort in allowed_sort else "scraped_at"
    order_dir = "ASC" if order.lower() == "asc" else "DESC"

    where_clauses = ["crawl_id = :crawl_id"]
    params: dict = {"crawl_id": crawl_id, "offset": (page - 1) * per_page, "limit": per_page}

    if search:
        where_clauses.append("(url LIKE :search OR title LIKE :search)")
        params["search"] = f"%{search}%"
    if status_code is not None:
        where_clauses.append("status_code = :status_code")
        params["status_code"] = status_code

    where = " AND ".join(where_clauses)

    async with db.get_session() as session:
        count_result = await session.execute(
            text(f"SELECT COUNT(*) FROM pages WHERE {where}"),
            {k: v for k, v in params.items() if k not in ("offset", "limit")},
        )
        total = count_result.scalar() or 0

        rows_result = await session.execute(
            text(f"""
                SELECT
                    id, url, domain, path, status_code, title,
                    response_time_ms, word_count, links_count,
                    external_links_count, depth, scraped_at, h1
                FROM pages
                WHERE {where}
                ORDER BY {sort_col} {order_dir}
                LIMIT :limit OFFSET :offset
            """),
            params,
        )
        rows = [dict(r._mapping) for r in rows_result.fetchall()]

    for r in rows:
        v = r.get("scraped_at")
        if v is not None and not isinstance(v, str):
            r["scraped_at"] = v.isoformat()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": rows,
    }


# ── Page detail ──────────────────────────────────────────────


@router.get("/pages/{page_id}")
async def get_page(request: Request, page_id: str):
    """Full detail for a single crawled page."""
    db = _db(request)
    async with db.get_session() as session:
        result = await session.execute(
            text("""
                SELECT
                    id, crawl_id, url, canonical_url, domain, path,
                    status_code, content_type, response_time_ms,
                    title, meta_description, word_count,
                    headings, h1, h2s,
                    links_count, external_links_count, images_count,
                    headings_count, depth, scraped_at,
                    response_headers
                FROM pages WHERE id = :id
            """),
            {"id": page_id},
        )
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Page not found")

    data = dict(row._mapping)
    v = data.get("scraped_at")
    if v is not None and not isinstance(v, str):
        data["scraped_at"] = v.isoformat()

    # headings and response_headers may already be dicts/lists (JSON columns)
    for col in ("headings", "h2s", "response_headers"):
        val = data.get(col)
        if isinstance(val, str):
            try:
                data[col] = json.loads(val)
            except Exception:
                pass

    return data


# ── Stats / chart data ───────────────────────────────────────


@router.get("/stats/{crawl_id}")
async def crawl_stats(request: Request, crawl_id: str):
    """Aggregate stats for chart rendering."""
    db = _db(request)
    async with db.get_session() as session:
        # Status code distribution
        sc_result = await session.execute(
            text("""
                SELECT status_code, COUNT(*) as count
                FROM pages
                WHERE crawl_id = :cid
                GROUP BY status_code
                ORDER BY count DESC
            """),
            {"cid": crawl_id},
        )
        status_codes = [dict(r._mapping) for r in sc_result.fetchall()]

        # Top domains by page count
        domain_result = await session.execute(
            text("""
                SELECT domain, COUNT(*) as count
                FROM pages
                WHERE crawl_id = :cid
                GROUP BY domain
                ORDER BY count DESC
                LIMIT 10
            """),
            {"cid": crawl_id},
        )
        top_domains = [dict(r._mapping) for r in domain_result.fetchall()]

        # Response time distribution buckets (ms)
        rt_result = await session.execute(
            text("""
                SELECT
                    CASE
                        WHEN response_time_ms < 200  THEN '<200ms'
                        WHEN response_time_ms < 500  THEN '200-500ms'
                        WHEN response_time_ms < 1000 THEN '500ms-1s'
                        WHEN response_time_ms < 2000 THEN '1s-2s'
                        ELSE '>2s'
                    END as bucket,
                    COUNT(*) as count
                FROM pages
                WHERE crawl_id = :cid AND response_time_ms IS NOT NULL
                GROUP BY bucket
                ORDER BY MIN(response_time_ms)
            """),
            {"cid": crawl_id},
        )
        response_times = [dict(r._mapping) for r in rt_result.fetchall()]

        # Depth distribution
        depth_result = await session.execute(
            text("""
                SELECT depth, COUNT(*) as count
                FROM pages
                WHERE crawl_id = :cid
                GROUP BY depth
                ORDER BY depth
            """),
            {"cid": crawl_id},
        )
        depth_dist = [dict(r._mapping) for r in depth_result.fetchall()]

        # Aggregate totals
        agg_result = await session.execute(
            text("""
                SELECT
                    COUNT(*) as total_pages,
                    COUNT(DISTINCT domain) as total_domains,
                    AVG(response_time_ms) as avg_response_ms,
                    SUM(word_count) as total_words,
                    SUM(links_count) as total_internal_links,
                    SUM(external_links_count) as total_external_links
                FROM pages WHERE crawl_id = :cid
            """),
            {"cid": crawl_id},
        )
        agg = dict(agg_result.fetchone()._mapping)
        # Round floats
        if agg.get("avg_response_ms") is not None:
            agg["avg_response_ms"] = round(agg["avg_response_ms"], 1)

    return {
        "status_codes": status_codes,
        "top_domains": top_domains,
        "response_times": response_times,
        "depth_distribution": depth_dist,
        "totals": agg,
    }


# ── Export ───────────────────────────────────────────────────


@router.get("/export/{crawl_id}")
async def export_crawl(
    request: Request,
    crawl_id: str,
    fmt: str = Query("csv", description="csv or json"),
):
    """Download all pages for a crawl as CSV or JSON."""
    db = _db(request)
    async with db.get_session() as session:
        result = await session.execute(
            text("""
                SELECT
                    url, domain, path, status_code, title,
                    h1, meta_description, word_count,
                    links_count, external_links_count,
                    response_time_ms, depth, scraped_at
                FROM pages
                WHERE crawl_id = :cid
                ORDER BY scraped_at ASC
            """),
            {"cid": crawl_id},
        )
        rows = [dict(r._mapping) for r in result.fetchall()]

    for r in rows:
        v = r.get("scraped_at")
        if v is not None and not isinstance(v, str):
            r["scraped_at"] = v.isoformat()

    if fmt == "json":
        content = json.dumps(rows, indent=2, default=str)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="crawl-{crawl_id[:8]}.json"'},
        )

    # CSV
    if not rows:
        raise HTTPException(status_code=404, detail="No pages found for this crawl")

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="crawl-{crawl_id[:8]}.csv"'},
    )
