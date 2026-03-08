"""
webreaper/billing.py
====================
Stripe webhook handler.

Listens for subscription events and syncs the user's plan
into their Supabase user metadata so auth.py can read it.

Mount this in your FastAPI app:
    from webreaper.billing import router as billing_router
    app.include_router(billing_router, prefix="/webhooks")

Then point your Stripe webhook to: https://yourdomain.com/webhooks/stripe
Events to enable in Stripe dashboard:
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
"""

import os
from typing import Optional

import structlog
from fastapi import APIRouter, Header, HTTPException, Request, status

from webreaper.auth import _get_supabase_client

logger = structlog.get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Price-to-plan mapping
# ---------------------------------------------------------------------------
def _get_price_to_plan() -> dict[str, str]:
    """
    Map Stripe Price IDs → plan names.

    Filters out empty strings so that unset env vars don't produce
    a phantom "" key that shadows real mappings.
    """
    raw = {
        os.environ.get("STRIPE_PRICE_STARTER", ""): "starter",
        os.environ.get("STRIPE_PRICE_PRO", ""): "pro",
        os.environ.get("STRIPE_PRICE_AGENCY", ""): "agency",
    }
    return {price_id: plan for price_id, plan in raw.items() if price_id}


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------
async def _set_user_plan(supabase_user_id: str, plan: str) -> None:
    """Update the user's plan in Supabase user metadata."""
    try:
        client = _get_supabase_client()
        client.auth.admin.update_user_by_id(
            supabase_user_id,
            {"user_metadata": {"plan": plan}},
        )
        logger.info("billing.plan_updated", user_id=supabase_user_id, plan=plan)
    except Exception as exc:
        logger.error(
            "billing.plan_update_failed",
            user_id=supabase_user_id,
            error=str(exc),
        )
        raise


async def _get_supabase_user_id_from_customer(
    stripe_customer_id: str,
) -> Optional[str]:
    """
    Look up a Supabase user ID from a Stripe customer ID.

    Queries the Supabase 'profiles' table where stripe_customer_id is stored.
    Adjust the table/column names to match your schema.
    """
    try:
        client = _get_supabase_client()
        result = (
            client.table("profiles")
            .select("id")
            .eq("stripe_customer_id", stripe_customer_id)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]["id"]

        logger.warning(
            "billing.customer_not_found",
            stripe_customer_id=stripe_customer_id,
        )
        return None

    except Exception as exc:
        logger.error(
            "billing.customer_lookup_failed",
            stripe_customer_id=stripe_customer_id,
            error=str(exc),
        )
        return None


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------
@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature"),
) -> dict:
    """
    Receives Stripe webhook events and updates user plan in Supabase.
    """
    import stripe  # type: ignore

    # ---- Guard: webhook secret must be configured ----
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="STRIPE_WEBHOOK_SECRET not configured",
        )

    # ---- Guard: signature header must be present ----
    if not stripe_signature:
        logger.warning("billing.missing_signature_header")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header",
        )

    payload = await request.body()

    # ---- Verify the event came from Stripe ----
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        logger.warning("billing.invalid_signature")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe signature",
        )
    except Exception as exc:
        logger.error("billing.event_parse_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not parse Stripe event",
        )

    event_type: str = event["type"]
    data: dict = event["data"]["object"]
    price_to_plan = _get_price_to_plan()

    logger.info("billing.event_received", event_type=event_type)

    # -------------------------------------------------------------------
    # Subscription created or updated → set plan
    # -------------------------------------------------------------------
    if event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
    ):
        customer_id = data.get("customer")
        if not customer_id:
            logger.warning("billing.missing_customer_id", event_type=event_type)
            return {"status": "ok"}

        # Safely extract price ID
        items = data.get("items", {}).get("data", [])
        if not items:
            logger.warning("billing.no_subscription_items", event_type=event_type)
            return {"status": "ok"}

        price_id = items[0].get("price", {}).get("id", "")
        plan = price_to_plan.get(price_id, "starter")
        sub_status = data.get("status")

        # Only activate if the subscription is actually active
        if sub_status in ("active", "trialing"):
            supabase_user_id = await _get_supabase_user_id_from_customer(
                customer_id
            )
            if supabase_user_id:
                await _set_user_plan(supabase_user_id, plan)
        else:
            logger.info("billing.subscription_not_active", status=sub_status)

    # -------------------------------------------------------------------
    # Subscription deleted / cancelled → downgrade to starter (free)
    # -------------------------------------------------------------------
    elif event_type == "customer.subscription.deleted":
        customer_id = data.get("customer")
        if not customer_id:
            logger.warning("billing.missing_customer_id", event_type=event_type)
            return {"status": "ok"}

        supabase_user_id = await _get_supabase_user_id_from_customer(
            customer_id
        )
        if supabase_user_id:
            await _set_user_plan(supabase_user_id, "starter")

    else:
        logger.debug("billing.unhandled_event", event_type=event_type)

    return {"status": "ok"}
