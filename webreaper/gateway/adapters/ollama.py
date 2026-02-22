"""Ollama local adapter — connects to local Ollama instance."""

import json
import logging
import os
from typing import AsyncIterator

import httpx

from .base import AgentAdapter

logger = logging.getLogger("webreaper.gateway.ollama")


class OllamaAdapter(AgentAdapter):
    """Adapter for local Ollama models with tool calling support."""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        self._connected = False
        self._base_url = "http://localhost:11434"
        self._model = "llama3.1"
        self._conversation: list[dict] = []

    async def connect(self, config: dict) -> bool:
        self._base_url = config.get("base_url", "http://localhost:11434")
        self._model = config.get("model", "llama3.1")
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=120)

        try:
            resp = await self._client.get("/api/tags")
            if resp.status_code == 200:
                self._connected = True
                self._conversation = []
                logger.info(f"Ollama adapter connected (model: {self._model})")
                return True
            logger.error(f"Ollama not responding: {resp.status_code}")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Ollama: {e}")
            return False

    async def disconnect(self):
        self._connected = False
        if self._client:
            await self._client.aclose()
            self._client = None
        self._conversation = []

    async def send(self, message: str, tools: list[dict]) -> AsyncIterator[dict]:
        if not self._client:
            yield {"type": "error", "content": "Ollama not connected"}
            return

        self._conversation.append({"role": "user", "content": message})

        ollama_tools = [
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
            resp = await self._client.post("/api/chat", json={
                "model": self._model,
                "messages": self._conversation,
                "tools": ollama_tools,
                "stream": False,
            })

            if resp.status_code != 200:
                yield {"type": "error", "content": f"Ollama error: {resp.status_code}"}
                return

            data = resp.json()
            msg = data.get("message", {})

            if msg.get("content"):
                yield {"type": "token", "content": msg["content"]}

            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    yield {
                        "type": "tool_call",
                        "tool": fn.get("name", ""),
                        "params": fn.get("arguments", {}),
                        "id": tc.get("id", ""),
                    }

            self._conversation.append(msg)
            yield {"type": "complete"}

        except Exception as e:
            logger.error(f"Ollama error: {e}")
            yield {"type": "error", "content": str(e)}

    def is_connected(self) -> bool:
        return self._connected

    def provider_name(self) -> str:
        return "Ollama"
