"""License management API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from webreaper.license import (
    get_license, install_license, get_tier, get_page_limit, revoke_license
)
from webreaper.usage import get_usage, reset_usage, get_summary

router = APIRouter()


class ActivateRequest(BaseModel):
    key: str


@router.get("")
async def license_status():
    """Get current license and usage status."""
    lic = get_license()
    tier = get_tier()
    limit = get_page_limit()
    usage = get_usage()
    summary = get_summary(limit)

    return {
        "installed": lic is not None,
        "tier": tier,
        "key_preview": (lic["key"][:11] + "****") if lic else None,
        "installed_at": lic.get("installed_at") if lic else None,
        "pages_limit": limit,
        "pages_used": summary["pages_used"],
        "pages_remaining": summary["pages_remaining"],
        "pct_used": summary["pct_used"],
        "month": summary["month"],
        "tier_description": _tier_label(tier),
    }


@router.post("/activate")
async def activate_license(body: ActivateRequest):
    """Install a license key."""
    result = install_license(body.key)
    if not result["valid"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {
        "success": True,
        "tier": result["tier"],
        "message": f"License activated — {_tier_label(result['tier'])}",
    }


@router.delete("")
async def deactivate_license():
    """Remove the installed license."""
    revoke_license()
    return {"success": True, "message": "License removed"}


@router.post("/reset-usage")
async def admin_reset_usage():
    """Reset monthly usage counter (admin)."""
    reset_usage()
    return {"success": True, "message": "Usage counter reset"}


def _tier_label(tier: str) -> str:
    labels = {
        "LITE": "LITE — 500 pages/month ($19.99/month)",
        "PRO":  "PRO — Unlimited ($119.99 one-time)",
        "FREE": "No license installed",
        "SELF_HOST": "Self-hosted mode — license enforcement disabled",
    }
    return labels.get(tier, tier)
