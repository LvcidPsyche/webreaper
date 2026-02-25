from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScanContext:
    url: str
    headers: dict[str, str]
    body: str
    forms: list[dict[str, Any]] = field(default_factory=list)
    auto_attack: bool = False
    aggressive: bool = False


@dataclass
class ScanOutput:
    findings: list[dict[str, Any]] = field(default_factory=list)
    technology: dict[str, Any] = field(default_factory=dict)
    passive_modules: list[str] = field(default_factory=list)
    active_modules: list[str] = field(default_factory=list)
