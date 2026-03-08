"""
webreaper/usage.py
==================
Usage tracking — two modes:

1. **File-based** (CLI / standalone): get_usage(), add_pages()
   Stores page counts in ~/.webreaper/usage.json. Used by the CLI and
   server/routes/jobs.py for license-based limits.

2. **DB-based** (SaaS / multi-user): get_usage_this_period(), increment_usage(),
   check_page_budget(), check_scraper_limit()
   Tracks per-user usage in the database. Used when running as a multi-tenant API.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from webreaper.auth import PLAN_LIMITS

logger = structlog.get_logger(__name__)


# ===========================================================================
# File-based usage (CLI / standalone mode)
# ===========================================================================

WEBREAPER_DIR = Path.home() / ".webreaper"
USAGE_FILE = WEBREAPER_DIR / "usage.json"


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def get_usage() -> dict:
    """Get current month's usage stats (file-based, for CLI/license checks)."""
    if not USAGE_FILE.exists():
        return {"month": _current_month(), "pages_crawled": 0}
    try:
        data = json.loads(USAGE_FILE.read_text())
        if data.get("month") != _current_month():
            return {"month": _current_month(), "pages_crawled": 0}
        return data
    except Exception:
        return {"month": _current_month(), "pages_crawled": 0}


def _save_usage(data: dict):
    WEBREAPER_DIR.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps(data, indent=2))


def add_pages(count: int):
    """Record that `count` pages were crawled this month (file-based)."""
    usage = get_usage()
    usage["pages_crawled"] = usage.get("pages_crawled", 0) + count
    _save_usage(usage)


def reset_usage():
    """Reset monthly counter (admin use)."""
    _save_usage({"month": _current_month(), "pages_crawled": 0})


def can_crawl(pages_requested: int, page_limit: Optional[int]) -> Tuple[bool, str]:
    """Check if a crawl is allowed under current license usage."""
    if page_limit is None:
        return True, ""

    if page_limit == 0:
        return False, "No active license. Visit webreaper.app to purchase a license."

    usage = get_usage()
    used = usage.get("pages_crawled", 0)

    if used >= page_limit:
        return False, (
            f"Monthly limit reached ({used}/{page_limit} pages used). "
            f"Resets on the 1st of next month. Upgrade to PRO for unlimited access."
        )

    remaining = page_limit - used
    if pages_requested > remaining:
        return False, (
            f"Requested {pages_requested} pages but only {remaining} remaining "
            f"this month ({used}/{page_limit} used). Reduce max_pages or upgrade to PRO."
        )

    return True, ""


def get_summary(page_limit: Optional[int]) -> dict:
    """Return a display-ready usage summary."""
    usage = get_usage()
    used = usage.get("pages_crawled", 0)
    return {
        "month": usage.get("month", _current_month()),
        "pages_used": used,
        "pages_limit": page_limit,
        "pages_remaining": (page_limit - used) if page_limit is not None else None,
        "pct_used": round((used / page_limit * 100), 1) if page_limit else 0,
    }


# ===========================================================================
# DB-based usage (multi-user SaaS mode)
# ===========================================================================

def _current_period_start() -> datetime:
    """Return the start of the current billing period (1st of the month, UTC)."""
    return datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0,
    )


async def get_usage_this_period(
    db: AsyncSession,
    user_id: str,
) -> int:
    """Return how many pages this user has scraped in the current billing period."""
    from webreaper.models import UserUsage

    period_start = _current_period_start()

    result = await db.execute(
        select(UserUsage.pages_scraped).where(
            UserUsage.user_id == user_id,
            UserUsage.period_start == period_start,
        )
    )
    row = result.scalar_one_or_none()
    return row or 0


async def increment_usage(
    db: AsyncSession,
    user_id: str,
    pages: int,
) -> None:
    """
    Atomically add `pages` to this user's usage for the current billing period.

    Uses INSERT ... ON CONFLICT DO UPDATE (true upsert) to avoid the
    read-then-write race condition where two concurrent jobs could both
    read the same count and silently exceed the limit.

    Dialect is selected based on the database engine in use.
    """
    from webreaper.models import UserUsage

    now = datetime.now(timezone.utc)
    period_start = _current_period_start()

    dialect_name = db.bind.dialect.name if db.bind else "postgresql"

    if dialect_name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as dialect_upsert
    else:
        from sqlalchemy.dialects.postgresql import insert as dialect_upsert

    stmt = dialect_upsert(UserUsage).values(
        user_id=user_id,
        period_start=period_start,
        pages_scraped=pages,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "period_start"],
        set_={
            "pages_scraped": UserUsage.__table__.c.pages_scraped + pages,
            "updated_at": now,
        },
    )
    await db.execute(stmt)
    await db.commit()

    logger.debug("usage.incremented", user_id=user_id, pages=pages)


async def check_page_budget(
    db: AsyncSession,
    user_id: str,
    plan: str,
    pages_requested: int = 1,
) -> None:
    """
    Raise HTTP 429 if this user has exceeded their monthly page limit.
    Call this before starting any scrape job.
    """
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["starter"])
    max_pages: Optional[int] = limits.get("max_pages_per_month")

    if max_pages is None:
        return

    current_usage = await get_usage_this_period(db, user_id)
    if current_usage + pages_requested > max_pages:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Monthly page limit reached ({current_usage:,}/{max_pages:,} pages). "
                f"Upgrade your plan to scrape more pages this month."
            ),
            headers={
                "X-Plan": plan,
                "X-Usage": str(current_usage),
                "X-Limit": str(max_pages),
            },
        )


async def check_scraper_limit(
    db: AsyncSession,
    user_id: str,
    plan: str,
) -> None:
    """
    Raise HTTP 403 if this user has reached their max scrapers limit.
    Call this before creating a new scraper.
    """
    from webreaper.models import Scraper

    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["starter"])
    max_scrapers: Optional[int] = limits.get("max_scrapers")

    if max_scrapers is None:
        return

    result = await db.execute(
        select(func.count())
        .select_from(Scraper)
        .where(
            Scraper.user_id == user_id,
            Scraper.is_deleted == False,  # noqa: E712
        )
    )
    count = result.scalar_one()

    if count >= max_scrapers:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Scraper limit reached ({count}/{max_scrapers}). "
                f"Upgrade your plan to create more scrapers."
            ),
        )
