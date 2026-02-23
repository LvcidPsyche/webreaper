"""REST endpoints for workstation data, briefs, and canvas."""

import json
import uuid
from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


class PinRequest(BaseModel):
    category: str | None = None
    content: dict
    position_x: float = 0
    position_y: float = 0


def _page_row(p) -> dict:
    return {
        "id": str(p.id),
        "url": p.url,
        "status_code": p.status_code or 0,
        "content_type": p.content_type or "",
        "title": p.title or "",
        "response_time_ms": p.response_time_ms or 0,
        "links_found": p.links_count or 0,
        "crawl_job_id": p.crawl_id or "",
        "crawled_at": p.scraped_at.isoformat() if p.scraped_at else "",
    }


@router.get("/briefs")
async def get_briefs(request: Request):
    """Get recent intelligence briefs — returns IntelligenceBrief[]."""
    db = request.app.state.db
    if not db:
        return []

    try:
        async with db.get_session() as session:
            from sqlalchemy import text
            result = await session.execute(text("""
                SELECT id, type, brief, status, results, created_at
                FROM missions
                ORDER BY created_at DESC
                LIMIT 20
            """))
            rows = result.fetchall()
            return [
                {
                    "id": str(r.id),
                    "title": (r.brief or "")[:80],
                    "summary": r.brief or "",
                    "content": json.dumps(r.results) if r.results else "",
                    "sources": [],
                    "tags": [r.type] if r.type else [],
                    "created_at": str(r.created_at),
                }
                for r in rows
            ]
    except Exception:
        return []


@router.get("/results")
async def get_results(
    request: Request,
    limit: int = Query(default=50, le=200),
):
    """Recent crawl results for the workstation data table."""
    db = request.app.state.db
    if not db:
        return []

    try:
        async with db.get_session() as session:
            from sqlalchemy import select
            from webreaper.database import Page
            query = select(Page).order_by(Page.scraped_at.desc()).limit(limit)
            result = await session.execute(query)
            pages = result.scalars().all()
            return [_page_row(p) for p in pages]
    except Exception:
        return []


@router.get("/canvas")
async def get_canvas(request: Request):
    """Get workstation canvas pins."""
    db = request.app.state.db
    if not db:
        return {"pins": []}

    try:
        async with db.get_session() as session:
            from sqlalchemy import text
            result = await session.execute(text("""
                SELECT id, category, content, position_x, position_y, created_at
                FROM workstation_pins
                ORDER BY created_at DESC
            """))
            rows = result.fetchall()
            return {
                "pins": [
                    {
                        "id": str(r.id),
                        "category": r.category,
                        "content": r.content,
                        "position_x": r.position_x,
                        "position_y": r.position_y,
                    }
                    for r in rows
                ]
            }
    except Exception:
        return {"pins": []}


@router.post("/canvas/pin")
async def add_pin(pin: PinRequest, request: Request):
    """Add a pin to the workstation canvas."""
    db = request.app.state.db
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        async with db.get_session() as session:
            from sqlalchemy import text
            pin_id = str(uuid.uuid4())
            await session.execute(
                text("""
                    INSERT INTO workstation_pins (id, category, content, position_x, position_y)
                    VALUES (:id, :category, :content, :x, :y)
                """),
                {
                    "id": pin_id,
                    "category": pin.category,
                    "content": json.dumps(pin.content),
                    "x": pin.position_x,
                    "y": pin.position_y,
                }
            )
            await session.commit()
            return {"id": pin_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
