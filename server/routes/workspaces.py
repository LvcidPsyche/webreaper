"""Workspace CRUD and scope utilities."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, select

from webreaper.database import Crawl, Page, Workspace, WorkspacePageFiling
from webreaper.workspaces.library import build_library_item, filter_library_items, summarize_library
from webreaper.workspaces.scope import evaluate_scope

router = APIRouter()


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    scope_rules: list[dict] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    risk_policy: dict = Field(default_factory=dict)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    scope_rules: list[dict] | None = None
    tags: list[str] | None = None
    risk_policy: dict | None = None
    archived: bool | None = None


class ScopeCheckRequest(BaseModel):
    url: str


class WorkspaceLibraryFilingUpdate(BaseModel):
    folder: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=50)
    labels: list[str] | None = None
    notes: str | None = None
    starred: bool | None = None


class WorkspaceLibraryAutoFileRequest(BaseModel):
    page_ids: list[str] = Field(default_factory=list)
    overwrite_existing: bool = False


def _serialize_workspace(ws: Workspace) -> dict:
    return {
        "id": str(ws.id),
        "name": ws.name,
        "description": ws.description,
        "scope_rules": ws.scope_rules or [],
        "tags": ws.tags or [],
        "risk_policy": ws.risk_policy or {},
        "archived": bool(ws.archived),
        "created_at": ws.created_at.isoformat() if ws.created_at else None,
        "updated_at": ws.updated_at.isoformat() if ws.updated_at else None,
    }


def _db(request: Request):
    db = getattr(request.app.state, "db", None)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")
    return db


def _serialize_filing(filing: WorkspacePageFiling | None) -> dict | None:
    if filing is None:
        return None
    return {
        "id": str(filing.id),
        "workspace_id": str(filing.workspace_id),
        "page_id": str(filing.page_id),
        "folder": filing.folder,
        "category": filing.category,
        "labels": filing.labels or [],
        "notes": filing.notes,
        "starred": bool(filing.starred),
        "created_at": filing.created_at.isoformat() if filing.created_at else None,
        "updated_at": filing.updated_at.isoformat() if filing.updated_at else None,
    }


async def _workspace_or_404(session, workspace_id: str) -> Workspace:
    workspace = await session.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


async def _page_or_404(session, workspace_id: str, page_id: str) -> Page:
    page = await session.get(Page, page_id)
    if not page or str(page.workspace_id or "") != workspace_id:
        raise HTTPException(status_code=404, detail="Workspace page not found")
    return page


async def _workspace_library_rows(session, workspace_id: str):
    result = await session.execute(
        select(Page, Crawl, WorkspacePageFiling)
        .join(Crawl, Page.crawl_id == Crawl.id)
        .outerjoin(
            WorkspacePageFiling,
            and_(
                WorkspacePageFiling.page_id == Page.id,
                WorkspacePageFiling.workspace_id == workspace_id,
            ),
        )
        .where(Page.workspace_id == workspace_id)
        .order_by(Page.scraped_at.desc(), Page.url.asc())
    )
    return result.all()


def _workspace_library_items(rows) -> list[dict]:
    items: list[dict] = []
    for page, crawl, filing in rows:
        items.append(
            build_library_item(
                page=page.__dict__,
                crawl=crawl.__dict__ if crawl is not None else None,
                filing=_serialize_filing(filing),
            )
        )
    return items


@router.get("")
async def list_workspaces(request: Request, include_archived: bool = False):
    db = _db(request)
    async with db.get_session() as session:
        q = select(Workspace).order_by(Workspace.created_at.desc())
        if not include_archived:
            q = q.where(Workspace.archived.is_(False))
        rows = (await session.execute(q)).scalars().all()
        return [_serialize_workspace(w) for w in rows]


@router.post("")
async def create_workspace(payload: WorkspaceCreate, request: Request):
    db = _db(request)
    async with db.get_session() as session:
        ws = Workspace(
            name=payload.name,
            description=payload.description,
            scope_rules=payload.scope_rules,
            tags=payload.tags,
            risk_policy=payload.risk_policy,
            archived=False,
            updated_at=datetime.now(timezone.utc),
        )
        session.add(ws)
        await session.flush()
        return _serialize_workspace(ws)


@router.get("/{workspace_id}")
async def get_workspace(workspace_id: str, request: Request):
    db = _db(request)
    async with db.get_session() as session:
        ws = await session.get(Workspace, workspace_id)
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return _serialize_workspace(ws)


@router.put("/{workspace_id}")
async def update_workspace(workspace_id: str, payload: WorkspaceUpdate, request: Request):
    db = _db(request)
    async with db.get_session() as session:
        ws = await session.get(Workspace, workspace_id)
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")

        updates = payload.model_dump(exclude_unset=True)
        for k, v in updates.items():
            setattr(ws, k, v)
        ws.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return _serialize_workspace(ws)


@router.delete("/{workspace_id}")
async def archive_workspace(workspace_id: str, request: Request):
    db = _db(request)
    async with db.get_session() as session:
        ws = await session.get(Workspace, workspace_id)
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")
        ws.archived = True
        ws.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return {"status": "archived", "id": workspace_id}


@router.post("/{workspace_id}/scope/check")
async def scope_check(workspace_id: str, payload: ScopeCheckRequest, request: Request):
    db = _db(request)
    async with db.get_session() as session:
        ws = await session.get(Workspace, workspace_id)
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")
        decision = evaluate_scope(payload.url, ws.scope_rules or [])
        return {
            "workspace_id": workspace_id,
            "url": payload.url,
            "allowed": decision.allowed,
            "reason": decision.reason,
            "matched_rule_id": decision.matched_rule_id,
        }


@router.get("/{workspace_id}/library/summary")
async def workspace_library_summary(workspace_id: str, request: Request):
    db = _db(request)
    async with db.get_session() as session:
        workspace = await _workspace_or_404(session, workspace_id)
        items = _workspace_library_items(await _workspace_library_rows(session, workspace_id))
    return {
        "workspace": _serialize_workspace(workspace),
        "summary": summarize_library(items),
        "recent_items": items[:10],
    }


@router.get("/{workspace_id}/library/items")
async def workspace_library_items(
    workspace_id: str,
    request: Request,
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    folder: str | None = Query(default=None),
    domain: str | None = Query(default=None),
    starred: bool | None = Query(default=None),
    status_code: int | None = Query(default=None),
    sort: str = Query(default="scraped_at"),
    order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=500),
):
    db = _db(request)
    async with db.get_session() as session:
        workspace = await _workspace_or_404(session, workspace_id)
        items = _workspace_library_items(await _workspace_library_rows(session, workspace_id))

    items = filter_library_items(
        items,
        search=search,
        category=category,
        folder=folder,
        domain=domain,
        starred=starred,
        status_code=status_code,
    )

    reverse = order.lower() != "asc"
    sort_key = sort if sort in {"scraped_at", "word_count", "title", "domain", "status_code", "category", "folder"} else "scraped_at"
    items.sort(key=lambda item: (item.get(sort_key) is None, item.get(sort_key)), reverse=reverse)

    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page

    return {
        "workspace": _serialize_workspace(workspace),
        "summary": summarize_library(items),
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": items[start:end],
    }


@router.put("/{workspace_id}/library/pages/{page_id}")
async def workspace_library_update_page(
    workspace_id: str,
    page_id: str,
    payload: WorkspaceLibraryFilingUpdate,
    request: Request,
):
    db = _db(request)
    async with db.get_session() as session:
        workspace = await _workspace_or_404(session, workspace_id)
        page = await _page_or_404(session, workspace_id, page_id)
        crawl = await session.get(Crawl, page.crawl_id)

        filing_result = await session.execute(
            select(WorkspacePageFiling).where(
                WorkspacePageFiling.workspace_id == workspace_id,
                WorkspacePageFiling.page_id == page_id,
            )
        )
        filing = filing_result.scalar_one_or_none()
        if filing is None:
            filing = WorkspacePageFiling(
                workspace_id=workspace_id,
                page_id=page_id,
                labels=[],
                starred=False,
                updated_at=datetime.now(timezone.utc),
            )
            session.add(filing)

        updates = payload.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(filing, key, value)
        filing.updated_at = datetime.now(timezone.utc)
        await session.flush()

        item = build_library_item(
            page=page.__dict__,
            crawl=crawl.__dict__ if crawl is not None else None,
            filing=_serialize_filing(filing),
        )

    return {
        "workspace": _serialize_workspace(workspace),
        "item": item,
    }


@router.post("/{workspace_id}/library/auto-file")
async def workspace_library_auto_file(
    workspace_id: str,
    payload: WorkspaceLibraryAutoFileRequest,
    request: Request,
):
    db = _db(request)
    target_page_ids = set(payload.page_ids)
    async with db.get_session() as session:
        workspace = await _workspace_or_404(session, workspace_id)
        rows = await _workspace_library_rows(session, workspace_id)

        created = 0
        updated = 0
        skipped = 0
        changed_items: list[dict] = []

        for page, crawl, filing in rows:
            page_id = str(page.id)
            if target_page_ids and page_id not in target_page_ids:
                continue
            suggested_item = build_library_item(
                page=page.__dict__,
                crawl=crawl.__dict__ if crawl is not None else None,
                filing=_serialize_filing(filing),
            )
            if filing is not None and not payload.overwrite_existing:
                skipped += 1
                continue

            if filing is None:
                filing = WorkspacePageFiling(
                    workspace_id=workspace_id,
                    page_id=page_id,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(filing)
                created += 1
            else:
                updated += 1

            filing.category = suggested_item["suggested_category"]
            filing.folder = suggested_item["suggested_folder"]
            filing.labels = suggested_item["suggested_labels"]
            filing.updated_at = datetime.now(timezone.utc)
            await session.flush()

            changed_items.append(
                build_library_item(
                    page=page.__dict__,
                    crawl=crawl.__dict__ if crawl is not None else None,
                    filing=_serialize_filing(filing),
                )
            )

    return {
        "workspace": _serialize_workspace(workspace),
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "items": changed_items,
    }


@router.get("/{workspace_id}/library/export")
async def workspace_library_export(
    workspace_id: str,
    request: Request,
    fmt: str = Query(default="json"),
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    folder: str | None = Query(default=None),
    domain: str | None = Query(default=None),
):
    db = _db(request)
    async with db.get_session() as session:
        await _workspace_or_404(session, workspace_id)
        items = _workspace_library_items(await _workspace_library_rows(session, workspace_id))

    items = filter_library_items(items, search=search, category=category, folder=folder, domain=domain)

    if fmt == "json":
        payload = io.BytesIO()
        payload.write((json.dumps(items, indent=2) + "\n").encode("utf-8"))
        payload.seek(0)
        return StreamingResponse(
            payload,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="workspace-{workspace_id[:8]}-library.json"'},
        )

    if fmt != "csv":
        raise HTTPException(status_code=422, detail="fmt must be 'json' or 'csv'")

    buffer = io.StringIO()
    rows = []
    for item in items:
        rows.append(
            {
                "page_id": item["page_id"],
                "url": item["url"],
                "domain": item["domain"],
                "title": item["title"],
                "status_code": item["status_code"],
                "category": item["category"],
                "folder": item["folder"],
                "labels": ", ".join(item["labels"]),
                "starred": item["starred"],
                "word_count": item["word_count"],
                "content_family": item["content_family"],
                "scraped_at": item["scraped_at"],
            }
        )
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    payload = io.BytesIO(buffer.getvalue().encode("utf-8"))
    return StreamingResponse(
        payload,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="workspace-{workspace_id[:8]}-library.csv"'},
    )
