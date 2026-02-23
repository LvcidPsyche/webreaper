"""Monthly usage tracking for license enforcement.

Stores page crawl counts in ~/.webreaper/usage.json.
Resets automatically on the first use of a new calendar month.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

WEBREAPER_DIR = Path.home() / ".webreaper"
USAGE_FILE = WEBREAPER_DIR / "usage.json"


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def get_usage() -> dict:
    """Get current month's usage stats."""
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
    """Record that `count` pages were crawled this month."""
    usage = get_usage()
    usage["pages_crawled"] = usage.get("pages_crawled", 0) + count
    _save_usage(usage)


def reset_usage():
    """Reset monthly counter (admin use)."""
    _save_usage({"month": _current_month(), "pages_crawled": 0})


def can_crawl(pages_requested: int, page_limit: Optional[int]) -> Tuple[bool, str]:
    """
    Check if a crawl is allowed under current license usage.

    Returns (allowed: bool, reason: str).
    If allowed is False, reason explains why.
    """
    if page_limit is None:
        return True, ""  # PRO — unlimited

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
