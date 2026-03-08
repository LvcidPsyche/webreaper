"""Tests for webreaper/billing.py — price mapping, webhook endpoint."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from webreaper.billing import _get_price_to_plan


class TestPriceToPlan:
    def test_filters_empty_strings(self):
        """Unset env vars should not produce phantom '' keys."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove any STRIPE_PRICE_ vars that might be set
            env = {k: v for k, v in os.environ.items() if not k.startswith("STRIPE_PRICE_")}
            with patch.dict(os.environ, env, clear=True):
                mapping = _get_price_to_plan()
                assert "" not in mapping

    def test_maps_set_prices(self):
        with patch.dict(os.environ, {
            "STRIPE_PRICE_STARTER": "price_starter_123",
            "STRIPE_PRICE_PRO": "price_pro_456",
            "STRIPE_PRICE_AGENCY": "price_agency_789",
        }):
            mapping = _get_price_to_plan()
            assert mapping["price_starter_123"] == "starter"
            assert mapping["price_pro_456"] == "pro"
            assert mapping["price_agency_789"] == "agency"

    def test_partial_env_vars(self):
        """Only set vars should appear in mapping."""
        with patch.dict(os.environ, {
            "STRIPE_PRICE_PRO": "price_pro_only",
        }, clear=False):
            # Clear the others
            env_patch = {
                "STRIPE_PRICE_STARTER": "",
                "STRIPE_PRICE_AGENCY": "",
                "STRIPE_PRICE_PRO": "price_pro_only",
            }
            with patch.dict(os.environ, env_patch):
                mapping = _get_price_to_plan()
                assert "price_pro_only" in mapping
                assert "" not in mapping


class TestStripeWebhook:
    @pytest.mark.asyncio
    async def test_missing_webhook_secret_returns_500(self, client):
        """If STRIPE_WEBHOOK_SECRET is not set, return 500."""
        with patch.dict(os.environ, {}, clear=False):
            # Ensure STRIPE_WEBHOOK_SECRET is not set
            os.environ.pop("STRIPE_WEBHOOK_SECRET", None)
            response = client.post(
                "/webhooks/stripe",
                content=b"{}",
                headers={"stripe-signature": "t=123,v1=abc"},
            )
            assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_missing_signature_returns_400(self, client):
        """If stripe-signature header is missing, return 400."""
        with patch.dict(os.environ, {"STRIPE_WEBHOOK_SECRET": "whsec_test"}):
            response = client.post(
                "/webhooks/stripe",
                content=b"{}",
            )
            assert response.status_code == 400
