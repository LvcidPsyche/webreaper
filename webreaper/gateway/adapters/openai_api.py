"""OpenAI API adapter — uses OpenAI API with function calling."""

import json
import logging
import os
from typing import AsyncIterator

from .base import AgentAdapter

logger = logging.getLogger("webreaper.gateway.openai")


class OpenAIAPIAdapter(AgentAdapter):
    """Adapter for OpenAI API with function calling for WebReaper tools."""

    def __init__(self):
        self._client = None
        self._connected = False
        self._conversation: list[dict] = []
        self._model = "gpt-4o"

    async def connect(self, config: dict) -> bool:
        api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.error("No OpenAI API key provided")
            return False

        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=api_key)
            self._model = config.get("model", "gpt-4o")
            self._connected = True
            self._conversation = [
                {"role": "system", "content": "You are an AI agent controlling WebReaper, a web intelligence suite. Use the provided tools to fulfill user requests. Be concise and action-oriented."}
            ]
            logger.info(f"OpenAI API adapter connected (model: {self._model})")
            return True
        except ImportError:
            logger.error("openai package not installed")
            return False

    async def disconnect(self):
        self._connected = False
        self._client = None
        self._conversation = []

    async def send(self, message: str, tools: list[dict]) -> AsyncIterator[dict]:
        if not self._client:
            yield {"type": "error", "content": "OpenAI API not connected"}
            return

        self._conversation.append({"role": "user", "content": message})

        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t.get("parameters", {"type": "object", "properties": {}}),
                },
            }
            for t in tools
        ]

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=self._conversation,
                tools=openai_tools,
                max_tokens=4096,
            )

            choice = response.choices[0]
            msg = choice.message

            if msg.content:
                yield {"type": "token", "content": msg.content}

            if msg.tool_calls:
                for tc in msg.tool_calls:
                    yield {
                        "type": "tool_call",
                        "tool": tc.function.name,
                        "params": json.loads(tc.function.arguments),
                        "id": tc.id,
                    }

            self._conversation.append(msg.model_dump())
            yield {"type": "complete"}

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            yield {"type": "error", "content": str(e)}

    def is_connected(self) -> bool:
        return self._connected

    def provider_name(self) -> str:
        return "OpenAI API"
