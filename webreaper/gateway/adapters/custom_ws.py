"""Custom WebSocket adapter — connects to any WebSocket-based agent endpoint."""

import asyncio
import json
import logging
from typing import AsyncIterator, Optional

import websockets

from .base import AgentAdapter

logger = logging.getLogger("webreaper.gateway.custom_ws")


class CustomWSAdapter(AgentAdapter):
    """Generic WebSocket adapter for custom agent endpoints.

    Expects the remote to accept JSON messages and respond with JSON chunks
    in the standard format:
      {"type": "token|tool_call|complete|error", ...}
    """

    def __init__(self):
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._uri: str = ""
        self._connected = False
        self._headers: dict = {}

    async def connect(self, config: dict) -> bool:
        self._uri = config["uri"]
        self._headers = config.get("headers", {})

        try:
            self._ws = await websockets.connect(
                self._uri,
                extra_headers=self._headers,
                ping_interval=30,
                ping_timeout=10,
            )
            self._connected = True
            logger.info(f"Custom WS adapter connected to {self._uri}")
            return True
        except Exception as e:
            logger.error(f"Custom WS connection failed: {e}")
            return False

    async def disconnect(self):
        self._connected = False
        if self._ws:
            await self._ws.close()

    async def send(self, message: str, tools: list[dict]) -> AsyncIterator[dict]:
        if not self._ws or not self._connected:
            yield {"type": "error", "content": "Custom WS not connected"}
            return

        await self._ws.send(json.dumps({
            "type": "message",
            "content": message,
            "tools": tools,
        }))

        while True:
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=120)
                chunk = json.loads(raw)
                yield chunk
                if chunk.get("type") in ("complete", "error"):
                    break
            except asyncio.TimeoutError:
                yield {"type": "error", "content": "Response timeout"}
                break
            except websockets.ConnectionClosed:
                self._connected = False
                yield {"type": "error", "content": "Connection closed"}
                break

    def is_connected(self) -> bool:
        return self._connected and self._ws is not None

    def provider_name(self) -> str:
        return "Custom WebSocket"
