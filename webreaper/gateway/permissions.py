"""Command authorization layer for agent tool execution."""

import json
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class PermissionLevel(Enum):
    AUTO_ALLOW = "auto_allow"
    REQUIRES_APPROVAL = "requires_approval"
    BLOCKED = "blocked"


def _audit_log_path() -> Path:
    log_dir = Path(os.path.expanduser("~/.webreaper/logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "audit.log"


def log_audit_event(tool_name: str, action: str, outcome: str, user_id: str = "agent", params: dict = None):
    """Append a JSONL audit entry to ~/.webreaper/logs/audit.log."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool_name,
        "action": action,
        "outcome": outcome,
        "user_id": user_id,
        "params": params or {},
    }
    try:
        with open(_audit_log_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # Never let audit logging crash the request


TOOL_PERMISSIONS = {
    # READ ops — auto-allowed
    "crawl": PermissionLevel.AUTO_ALLOW,
    "security_scan": PermissionLevel.AUTO_ALLOW,
    "fingerprint": PermissionLevel.AUTO_ALLOW,
    "blogwatch": PermissionLevel.AUTO_ALLOW,
    "digest": PermissionLevel.AUTO_ALLOW,
    "search": PermissionLevel.AUTO_ALLOW,
    "query_results": PermissionLevel.AUTO_ALLOW,

    # WRITE ops — require user approval
    "watch": PermissionLevel.REQUIRES_APPROVAL,
    "export": PermissionLevel.REQUIRES_APPROVAL,
    "mission": PermissionLevel.REQUIRES_APPROVAL,

    # DANGEROUS ops — blocked by default
    "security_scan_attack": PermissionLevel.BLOCKED,
}


def check_permission(tool_name: str) -> PermissionLevel:
    return TOOL_PERMISSIONS.get(tool_name, PermissionLevel.REQUIRES_APPROVAL)
