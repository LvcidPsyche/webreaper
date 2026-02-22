"""Pydantic response models for the API."""

from pydantic import BaseModel


class JobResponse(BaseModel):
    job_id: str
    status: str
    target_urls: list[str]


class HealthResponse(BaseModel):
    status: str
    version: str


class SecuritySummary(BaseModel):
    total: int
    by_severity: dict[str, int]


class AgentStatus(BaseModel):
    connected: bool
    provider: str | None = None
    tools_available: int = 0
