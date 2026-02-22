"""Claude API adapter — uses Anthropic API with tool use for agent capabilities."""

import json
import logging
import os
from typing import AsyncIterator

import anthropic

from .base import AgentAdapter

logger = logging.getLogger("webreaper.gateway.claude")


class ClaudeAPIAdapter(AgentAdapter):
    """Adapter for Claude API with tool_use for WebReaper tool execution."""

    def __init__(self):
        self._client: anthropic.AsyncAnthropic | None = None
        self._connected = False
        self._conversation: list[dict] = []
        self._model = "claude-sonnet-4-6"

    async def connect(self, config: dict) -> bool:
        api_key = config.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error("No Anthropic API key provided")
            return False

        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = config.get("model", "claude-sonnet-4-6")
        self._connected = True
        self._conversation = []
        logger.info(f"Claude API adapter connected (model: {self._model})")
        return True

    async def disconnect(self):
        self._connected = False
        self._client = None
        self._conversation = []

    async def send(self, message: str, tools: list[dict]) -> AsyncIterator[dict]:
        if not self._client:
            yield {"type": "error", "content": "Claude API not connected"}
            return

        self._conversation.append({"role": "user", "content": message})

        claude_tools = [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
            }
            for t in tools
        ]

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                system="You are an AI agent controlling WebReaper, a web intelligence suite. Use the provided tools to fulfill user requests. Be concise and action-oriented.",
                messages=self._conversation,
                tools=claude_tools,
            )

            for block in response.content:
                if block.type == "text":
                    yield {"type": "token", "content": block.text}
                elif block.type == "tool_use":
                    yield {
                        "type": "tool_call",
                        "tool": block.name,
                        "params": block.input,
                        "id": block.id,
                    }

            self._conversation.append({"role": "assistant", "content": response.content})
            yield {"type": "complete"}

        except Exception as e:
            logger.error(f"Claude API error: {e}")
            yield {"type": "error", "content": str(e)}

    def is_connected(self) -> bool:
        return self._connected

    def provider_name(self) -> str:
        return "Claude API"
