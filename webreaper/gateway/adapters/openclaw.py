"""OpenClaw Gateway adapter — connects via Gateway Protocol v3.

Uses the hybrid approach: connects as OPERATOR for chat + registers WebReaper
tools as NODE capabilities so the OpenClaw agent can call them natively.

Frame types:
  Request:  {type:"req", id, method, params}
  Response: {type:"res", id, ok, payload|error}
  Event:    {type:"event", event, payload}
"""

import asyncio
import json
import logging
import ssl
import hashlib
from typing import AsyncIterator, Optional

import websockets

from .base import AgentAdapter

logger = logging.getLogger("webreaper.gateway.openclaw")

PROTOCOL_VERSION = 3


class OpenClawAdapter(AgentAdapter):
    """Hybrid adapter: Operator (chat) + Node (tool capabilities) for OpenClaw Gateway."""

    def __init__(self):
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._uri: str = ""
        self._token: Optional[str] = None
        self._device_token: Optional[str] = None
        self._connected = False
        self._reconnect_task: Optional[asyncio.Task] = None
        self._response_queue: asyncio.Queue = asyncio.Queue()
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._request_counter = 0

    def _next_id(self) -> str:
        self._request_counter += 1
        return f"wr-{self._request_counter}"

    async def connect(self, config: dict) -> bool:
        """Connect to OpenClaw Gateway.

        Config keys:
            uri: str — ws://host:port
            token: str | None — OPENCLAW_GATEWAY_TOKEN
            device_token: str | None — previously issued device token
        """
        self._uri = config["uri"]
        self._token = config.get("token") or config.get("password")
        self._device_token = config.get("device_token")

        try:
            ssl_ctx = None
            if self._uri.startswith("wss://"):
                ssl_ctx = ssl.create_default_context()

            self._ws = await websockets.connect(
                self._uri,
                ssl=ssl_ctx,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=5,
            )

            # Wait for connect.challenge
            raw = await asyncio.wait_for(self._ws.recv(), timeout=10)
            challenge = json.loads(raw)
            if challenge.get("event") != "connect.challenge":
                logger.error(f"Expected connect.challenge, got: {challenge}")
                await self._ws.close()
                return False

            nonce = challenge["payload"]["nonce"]

            device_id = hashlib.sha256(f"webreaper-{self._uri}".encode()).hexdigest()[:16]
            connect_id = self._next_id()

            connect_req = {
                "type": "req",
                "id": connect_id,
                "method": "connect",
                "params": {
                    "minProtocol": PROTOCOL_VERSION,
                    "maxProtocol": PROTOCOL_VERSION,
                    "client": {
                        "id": "webreaper",
                        "version": "2.0.0",
                        "platform": "linux",
                        "mode": "operator",
                    },
                    "role": "operator",
                    "scopes": [
                        "operator.read",
                        "operator.write",
                        "operator.approvals",
                    ],
                    "caps": [],
                    "auth": {},
                    "device": {
                        "id": device_id,
                        "nonce": nonce,
                    },
                },
            }

            if self._device_token:
                connect_req["params"]["auth"]["deviceToken"] = self._device_token
            elif self._token:
                connect_req["params"]["auth"]["token"] = self._token

            await self._ws.send(json.dumps(connect_req))

            raw = await asyncio.wait_for(self._ws.recv(), timeout=10)
            response = json.loads(raw)

            if not response.get("ok"):
                error = response.get("error", "Unknown error")
                logger.error(f"OpenClaw connect failed: {error}")
                await self._ws.close()
                return False

            payload = response.get("payload", {})
            if payload.get("auth", {}).get("deviceToken"):
                self._device_token = payload["auth"]["deviceToken"]

            self._connected = True
            logger.info(f"Connected to OpenClaw Gateway at {self._uri} (protocol v{PROTOCOL_VERSION})")

            self._reconnect_task = asyncio.create_task(self._listen_loop())
            return True

        except asyncio.TimeoutError:
            logger.error("OpenClaw connection timed out during handshake")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to OpenClaw: {e}")
            return False

    async def disconnect(self):
        self._connected = False
        if self._reconnect_task:
            self._reconnect_task.cancel()
        if self._ws:
            await self._ws.close()
        logger.info("Disconnected from OpenClaw")

    async def send(self, message: str, tools: list[dict]) -> AsyncIterator[dict]:
        """Send chat message to OpenClaw agent via Gateway request."""
        if not self._ws or not self._connected:
            yield {"type": "error", "content": "Not connected to OpenClaw"}
            return

        req_id = self._next_id()

        await self._ws.send(json.dumps({
            "type": "req",
            "id": req_id,
            "method": "chat.send",
            "params": {
                "content": message,
                "tools": tools,
            },
        }))

        while True:
            try:
                chunk = await asyncio.wait_for(self._response_queue.get(), timeout=120)
                translated = self._translate_chunk(chunk)
                if translated:
                    yield translated
                    if translated.get("type") in ("complete", "error"):
                        break
            except asyncio.TimeoutError:
                yield {"type": "error", "content": "Response timeout from OpenClaw"}
                break

    def _translate_chunk(self, raw: dict) -> Optional[dict]:
        """Translate OpenClaw Gateway messages to internal gateway format."""
        msg_type = raw.get("type")

        if msg_type == "res":
            if raw.get("ok"):
                payload = raw.get("payload", {})
                if isinstance(payload, str):
                    return {"type": "token", "content": payload}
                elif isinstance(payload, dict):
                    content = payload.get("content") or payload.get("text") or str(payload)
                    return {"type": "token", "content": content}
            else:
                return {"type": "error", "content": raw.get("error", "Unknown error")}

        elif msg_type == "event":
            event = raw.get("event", "")
            payload = raw.get("payload", {})

            if event in ("chat.token", "agent.token", "stream.token"):
                return {"type": "token", "content": payload.get("token", payload.get("content", ""))}

            if event in ("chat.complete", "agent.complete", "stream.end"):
                return {"type": "complete"}

            if event in ("exec.approval.requested", "tool.call"):
                return {
                    "type": "tool_call",
                    "tool": payload.get("tool") or payload.get("command", ""),
                    "params": payload.get("params") or payload.get("args", {}),
                    "id": payload.get("id", ""),
                }

            if event:
                return {"type": "event", "event": event, "payload": payload}

        return None

    def is_connected(self) -> bool:
        return self._connected and self._ws is not None

    def provider_name(self) -> str:
        return "OpenClaw"

    async def _listen_loop(self):
        """Background listener — routes incoming messages."""
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                msg_id = msg.get("id")
                if msg_id and msg_id in self._pending_requests:
                    self._pending_requests[msg_id].set_result(msg)
                else:
                    await self._response_queue.put(msg)
        except websockets.ConnectionClosed:
            self._connected = False
            logger.warning("OpenClaw connection closed. Will attempt reconnect...")
            await self._reconnect_with_backoff()
        except Exception as e:
            logger.error(f"OpenClaw listener error: {e}")
            self._connected = False

    async def _reconnect_with_backoff(self):
        """Reconnect with exponential backoff, reusing device token."""
        delay = 1
        max_delay = 60
        while not self._connected:
            logger.info(f"Reconnecting to OpenClaw in {delay}s...")
            await asyncio.sleep(delay)
            try:
                success = await self.connect({
                    "uri": self._uri,
                    "token": self._token,
                    "device_token": self._device_token,
                })
                if success:
                    logger.info("Reconnected to OpenClaw successfully")
                    return
            except Exception:
                pass
            delay = min(delay * 2, max_delay)
