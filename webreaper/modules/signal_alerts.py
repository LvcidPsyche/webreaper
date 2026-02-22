"""Signal — Alerting & Webhooks.

Rule-based alerting engine with multiple delivery channels:
Slack, Discord, email (SMTP), and custom webhooks.
"""

import asyncio
import json
import logging
import smtplib
import os
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.text import MIMEText
from enum import Enum
from typing import Optional

import httpx

logger = logging.getLogger("webreaper.signal")


class DeliveryChannel(Enum):
    SLACK = "slack"
    DISCORD = "discord"
    EMAIL = "email"
    WEBHOOK = "webhook"


@dataclass
class AlertRule:
    """A condition-based alert rule."""
    name: str
    condition: dict  # {"field": "severity", "op": "eq", "value": "Critical"}
    delivery: dict  # {"channel": "slack", "webhook_url": "..."}
    enabled: bool = True
    cooldown_seconds: int = 300
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0


@dataclass
class Alert:
    """A triggered alert."""
    rule_name: str
    message: str
    data: dict
    delivered: bool = False
    delivered_at: Optional[str] = None
    channel: str = ""


class SignalAlerts:
    """Rule-based alerting engine."""

    def __init__(self):
        self._rules: list[AlertRule] = []
        self._history: list[Alert] = []
        self._dedup_cache: set[str] = set()

    def add_rule(self, rule: AlertRule):
        self._rules.append(rule)

    def remove_rule(self, name: str):
        self._rules = [r for r in self._rules if r.name != name]

    async def evaluate(self, event_type: str, data: dict):
        """Evaluate all rules against an event."""
        for rule in self._rules:
            if not rule.enabled:
                continue

            # Cooldown check
            if rule.last_triggered:
                elapsed = (datetime.utcnow() - rule.last_triggered).total_seconds()
                if elapsed < rule.cooldown_seconds:
                    continue

            if self._matches(rule.condition, data):
                # Deduplication
                dedup_key = f"{rule.name}:{json.dumps(data, sort_keys=True, default=str)}"
                if dedup_key in self._dedup_cache:
                    continue
                self._dedup_cache.add(dedup_key)

                message = self._format_message(rule, event_type, data)
                alert = Alert(
                    rule_name=rule.name,
                    message=message,
                    data=data,
                    channel=rule.delivery.get("channel", ""),
                )

                try:
                    await self._deliver(alert, rule.delivery)
                    alert.delivered = True
                    alert.delivered_at = datetime.utcnow().isoformat()
                except Exception as e:
                    logger.error(f"Alert delivery failed for {rule.name}: {e}")

                rule.last_triggered = datetime.utcnow()
                rule.trigger_count += 1
                self._history.append(alert)

    def _matches(self, condition: dict, data: dict) -> bool:
        """Check if data matches a condition."""
        field_name = condition.get("field", "")
        op = condition.get("op", "eq")
        value = condition.get("value")

        actual = data.get(field_name)
        if actual is None:
            return False

        if op == "eq":
            return actual == value
        elif op == "neq":
            return actual != value
        elif op == "gt":
            return actual > value
        elif op == "lt":
            return actual < value
        elif op == "gte":
            return actual >= value
        elif op == "contains":
            return value in str(actual)
        elif op == "in":
            return actual in value
        return False

    def _format_message(self, rule: AlertRule, event_type: str, data: dict) -> str:
        """Format alert message."""
        return (
            f"[WebReaper Alert] {rule.name}\n"
            f"Event: {event_type}\n"
            f"Data: {json.dumps(data, indent=2, default=str)}"
        )

    async def _deliver(self, alert: Alert, delivery: dict):
        """Deliver alert via configured channel."""
        channel = delivery.get("channel", "")

        if channel == "slack":
            await self._send_slack(delivery["webhook_url"], alert.message)
        elif channel == "discord":
            await self._send_discord(delivery["webhook_url"], alert.message)
        elif channel == "email":
            await self._send_email(delivery, alert.message)
        elif channel == "webhook":
            await self._send_webhook(delivery["url"], alert)
        else:
            logger.warning(f"Unknown delivery channel: {channel}")

    async def _send_slack(self, webhook_url: str, message: str):
        """Send alert to Slack webhook."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json={"text": message})
            resp.raise_for_status()

    async def _send_discord(self, webhook_url: str, message: str):
        """Send alert to Discord webhook."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json={"content": message[:2000]})
            resp.raise_for_status()

    async def _send_email(self, config: dict, message: str):
        """Send alert via SMTP."""
        smtp_host = config.get("smtp_host", os.environ.get("SMTP_HOST", ""))
        smtp_port = int(config.get("smtp_port", os.environ.get("SMTP_PORT", "587")))
        smtp_user = config.get("smtp_user", os.environ.get("SMTP_USER", ""))
        smtp_pass = config.get("smtp_pass", os.environ.get("SMTP_PASS", ""))
        to_email = config.get("to_email", "")

        if not all([smtp_host, smtp_user, smtp_pass, to_email]):
            raise ValueError("Missing SMTP configuration")

        msg = MIMEText(message)
        msg["Subject"] = "[WebReaper] Alert Triggered"
        msg["From"] = smtp_user
        msg["To"] = to_email

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self._smtp_send(smtp_host, smtp_port, smtp_user, smtp_pass, msg))

    def _smtp_send(self, host, port, user, password, msg):
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)

    async def _send_webhook(self, url: str, alert: Alert):
        """Send alert to custom webhook."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={
                "rule": alert.rule_name,
                "message": alert.message,
                "data": alert.data,
                "channel": alert.channel,
            })
            resp.raise_for_status()

    def get_history(self, limit: int = 50) -> list[dict]:
        """Return recent alert history."""
        return [
            {
                "rule": a.rule_name,
                "message": a.message[:200],
                "delivered": a.delivered,
                "channel": a.channel,
                "delivered_at": a.delivered_at,
            }
            for a in self._history[-limit:]
        ]
