"""REST endpoints for security findings."""

from fastapi import APIRouter, Request, HTTPException, Query

router = APIRouter()


@router.get("/findings")
async def get_findings(
    request: Request,
    crawl_id: str | None = None,
    severity: str | None = None,
    finding_type: str | None = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
):
    """Query security findings with filters."""
    db = request.app.state.db
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db.get_session() as session:
        from sqlalchemy import select
        from webreaper.database import SecurityFinding
        query = select(SecurityFinding)
        if crawl_id:
            query = query.where(SecurityFinding.crawl_id == crawl_id)
        if severity:
            query = query.where(SecurityFinding.severity == severity)
        if finding_type:
            query = query.where(SecurityFinding.finding_type == finding_type)
        query = query.order_by(SecurityFinding.discovered_at.desc()).offset(offset).limit(limit)
        result = await session.execute(query)
        findings = result.scalars().all()
        return [
            {
                "id": str(f.id),
                "type": f.finding_type,
                "severity": f.severity,
                "url": f.url,
                "evidence": f.evidence,
                "title": f.title,
                "parameter": f.parameter,
                "remediation": f.remediation,
            }
            for f in findings
        ]


@router.get("/summary")
async def security_summary(request: Request):
    """Get security findings summary with severity breakdown."""
    db = request.app.state.db
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    async with db.get_session() as session:
        from sqlalchemy import text
        result = await session.execute(text("""
            SELECT severity, COUNT(*) as count
            FROM security_findings
            GROUP BY severity
            ORDER BY CASE severity
                WHEN 'Critical' THEN 1
                WHEN 'High' THEN 2
                WHEN 'Medium' THEN 3
                WHEN 'Low' THEN 4
                ELSE 5
            END
        """))
        rows = result.fetchall()
        return {
            "total": sum(r.count for r in rows),
            "by_severity": {r.severity: r.count for r in rows},
        }
