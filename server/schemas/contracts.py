from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class ApiError(BaseModel):
    detail: str


class SSEEnvelope(BaseModel):
    type: str
    ts: str
    payload: dict[str, Any] | list[Any] | str | int | float | bool | None = None


class WebSocketEnvelope(BaseModel):
    type: str
    payload: dict[str, Any] | list[Any] | str | int | float | bool | None = None


class SecurityFindingContract(BaseModel):
    id: str
    type: str | None = None
    category: str
    severity: Literal['critical', 'high', 'medium', 'low', 'info']
    url: str
    title: str | None = None
    evidence: str | None = None
    remediation: str | None = None
    found_at: str | None = None
    triage_status: str | None = 'open'
    triage_assignee: str | None = None
    triage_tags: list[str] = Field(default_factory=list)


class DataCrawlContract(BaseModel):
    id: str
    target_url: str | None = None
    status: str
    pages_crawled: int | None = 0
    pages_failed: int | None = 0
    started_at: str | None = None
    completed_at: str | None = None


class EndpointInventoryItemContract(BaseModel):
    id: str
    host: str
    scheme: str
    method: str
    path: str
    query_params: list[str] = Field(default_factory=list)
    body_param_names: list[str] = Field(default_factory=list)
    content_types: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
