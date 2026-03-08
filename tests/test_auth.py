"""Tests for webreaper/auth.py — plan validation, plan limits, singleton reset."""

import pytest
from unittest.mock import patch, MagicMock

from webreaper.auth import (
    AuthUser,
    PLAN_RANK,
    PLAN_LIMITS,
    get_plan_limits,
    require_plan,
    reset_supabase_client,
)


class TestAuthUser:
    def test_defaults(self):
        user = AuthUser(id="u1")
        assert user.plan == "starter"
        assert user.is_active is True
        assert user.email is None

    def test_all_fields(self):
        user = AuthUser(id="u2", email="a@b.com", plan="pro", is_active=False)
        assert user.id == "u2"
        assert user.email == "a@b.com"
        assert user.plan == "pro"
        assert user.is_active is False


class TestPlanRank:
    def test_rank_order(self):
        assert PLAN_RANK["starter"] < PLAN_RANK["pro"] < PLAN_RANK["agency"]

    def test_all_plans_have_limits(self):
        for plan in PLAN_RANK:
            assert plan in PLAN_LIMITS


class TestGetPlanLimits:
    def test_known_plan(self):
        limits = get_plan_limits("pro")
        assert limits["max_scrapers"] == 25
        assert limits["ai_digest"] is True

    def test_unknown_plan_falls_back_to_starter(self):
        limits = get_plan_limits("nonexistent")
        assert limits == PLAN_LIMITS["starter"]

    def test_agency_unlimited_pages(self):
        limits = get_plan_limits("agency")
        assert limits["max_pages_per_month"] is None


class TestRequirePlan:
    def test_unknown_plan_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown plan"):
            require_plan("superadmin")

    @pytest.mark.asyncio
    async def test_sufficient_plan_passes(self):
        check = require_plan("starter")
        user = AuthUser(id="u1", plan="pro")
        await check(user)  # should not raise

    @pytest.mark.asyncio
    async def test_insufficient_plan_raises_403(self):
        from fastapi import HTTPException
        check = require_plan("agency")
        user = AuthUser(id="u1", plan="starter")
        with pytest.raises(HTTPException) as exc_info:
            await check(user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_same_plan_passes(self):
        check = require_plan("pro")
        user = AuthUser(id="u1", plan="pro")
        await check(user)  # should not raise


class TestResetSupabaseClient:
    def test_reset_clears_singleton(self):
        import webreaper.auth as auth_module
        auth_module._supabase_client = "fake"
        reset_supabase_client()
        assert auth_module._supabase_client is None
