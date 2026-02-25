"""REST endpoints for security findings."""

from datetime import datetime, timezone
import json

from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel, Field
import httpx
from sqlalchemy import select

from webreaper.database import SecurityFinding, FindingTriage
from webreaper.governance.policy import evaluate_policy, audit_log

router = APIRouter()


class ScanRequest(BaseModel):
    url: str
    auto_attack: bool = False
    workspace_id: str | None = None
    acknowledge_risk: bool = False


class FindingTriageRequest(BaseModel):
    status: str = Field(default="open")
    assignee: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    endpoint_id: str | None = None
    transaction_id: str | None = None
    reproduction_steps: list[str] = Field(default_factory=list)
    evidence_refs: list[dict] = Field(default_factory=list)


@router.get("")
@router.get("/findings")
async def get_findings(
    request: Request,
    crawl_id: str | None = None,
    workspace_id: str | None = None,
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
        query = select(SecurityFinding)
        if workspace_id:
            query = query.where(SecurityFinding.workspace_id == workspace_id)
        if crawl_id:
            query = query.where(SecurityFinding.crawl_id == crawl_id)
        if severity:
            query = query.where(SecurityFinding.severity == severity)
        if finding_type:
            query = query.where(SecurityFinding.finding_type == finding_type)
        query = query.order_by(SecurityFinding.discovered_at.desc()).offset(offset).limit(limit)
        result = await session.execute(query)
        findings = result.scalars().all()
        triage_result = await session.execute(
            select(FindingTriage).where(FindingTriage.finding_id.in_([f.id for f in findings])) if findings else select(FindingTriage).where(FindingTriage.id == "__none__")
        )
        triage_by_fid = {str(t.finding_id): t for t in triage_result.scalars().all()}
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
                "workspace_id": str(f.workspace_id) if f.workspace_id else None,
                "verified": bool(f.verified),
                "false_positive": bool(f.false_positive),
                "confidence": f.confidence,
                "triage_status": (triage_by_fid.get(str(f.id)).status if triage_by_fid.get(str(f.id)) else "open"),
                "triage_assignee": (triage_by_fid.get(str(f.id)).assignee if triage_by_fid.get(str(f.id)) else None),
                "triage_tags": (triage_by_fid.get(str(f.id)).tags if triage_by_fid.get(str(f.id)) else []),
                "triage_notes": (triage_by_fid.get(str(f.id)).notes if triage_by_fid.get(str(f.id)) else None),
                "endpoint_id": (str(triage_by_fid.get(str(f.id)).endpoint_id) if triage_by_fid.get(str(f.id)) and triage_by_fid.get(str(f.id)).endpoint_id else None),
                "transaction_id": (str(triage_by_fid.get(str(f.id)).transaction_id) if triage_by_fid.get(str(f.id)) and triage_by_fid.get(str(f.id)).transaction_id else None),
            }
            for f in findings
        ]


