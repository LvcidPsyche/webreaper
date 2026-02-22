"""Command authorization layer for agent tool execution."""

from enum import Enum


class PermissionLevel(Enum):
    AUTO_ALLOW = "auto_allow"
    REQUIRES_APPROVAL = "requires_approval"
    BLOCKED = "blocked"


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
