"""License key management for WebReaper.

Key format: WR-{TIER}-{8CHAR_ID}-{8CHAR_SIG}
  TIER: LITE or PRO
  ID:   8 random hex chars (uppercase)
  SIG:  first 8 chars of HMAC-SHA256("{TIER}:{ID}", secret) uppercased

Tiers:
  LITE  — 500 pages/month  ($19.99/month)
  PRO   — unlimited        ($119.99 one-time)

Admin key generation requires WEBREAPER_LICENSE_SECRET env var.
Validation works offline — the HMAC is verified locally.
"""

import hmac
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

WEBREAPER_DIR = Path.home() / ".webreaper"
LICENSE_FILE = WEBREAPER_DIR / "license.json"

# Secret used to sign/verify keys. Must be the same value used at generation time.
# In production, WEBREAPER_LICENSE_SECRET must be set — the dev fallback is only
# used when APP_ENV is not "production" to allow local development.
_DEV_SECRET = "wr-dev-secret-change-in-production"  # noqa: S105

TIER_LIMITS: dict[str, Optional[int]] = {
    "LITE": 500,   # pages per month
    "PRO": None,   # unlimited
}

TIER_PRICES = {
    "LITE": "$19.99/month — 500 pages/month",
    "PRO":  "$119.99 one-time — unlimited",
}


def _secret() -> str:
    secret = os.getenv("WEBREAPER_LICENSE_SECRET")
    if secret:
        return secret
    if os.getenv("APP_ENV") == "production":
        raise RuntimeError(
            "WEBREAPER_LICENSE_SECRET must be set in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    return _DEV_SECRET


def _sign(tier: str, key_id: str) -> str:
    payload = f"{tier}:{key_id}"
    return hmac.new(
        _secret().encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()[:8].upper()


def generate_key(tier: str) -> str:
    """Generate a signed license key. Requires WEBREAPER_LICENSE_SECRET to be set."""
    tier = tier.upper()
    if tier not in TIER_LIMITS:
        raise ValueError(f"Unknown tier '{tier}'. Use: {list(TIER_LIMITS)}")
    key_id = uuid.uuid4().hex[:8].upper()
    sig = _sign(tier, key_id)
    return f"WR-{tier}-{key_id}-{sig}"


def validate_key(key: str) -> dict:
    """Validate a license key. Returns {'valid': bool, 'tier': str, 'error': str|None}."""
    try:
        parts = key.strip().upper().split("-")
        if len(parts) != 4 or parts[0] != "WR":
            return {"valid": False, "tier": None, "error": "Invalid format (expected WR-TIER-XXXXXXXX-YYYYYYYY)"}

        _, tier, key_id, sig = parts

        if tier not in TIER_LIMITS:
            return {"valid": False, "tier": None, "error": f"Unknown tier '{tier}'"}

        expected = _sign(tier, key_id)
        if not hmac.compare_digest(sig, expected):
            return {"valid": False, "tier": None, "error": "Invalid key — signature mismatch"}

        return {"valid": True, "tier": tier, "error": None}

    except Exception as e:
        return {"valid": False, "tier": None, "error": str(e)}


def install_license(key: str) -> dict:
    """Install a license key to ~/.webreaper/license.json. Returns validation result."""
    result = validate_key(key)
    if not result["valid"]:
        return result

    WEBREAPER_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "key": key.strip().upper(),
        "tier": result["tier"],
        "installed_at": datetime.now(timezone.utc).isoformat(),
    }
    LICENSE_FILE.write_text(json.dumps(data, indent=2))
    return result


def get_license() -> Optional[dict]:
    """Read installed license. Returns None if not installed or tampered."""
    if not LICENSE_FILE.exists():
        return None
    try:
        data = json.loads(LICENSE_FILE.read_text())
        check = validate_key(data.get("key", ""))
        if not check["valid"]:
            return None
        return data
    except Exception:
        return None


def get_tier() -> str:
    """Return current tier: LITE, PRO, or FREE (no license)."""
    lic = get_license()
    return lic["tier"] if lic else "FREE"


def get_page_limit() -> Optional[int]:
    """Return monthly page limit. None = unlimited. 0 = no access via API."""
    tier = get_tier()
    if tier == "FREE":
        return 0  # FREE tier cannot use the API/dashboard; use CLI only
    return TIER_LIMITS.get(tier, 0)


def revoke_license():
    """Remove installed license."""
    if LICENSE_FILE.exists():
        LICENSE_FILE.unlink()


def is_admin() -> bool:
    """Return True if running in admin mode (owner bypass — no license required)."""
    return os.getenv("WEBREAPER_ADMIN", "").strip() == "1"
