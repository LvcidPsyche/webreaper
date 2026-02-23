"""REST endpoints for security findings."""

from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


class ScanRequest(BaseModel):
    url: str
    auto_attack: bool = False


@router.get("")
@router.get("/findings")
async def get_findings(
    request: Request,
    crawl_id: str | None = None,
    severity: str | None = None,
    finding_type: str | None = None,
    limit: int = Query(default=200, le=1000),
    offset: int = 0,
):
    """Query security findings with filters. Accessible at both /api/security and /api/security/findings."""
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
                "category": f.finding_type,
                "severity": f.severity.lower() if f.severity else "info",
                "url": f.url,
                "evidence": f.evidence,
                "title": f.title,
                "parameter": f.parameter,
                "remediation": f.remediation,
                "found_at": f.discovered_at.isoformat() if f.discovered_at else "",
                "crawl_id": str(f.crawl_id) if f.crawl_id else None,
            }
            for f in findings
        ]


@router.post("/scan")
async def scan_url(req: ScanRequest, request: Request):
    """Run an on-demand security scan against a URL and persist findings."""
    db = request.app.state.db
    from webreaper.fetcher import StealthFetcher
    from webreaper.config import StealthConfig
    from webreaper.modules.security import SecurityScanner
    import uuid

    try:
        fetcher_config = StealthConfig()
        async with StealthFetcher(fetcher_config) as fetcher:
            status, headers, body = await fetcher.fetch(req.url)

        scanner = SecurityScanner(auto_attack=req.auto_attack)
        findings = scanner.scan(req.url, headers, body, [])
        tech = scanner.fingerprint_tech(req.url, headers, body)

        # Persist findings to DB
        saved = 0
        if db and findings:
            async with db.get_session() as session:
                from webreaper.database import SecurityFinding
                from datetime import datetime, timezone
                for f in findings:
                    sf = SecurityFinding(
                        id=uuid.uuid4(),
                        url=req.url,
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
                saved = len(findings)

        return {
            "url": req.url,
            "status_code": status,
            "findings_count": len(findings),
            "findings_saved": saved,
            "findings": findings,
            "technology": tech,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
