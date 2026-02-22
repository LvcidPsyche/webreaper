"""Echo — Content Intelligence Engine.

Semantic change detection, content classification, and Wayback Machine
integration for building content timelines.
"""

import asyncio
import difflib
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import httpx

logger = logging.getLogger("webreaper.echo")


class ChangeType(Enum):
    PRICING = "pricing"
    POLICY = "policy"
    FEATURE = "feature"
    LEGAL = "legal"
    CONTENT = "content"
    LAYOUT = "layout"
    METADATA = "metadata"
    UNKNOWN = "unknown"


@dataclass
class ContentChange:
    """A detected content change with classification."""
    url: str
    change_type: ChangeType
    summary: str
    diff: str
    old_hash: str
    new_hash: str
    detected_at: str = ""
    confidence: float = 0.0


class Echo:
    """Content intelligence engine with semantic change detection."""

    # Keywords that indicate change type
    CHANGE_INDICATORS = {
        ChangeType.PRICING: ["price", "cost", "$", "€", "£", "per month", "per year", "plan", "tier", "subscription", "billing"],
        ChangeType.POLICY: ["privacy", "cookie", "data collection", "gdpr", "ccpa", "opt-out", "consent"],
        ChangeType.FEATURE: ["new feature", "update", "improved", "now supports", "introducing", "launch"],
        ChangeType.LEGAL: ["terms of service", "tos", "agreement", "liability", "warranty", "dispute"],
        ChangeType.METADATA: ["title", "description", "og:", "meta"],
    }

    def __init__(self):
        self._snapshots: dict[str, str] = {}

    def detect_change(self, url: str, old_text: str, new_text: str) -> Optional[ContentChange]:
        """Detect and classify changes between two versions of content."""
        old_hash = hashlib.sha256(old_text.encode()).hexdigest()
        new_hash = hashlib.sha256(new_text.encode()).hexdigest()

        if old_hash == new_hash:
            return None

        diff = self._generate_diff(old_text, new_text)
        if not diff.strip():
            return None

        change_type = self._classify_change(diff)
        summary = self._summarize_diff(diff)

        return ContentChange(
            url=url,
            change_type=change_type,
            summary=summary,
            diff=diff,
            old_hash=old_hash,
            new_hash=new_hash,
            detected_at=datetime.utcnow().isoformat(),
            confidence=0.8,
        )

    def _generate_diff(self, old: str, new: str) -> str:
        """Generate unified diff between two text versions."""
        old_lines = old.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)
        diff = difflib.unified_diff(old_lines, new_lines, lineterm="")
        return "".join(list(diff)[:200])  # Cap at 200 lines

    def _classify_change(self, diff: str) -> ChangeType:
        """Classify what type of change occurred based on diff content."""
        diff_lower = diff.lower()
        scores: dict[ChangeType, int] = {}

        for change_type, keywords in self.CHANGE_INDICATORS.items():
            score = sum(1 for kw in keywords if kw in diff_lower)
            if score > 0:
                scores[change_type] = score

        if scores:
            return max(scores, key=scores.get)
        return ChangeType.CONTENT

    def _summarize_diff(self, diff: str) -> str:
        """Generate a human-readable summary of the diff."""
        added = [l[1:].strip() for l in diff.split("\n") if l.startswith("+") and not l.startswith("+++")]
        removed = [l[1:].strip() for l in diff.split("\n") if l.startswith("-") and not l.startswith("---")]

        parts = []
        if added:
            parts.append(f"Added {len(added)} lines")
        if removed:
            parts.append(f"Removed {len(removed)} lines")
        return "; ".join(parts) if parts else "Content changed"

    async def wayback_history(self, url: str, limit: int = 20) -> list[dict]:
        """Fetch historical snapshots from the Wayback Machine."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://web.archive.org/cdx/search/cdx",
                    params={
                        "url": url,
                        "output": "json",
                        "limit": limit,
                        "fl": "timestamp,statuscode,digest,length",
                    },
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                if len(data) < 2:
                    return []

                headers = data[0]
                snapshots = []
                for row in data[1:]:
                    entry = dict(zip(headers, row))
                    ts = entry["timestamp"]
                    entry["wayback_url"] = f"https://web.archive.org/web/{ts}/{url}"
                    entry["date"] = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
                    snapshots.append(entry)

                return snapshots
        except Exception as e:
            logger.warning(f"Wayback Machine lookup failed: {e}")
            return []

    async def wayback_fetch(self, url: str, timestamp: str) -> Optional[str]:
        """Fetch a specific Wayback Machine snapshot."""
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(
                    f"https://web.archive.org/web/{timestamp}id_/{url}"
                )
                if resp.status_code == 200:
                    return resp.text
        except Exception as e:
            logger.warning(f"Wayback fetch failed: {e}")
        return None

    async def build_timeline(self, url: str, limit: int = 10) -> list[dict]:
        """Build a content change timeline using Wayback Machine snapshots."""
        snapshots = await self.wayback_history(url, limit=limit)
        if len(snapshots) < 2:
            return []

        timeline = []
        prev_content = None

        for snap in snapshots[:limit]:
            content = await self.wayback_fetch(url, snap["timestamp"])
            if not content:
                continue

            if prev_content:
                change = self.detect_change(url, prev_content, content)
                if change:
                    timeline.append({
                        "date": snap["date"],
                        "change_type": change.change_type.value,
                        "summary": change.summary,
                        "wayback_url": snap["wayback_url"],
                    })

            prev_content = content

        return timeline
