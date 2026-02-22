"""REST endpoints for workstation data, briefs, and canvas."""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter()


class PinRequest(BaseModel):
    category: str | None = None
    content: dict
    position_x: float = 0
    position_y: float = 0


@router.get("/briefs")
async def get_briefs(request: Request):
    """Get recent intelligence briefs from missions."""
    db = request.app.state.db
    if not db:
        return {"briefs": []}

    async with db.get_session() as session:
        from sqlalchemy import text
        result = await session.execute(text("""
            SELECT id, type, brief, status, results, created_at, completed_at
            FROM missions
            ORDER BY created_at DESC
            LIMIT 20
        """))
        rows = result.fetchall()
        return {
            "briefs": [
                {
                    "id": str(r.id),
                    "type": r.type,
                    "brief": r.brief,
                    "status": r.status,
                    "results": r.results,
                    "created_at": str(r.created_at),
                }
                for r in rows
            ]
        }


@router.get("/canvas")
async def get_canvas(request: Request):
    """Get workstation canvas pins."""
    db = request.app.state.db
    if not db:
        return {"pins": []}

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


@router.post("/canvas/pin")
async def add_pin(pin: PinRequest, request: Request):
    """Add a pin to the workstation canvas."""
    db = request.app.state.db
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db.get_session() as session:
        from sqlalchemy import text
        result = await session.execute(
            text("""
                INSERT INTO workstation_pins (category, content, position_x, position_y)
                VALUES (:category, :content::jsonb, :x, :y)
                RETURNING id
            """),
            {
                "category": pin.category,
                "content": str(pin.content),
                "x": pin.position_x,
                "y": pin.position_y,
            }
        )
        row = result.fetchone()
        return {"id": str(row.id), "status": "created"}
