"""REST endpoints for querying crawl results."""

from fastapi import APIRouter, Request, HTTPException, Query

router = APIRouter()


@router.get("/pages")
async def get_pages(
    request: Request,
    crawl_id: str | None = None,
    domain: str | None = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
):
    """Query crawled pages with filters."""
    db = request.app.state.db
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db.get_session() as session:
        from sqlalchemy import select
        from webreaper.database import Page
        query = select(Page)
        if crawl_id:
            query = query.where(Page.crawl_id == crawl_id)
        if domain:
            query = query.where(Page.domain == domain)
        query = query.order_by(Page.scraped_at.desc()).offset(offset).limit(limit)
        result = await session.execute(query)
        pages = result.scalars().all()
        return [
            {
                "id": str(p.id),
                "url": p.url,
                "status_code": p.status_code,
                "title": p.title,
                "word_count": p.word_count,
                "response_time_ms": p.response_time_ms,
                "depth": p.depth,
                "domain": p.domain,
            }
            for p in pages
        ]


@router.get("/search")
async def search_content(
    request: Request,
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, le=100),
):
    """Full-text search across crawled pages."""
    db = request.app.state.db
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db.get_session() as session:
        from sqlalchemy import select
        from webreaper.database import Page
        pattern = f"%{q}%"
        query = (
            select(Page)
            .where(
                (Page.title.ilike(pattern)) | (Page.content_text.ilike(pattern))
            )
            .order_by(Page.scraped_at.desc())
            .limit(limit)
        )
        result = await session.execute(query)
        pages = result.scalars().all()
        return [
            {
                "id": str(p.id),
                "url": p.url,
                "title": p.title or "",
                "snippet": (p.content_text or "")[:200],
                "rank": 1.0,
            }
            for p in pages
        ]