@router.post("/scan")
async def scan_url(req: ScanRequest, request: Request):
    """Run an on-demand security scan against a URL and persist findings."""
    db = request.app.state.db
    from webreaper.fetcher import StealthFetcher
    from webreaper.config import StealthConfig
    from webreaper.deep_extractor import DeepExtractor
    from webreaper.scanner.engine import SecurityScanEngine
    from webreaper.scanner.contracts import ScanContext
    import uuid

    if req.auto_attack and db:
        decision = await evaluate_policy(db, req.workspace_id, "security.active_scan", acknowledge=req.acknowledge_risk)
        await audit_log(
            db,
            workspace_id=req.workspace_id,
            action="security.active_scan",
            allowed=decision.allowed,
            resource_type="url",
            resource_id=None,
            policy_rule=decision.rule,
            reason=decision.reason,
            details={"url": req.url, "auto_attack": True},
        )
        if not decision.allowed:
            raise HTTPException(status_code=403, detail=decision.reason)

    try:
        fetcher_config = StealthConfig()
        async with StealthFetcher(fetcher_config) as fetcher:
            status, headers, body = await fetcher.fetch(req.url)

        extractor = DeepExtractor()
        try:
            deep = extractor.extract(
                url=req.url,
                status_code=status,
                html=body or "",
                headers=headers or {},
                response_time_ms=0,
                depth=0,
            )
            forms = deep.forms
        except Exception:
            forms = []

        engine = SecurityScanEngine(auto_attack=req.auto_attack)
        ctx = ScanContext(
            url=req.url,
            headers=headers or {},
            body=body or "",
            forms=forms or [],
            auto_attack=req.auto_attack,
            aggressive=bool(req.auto_attack),
        )
        if req.auto_attack:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                scan_out = await engine.run(ctx, http_session=client)
        else:
            scan_out = await engine.run(ctx, http_session=None)
        findings = scan_out.findings
        tech = scan_out.technology

        # Persist findings to DB
        saved = 0
        if db and findings:
            async with db.get_session() as session:
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
                        workspace_id=req.workspace_id,
                    )
                    session.add(sf)
                    await session.flush()
                    triage = FindingTriage(
                        finding_id=sf.id,
                        workspace_id=req.workspace_id,
                        status="open",
                        tags=["auto_attack" if req.auto_attack else "passive"],
                        evidence_refs=[{"type": "scan_url", "url": req.url}],
                        reproduction_steps=[],
                        triaged_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                    session.add(triage)
                await session.commit()
                saved = len(findings)

        return {
            "url": req.url,
            "status_code": status,
            "findings_count": len(findings),
            "findings_saved": saved,
            "findings": findings,
            "technology": tech,
            "scan_engine": {
                "passive_modules": scan_out.passive_modules,
                "active_modules": scan_out.active_modules,
            },
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


@router.patch("/findings/{finding_id}/triage")
async def triage_finding(finding_id: str, payload: FindingTriageRequest, request: Request):
    db = request.app.state.db
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    async with db.get_session() as session:
        finding = await session.get(SecurityFinding, finding_id)
        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found")

        triage = (await session.execute(select(FindingTriage).where(FindingTriage.finding_id == finding.id))).scalar_one_or_none()
        if not triage:
            triage = FindingTriage(
                finding_id=finding.id,
                workspace_id=finding.workspace_id,
            )
            session.add(triage)
        triage.status = payload.status
        triage.assignee = payload.assignee
        triage.tags = payload.tags
        triage.notes = payload.notes
        triage.endpoint_id = payload.endpoint_id
        triage.transaction_id = payload.transaction_id
        triage.reproduction_steps = payload.reproduction_steps
        triage.evidence_refs = payload.evidence_refs
        triage.updated_at = datetime.now(timezone.utc)
        triage.triaged_at = datetime.now(timezone.utc)

        # Mirror core disposition fields on finding
        if payload.status == "false_positive":
            finding.false_positive = True
            finding.verified = False
        elif payload.status in {"resolved", "accepted", "in_progress", "risk_accepted"}:
            finding.false_positive = False
            finding.verified = payload.status in {"resolved", "accepted"}

        await session.flush()
        finding_workspace_id = str(finding.workspace_id) if finding.workspace_id else None

    await audit_log(
        db,
        workspace_id=finding_workspace_id,
        action="security.finding_triage",
        allowed=True,
        resource_type="finding",
        resource_id=finding_id,
        details={"status": payload.status, "assignee": payload.assignee, "tags": payload.tags},
    )
    return {"status": "ok", "finding_id": finding_id, "triage_status": payload.status}


@router.get("/triage")
async def list_triage(
    request: Request,
    workspace_id: str | None = None,
    status: str | None = None,
    assignee: str | None = None,
):
    db = request.app.state.db
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    async with db.get_session() as session:
        q = (
            select(FindingTriage, SecurityFinding)
            .join(SecurityFinding, SecurityFinding.id == FindingTriage.finding_id)
            .order_by(FindingTriage.triaged_at.desc())
        )
        if workspace_id:
            q = q.where(FindingTriage.workspace_id == workspace_id)
        if status:
            q = q.where(FindingTriage.status == status)
        if assignee:
            q = q.where(FindingTriage.assignee == assignee)
        rows = (await session.execute(q)).all()
    return [
        {
            "finding_id": str(f.id),
            "url": f.url,
            "severity": (f.severity or "Info").lower(),
            "type": f.finding_type,
            "title": f.title,
            "status": t.status,
            "assignee": t.assignee,
            "tags": t.tags or [],
            "notes": t.notes,
            "endpoint_id": str(t.endpoint_id) if t.endpoint_id else None,
            "transaction_id": str(t.transaction_id) if t.transaction_id else None,
            "triaged_at": t.triaged_at.isoformat() if t.triaged_at else None,
        }
        for t, f in rows
    ]


@router.get("/report/export")
async def export_findings_report(
    request: Request,
    workspace_id: str | None = None,
    crawl_id: str | None = None,
    format: str = Query(default="json", pattern="^(json|markdown)$"),
    redact_payloads: bool = True,
):
    db = request.app.state.db
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    findings = await get_findings(
        request=request,
        crawl_id=crawl_id,
        workspace_id=workspace_id,
        severity=None,
        finding_type=None,
        limit=1000,
        offset=0,
    )
    for f in findings:
        if redact_payloads and f.get("evidence"):
            f["evidence"] = str(f["evidence"])[:500]

    summary = {}
    for f in findings:
        sev = f.get("severity", "info")
        summary[sev] = summary.get(sev, 0) + 1

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace_id": workspace_id,
        "crawl_id": crawl_id,
        "summary": summary,
        "total": len(findings),
        "findings": findings,
    }
    await audit_log(
        db,
        workspace_id=workspace_id,
        action="security.report_export",
        allowed=True,
        resource_type="report",
        details={"format": format, "crawl_id": crawl_id, "findings": len(findings)},
    )
    if format == "json":
        return report

    lines = [
        "# WebReaper Security Findings Report",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Total findings: {report['total']}",
        f"- Severity summary: {json.dumps(summary)}",
        "",
        "## Findings",
        "",
    ]
    for i, f in enumerate(findings, 1):
        lines.extend(
            [
                f"### {i}. [{f.get('severity','info').upper()}] {f.get('title') or f.get('type')}",
                f"- URL: {f.get('url')}",
                f"- Type: {f.get('type')}",
                f"- Triage: {f.get('triage_status', 'open')}",
                f"- Evidence: {f.get('evidence') or ''}",
                f"- Remediation: {f.get('remediation') or ''}",
                "",
            ]
        )
    return {"format": "markdown", "content": "\n".join(lines), "summary": summary, "total": len(findings)}
