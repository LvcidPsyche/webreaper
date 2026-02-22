"""Pydantic request models for the API."""

from pydantic import BaseModel, Field


class CrawlRequest(BaseModel):
    urls: list[str]
    depth: int = Field(default=3, ge=0, le=10)
    concurrency: int = Field(default=100, ge=1, le=1000)
    stealth: bool = False
    tor: bool = False
    rate_limit: float = Field(default=10.0, ge=0)
    respect_robots: bool = False
    genre: str | None = None


class SecurityScanRequest(BaseModel):
    url: str
    auto_attack: bool = False
    xss: bool = True
    sqli: bool = True


class AgentConnectRequest(BaseModel):
    provider: str
    config: dict


class MissionRequest(BaseModel):
    type: str  # COMPETITIVE_INTEL, THREAT_HUNT, MARKET_RESEARCH, DEEP_PROFILE
    brief: str
    auto_execute: bool = False


class AlertRuleRequest(BaseModel):
    name: str
    condition: dict
    delivery: dict
    enabled: bool = True
