"""Scope matching utilities for workspaces."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from typing import Any
from urllib.parse import urlparse


@dataclass
class ScopeDecision:
    allowed: bool
    reason: str
    matched_rule_id: str | None = None


def evaluate_scope(url: str, scope_rules: list[dict[str, Any]] | None) -> ScopeDecision:
    """Evaluate URL against workspace include/exclude scope rules.

    Rules shape (minimal):
      {id?, mode: include|exclude, type: host|host_glob|path_prefix|scheme, value: str}
    If no include rules are present, default is allow unless excluded.
    If include rules exist, URL must match at least one include and no excludes.
    """
    if not scope_rules:
        return ScopeDecision(True, "no_rules")

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path or "/"
    scheme = (parsed.scheme or "").lower()

    include_rules = [r for r in scope_rules if (r.get("mode") or "include") == "include"]
    exclude_rules = [r for r in scope_rules if r.get("mode") == "exclude"]

    def matches(rule: dict[str, Any]) -> bool:
        rtype = rule.get("type")
        value = str(rule.get("value", ""))
        if rtype == "host":
            return host == value.lower()
        if rtype == "host_glob":
            return fnmatch(host, value.lower())
        if rtype == "path_prefix":
            return path.startswith(value)
        if rtype == "scheme":
            return scheme == value.lower()
        return False

    for rule in exclude_rules:
        if matches(rule):
            return ScopeDecision(False, "excluded", rule.get("id"))

    if not include_rules:
        return ScopeDecision(True, "default_allow")

    for rule in include_rules:
        if matches(rule):
            return ScopeDecision(True, "included", rule.get("id"))

    return ScopeDecision(False, "no_include_match")

