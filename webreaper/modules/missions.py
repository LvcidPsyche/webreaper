"""Missions — Autonomous Research.

Takes a natural language brief, decomposes into tool calls, executes
sequentially/parallel, and aggregates results into intelligence reports.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger("webreaper.missions")


class MissionType(Enum):
    COMPETITIVE_INTEL = "competitive_intel"
    THREAT_HUNT = "threat_hunt"
    MARKET_RESEARCH = "market_research"
    DEEP_PROFILE = "deep_profile"
    CUSTOM = "custom"


class MissionStatus(Enum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class MissionStep:
    """A single step in a mission plan."""
    tool: str
    params: dict
    description: str
    status: str = "pending"
    result: Optional[dict] = None
    error: Optional[str] = None
    depends_on: list[int] = field(default_factory=list)


@dataclass
class Mission:
    """An autonomous research mission."""
    type: MissionType
    brief: str
    steps: list[MissionStep] = field(default_factory=list)
    results: dict = field(default_factory=dict)
    status: MissionStatus = MissionStatus.PENDING
    created_at: str = ""
    completed_at: Optional[str] = None


# Pre-built mission templates
MISSION_TEMPLATES = {
    MissionType.COMPETITIVE_INTEL: [
        MissionStep(tool="crawl", params={"depth": 2}, description="Crawl competitor site"),
        MissionStep(tool="fingerprint", params={}, description="Detect tech stack"),
        MissionStep(tool="security_scan", params={}, description="Security posture assessment"),
    ],
    MissionType.THREAT_HUNT: [
        MissionStep(tool="security_scan", params={"auto_attack": False}, description="Vulnerability scan"),
        MissionStep(tool="fingerprint", params={}, description="Detect tech stack for known CVEs"),
        MissionStep(tool="crawl", params={"depth": 1}, description="Surface crawl for exposed endpoints"),
    ],
    MissionType.DEEP_PROFILE: [
        MissionStep(tool="crawl", params={"depth": 3}, description="Deep crawl target"),
        MissionStep(tool="fingerprint", params={}, description="Full tech fingerprint"),
        MissionStep(tool="security_scan", params={}, description="Security assessment"),
        MissionStep(tool="blogwatch", params={}, description="Content extraction"),
    ],
    MissionType.MARKET_RESEARCH: [
        MissionStep(tool="crawl", params={"depth": 2}, description="Crawl for content"),
        MissionStep(tool="blogwatch", params={}, description="Extract articles/content"),
        MissionStep(tool="digest", params={}, description="AI summary of findings"),
    ],
}


class MissionPlanner:
    """Plans and executes autonomous research missions."""

    def __init__(self):
        self._active_missions: list[Mission] = []
        self._completed_missions: list[Mission] = []

    def create_mission(self, mission_type: str, brief: str, target_url: Optional[str] = None) -> Mission:
        """Create a new mission from a brief."""
        try:
            mtype = MissionType(mission_type)
        except ValueError:
            mtype = MissionType.CUSTOM

        mission = Mission(
            type=mtype,
            brief=brief,
            created_at=datetime.utcnow().isoformat(),
            status=MissionStatus.PLANNING,
        )

        # Use template if available, otherwise create custom plan
        if mtype in MISSION_TEMPLATES:
            template_steps = MISSION_TEMPLATES[mtype]
            for step in template_steps:
                params = dict(step.params)
                if target_url and "url" not in params:
                    params["url"] = target_url
                mission.steps.append(MissionStep(
                    tool=step.tool,
                    params=params,
                    description=step.description,
                ))
        else:
            # Custom mission — basic crawl + analysis
            if target_url:
                mission.steps = [
                    MissionStep(tool="crawl", params={"url": target_url, "depth": 2}, description="Crawl target"),
                    MissionStep(tool="fingerprint", params={"url": target_url}, description="Tech fingerprint"),
                ]

        self._active_missions.append(mission)
        return mission

    async def execute(self, mission: Mission, tool_executor) -> Mission:
        """Execute a mission plan step by step."""
        mission.status = MissionStatus.EXECUTING
        all_results = {}

        for i, step in enumerate(mission.steps):
            # Check dependencies
            for dep_idx in step.depends_on:
                dep_step = mission.steps[dep_idx]
                if dep_step.status != "completed":
                    step.status = "skipped"
                    step.error = f"Dependency step {dep_idx} not completed"
                    continue

            step.status = "running"
            try:
                result = await tool_executor(step.tool, step.params)
                step.result = result
                step.status = "completed"
                all_results[f"step_{i}_{step.tool}"] = result
            except Exception as e:
                step.status = "failed"
                step.error = str(e)
                logger.error(f"Mission step {i} ({step.tool}) failed: {e}")

        mission.results = all_results
        mission.status = MissionStatus.COMPLETED
        mission.completed_at = datetime.utcnow().isoformat()

        self._active_missions.remove(mission)
        self._completed_missions.append(mission)
        return mission

    def get_active(self) -> list[dict]:
        """Return active missions."""
        return [
            {
                "type": m.type.value,
                "brief": m.brief,
                "status": m.status.value,
                "steps_total": len(m.steps),
                "steps_completed": sum(1 for s in m.steps if s.status == "completed"),
            }
            for m in self._active_missions
        ]

    def get_completed(self, limit: int = 20) -> list[dict]:
        """Return completed missions."""
        return [
            {
                "type": m.type.value,
                "brief": m.brief,
                "status": m.status.value,
                "created_at": m.created_at,
                "completed_at": m.completed_at,
                "results_summary": {k: type(v).__name__ for k, v in m.results.items()},
            }
            for m in self._completed_missions[-limit:]
        ]

    def generate_report(self, mission: Mission) -> str:
        """Generate a markdown intelligence report from mission results."""
        lines = [
            f"# Mission Report: {mission.type.value.replace('_', ' ').title()}",
            f"**Brief:** {mission.brief}",
            f"**Status:** {mission.status.value}",
            f"**Started:** {mission.created_at}",
            f"**Completed:** {mission.completed_at or 'N/A'}",
            "",
            "## Steps",
        ]

        for i, step in enumerate(mission.steps):
            status_icon = {"completed": "+", "failed": "!", "skipped": "-"}.get(step.status, "?")
            lines.append(f"  [{status_icon}] Step {i+1}: {step.description} ({step.tool})")
            if step.error:
                lines.append(f"      Error: {step.error}")

        lines.append("")
        lines.append("## Results")

        for key, value in mission.results.items():
            lines.append(f"\n### {key}")
            if isinstance(value, dict):
                lines.append(f"```json\n{json.dumps(value, indent=2, default=str)[:2000]}\n```")
            else:
                lines.append(str(value)[:1000])

        return "\n".join(lines)
