"""Agent Gateway — routes messages between agent adapters and WebReaper tools."""

import asyncio
import logging
from typing import AsyncIterator, Optional

from .adapters.base import AgentAdapter
from .tools import TOOL_MANIFEST, execute_tool
from .permissions import PermissionLevel, check_permission
from .registry import ProviderRegistry

logger = logging.getLogger("webreaper.gateway")

_instance: Optional["AgentGateway"] = None


class AgentGateway:
    """Central gateway that bridges any agent to WebReaper's tool system."""

    def __init__(self):
        self._adapter: Optional[AgentAdapter] = None
        self._registry = ProviderRegistry()
        self._pending_approvals: dict[str, asyncio.Event] = {}
        self._approval_results: dict[str, bool] = {}
        self._audit_log: list[dict] = []

    @classmethod
    def instance(cls) -> "AgentGateway":
        global _instance
        if _instance is None:
            _instance = cls()
        return _instance

    async def connect(self, provider_name: str, config: dict) -> bool:
        """Connect to an agent provider."""
        adapter = self._registry.get_adapter(provider_name)
        if not adapter:
            logger.error(f"Unknown provider: {provider_name}")
            return False

        success = await adapter.connect(config)
        if success:
            self._adapter = adapter
            logger.info(f"Gateway connected to {provider_name}")
        return success

    async def disconnect(self):
        if self._adapter:
            await self._adapter.disconnect()
            self._adapter = None

    def is_connected(self) -> bool:
        return self._adapter is not None and self._adapter.is_connected()

    async def send_message(self, message: str) -> AsyncIterator[dict]:
        """Send user message to agent, execute tool calls, yield all chunks."""
        if not self._adapter:
            yield {"type": "error", "content": "No agent connected"}
            return

        tools = TOOL_MANIFEST

        async for chunk in self._adapter.send(message, tools):
            if chunk["type"] == "tool_call":
                tool_name = chunk["tool"]
                permission = check_permission(tool_name)

                if permission == PermissionLevel.BLOCKED:
                    yield {"type": "tool_denied", "tool": tool_name, "reason": "Blocked by policy"}
                    continue

                if permission == PermissionLevel.REQUIRES_APPROVAL:
                    yield {
                        "type": "tool_approval_request",
                        "tool": tool_name,
                        "params": chunk["params"],
                        "id": chunk["id"],
                    }
                    approved = await self._wait_for_approval(chunk["id"])
                    if not approved:
                        yield {"type": "tool_denied", "tool": tool_name, "reason": "User denied"}
                        continue

                yield {"type": "tool_executing", "tool": tool_name, "params": chunk["params"]}
                try:
                    result = await execute_tool(tool_name, chunk["params"])
                    self._audit_log.append({
                        "tool": tool_name,
                        "params": chunk["params"],
                        "result": "success",
                    })
                    yield {"type": "tool_result", "tool": tool_name, "result": result, "id": chunk.get("id")}
                except Exception as e:
                    yield {"type": "tool_error", "tool": tool_name, "error": str(e)}
            else:
                yield chunk

    async def approve_tool(self, tool_id: str):
        self._approval_results[tool_id] = True
        if tool_id in self._pending_approvals:
            self._pending_approvals[tool_id].set()

    async def deny_tool(self, tool_id: str):
        self._approval_results[tool_id] = False
        if tool_id in self._pending_approvals:
            self._pending_approvals[tool_id].set()

    async def _wait_for_approval(self, tool_id: str, timeout: float = 60) -> bool:
        event = asyncio.Event()
        self._pending_approvals[tool_id] = event
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return self._approval_results.get(tool_id, False)
        except asyncio.TimeoutError:
            return False
        finally:
            self._pending_approvals.pop(tool_id, None)
            self._approval_results.pop(tool_id, None)
