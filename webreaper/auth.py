"""
webreaper/auth.py
=================
Supabase JWT authentication middleware for FastAPI.

Usage — protect a route:
    from webreaper.auth import require_auth, CurrentUser

    @router.get("/scrapers")
    async def list_scrapers(user: CurrentUser):
        return await get_scrapers_for_user(user.id)

Usage — check plan limits:
    from webreaper.auth import require_plan

    @router.post("/scrapers")
    async def create_scraper(
        data: ScraperCreate,
        user: CurrentUser,
        _: None = Depends(require_plan("starter")),
    ):
        ...
"""

import os
import threading
from typing import Annotated, Optional

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Bearer token extractor
# ---------------------------------------------------------------------------
_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# User model (subset of Supabase JWT claims we care about)
# ---------------------------------------------------------------------------
class AuthUser(BaseModel):
    id: str                      # Supabase user UUID
    email: Optional[str] = None
    plan: str = "starter"        # "starter" | "pro" | "agency"
    is_active: bool = True


# ---------------------------------------------------------------------------
# Plan hierarchy (used for limit enforcement)
# ---------------------------------------------------------------------------
PLAN_RANK: dict[str, int] = {"starter": 0, "pro": 1, "agency": 2}


# ---------------------------------------------------------------------------
# Supabase client singleton
# ---------------------------------------------------------------------------
# Thread-safe lazy singleton.  The Supabase Python client is safe to reuse
# across requests — it holds an httpx client internally that pools connections.
_supabase_client = None
_supabase_lock = threading.Lock()


def _get_supabase_client():
    """
    Return a shared Supabase admin client (service role).

    Raises HTTPException 500 if SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY
    are missing from the environment.
    """
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    with _supabase_lock:
        # Double-check after acquiring lock
        if _supabase_client is not None:
            return _supabase_client

        try:
            from supabase import create_client  # type: ignore

            url = os.environ["SUPABASE_URL"]
            key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        except ImportError:
            logger.error("auth.supabase_not_installed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="supabase package is not installed. "
                       "Run: pip install supabase",
            )
        except KeyError as exc:
            logger.error("auth.config_missing", missing=str(exc))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Auth is not configured. "
                       "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.",
            )

        _supabase_client = create_client(url, key)
        return _supabase_client


def reset_supabase_client() -> None:
    """
    Reset the cached client.  Call this in tests or if credentials rotate.
    """
    global _supabase_client
    with _supabase_lock:
        _supabase_client = None


# ---------------------------------------------------------------------------
# Core: verify Supabase JWT and return AuthUser
# ---------------------------------------------------------------------------
async def _verify_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> AuthUser:
    """
    Verifies the Bearer token against Supabase and returns the AuthUser.
    Raises HTTP 401 if the token is missing or invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        client = _get_supabase_client()
        response = client.auth.get_user(token)
        supabase_user = response.user

        if supabase_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Pull plan from user metadata (set by Stripe webhook)
        plan = (supabase_user.user_metadata or {}).get("plan", "starter")

        # Guard against tampered/unknown plan values
        if plan not in PLAN_RANK:
            logger.warning(
                "auth.unknown_plan",
                user_id=supabase_user.id,
                plan=plan,
            )
            plan = "starter"

        return AuthUser(
            id=supabase_user.id,
            email=supabase_user.email,
            plan=plan,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("auth.verification_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# Public Depends aliases
# ---------------------------------------------------------------------------

# Use this in route signatures:  user: CurrentUser
CurrentUser = Annotated[AuthUser, Depends(_verify_token)]


def require_plan(minimum_plan: str):
    """
    Dependency factory: require user to be on minimum_plan or higher.

    Usage:
        @router.post("/scrapers")
        async def create_scraper(
            user: CurrentUser,
            _: None = Depends(require_plan("pro")),
        ): ...
    """
    if minimum_plan not in PLAN_RANK:
        raise ValueError(
            f"Unknown plan '{minimum_plan}'. "
            f"Valid plans: {list(PLAN_RANK.keys())}"
        )

    async def _check(user: CurrentUser) -> None:
        user_rank = PLAN_RANK.get(user.plan, 0)
        required_rank = PLAN_RANK[minimum_plan]
        if user_rank < required_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires the '{minimum_plan}' plan or higher. "
                       f"Your current plan is '{user.plan}'.",
            )
    return _check


# ---------------------------------------------------------------------------
# Plan limits (enforce in middleware or per-route)
# ---------------------------------------------------------------------------
PLAN_LIMITS: dict[str, dict] = {
    "starter": {
        "max_scrapers": 5,
        "max_pages_per_month": 5_000,
        "max_concurrent_jobs": 2,
        "ai_digest": False,
        "stealth_mode": False,
        "webhooks": False,
        "api_access": False,
    },
    "pro": {
        "max_scrapers": 25,
        "max_pages_per_month": 50_000,
        "max_concurrent_jobs": 10,
        "ai_digest": True,
        "stealth_mode": True,
        "webhooks": True,
        "api_access": False,
    },
    "agency": {
        "max_scrapers": None,        # unlimited
        "max_pages_per_month": None,  # unlimited
        "max_concurrent_jobs": 50,
        "ai_digest": True,
        "stealth_mode": True,
        "webhooks": True,
        "api_access": True,
    },
}


def get_plan_limits(plan: str) -> dict:
    """Return the limits dict for a given plan name."""
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["starter"])
