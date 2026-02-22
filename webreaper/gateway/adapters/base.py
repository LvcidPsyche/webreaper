"""Base adapter for agent providers."""

from abc import ABC, abstractmethod
from typing import AsyncIterator


class AgentAdapter(ABC):
    """Abstract base for all agent provider adapters."""

    @abstractmethod
    async def connect(self, config: dict) -> bool:
        """Establish connection. Returns True on success."""
        ...

    @abstractmethod
    async def disconnect(self):
        """Close connection."""
        ...

    @abstractmethod
    async def send(self, message: str, tools: list[dict]) -> AsyncIterator[dict]:
        """Send message to agent, yield response chunks.

        Each chunk is a dict with:
          {"type": "token", "content": "..."} — text token
          {"type": "tool_call", "tool": "crawl", "params": {...}, "id": "..."} — tool request
          {"type": "tool_result", "id": "...", "result": {...}} — tool result
          {"type": "complete"} — end of response
          {"type": "error", "content": "..."} — error
        """
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        ...

    @abstractmethod
    def provider_name(self) -> str:
        ...
