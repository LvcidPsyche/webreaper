"""Tests for chat WebSocket normalization and tool approval forwarding."""

import sys
from types import ModuleType

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.routes import chat


class _FakeGateway:
    def __init__(self, *, connected: bool = True):
        self._connected = connected
        self.approved: list[str] = []
        self.denied: list[str] = []

    def is_connected(self) -> bool:
        return self._connected

    async def send_message(self, message: str):
        assert message == "hello"
        yield {"type": "token", "content": "Hi"}
        yield {"type": "token", "content": " there"}
        yield {"type": "tool_approval_request", "id": "tool-1", "tool": "crawl", "params": {"url": "https://example.com"}}
        yield {"type": "tool_executing", "id": "tool-1", "tool": "crawl", "params": {"url": "https://example.com"}}
        yield {"type": "tool_result", "id": "tool-1", "tool": "crawl", "result": {"ok": True}}
        yield {"type": "complete"}

    async def approve_tool(self, tool_id: str):
        self.approved.append(tool_id)

    async def deny_tool(self, tool_id: str):
        self.denied.append(tool_id)


def _install_fake_gateway_module(fake_gateway: _FakeGateway):
    fake_mod = ModuleType("webreaper.gateway.gateway")

    class AgentGateway:  # noqa: D401 - simple test stub
        @classmethod
        def instance(cls):
            return fake_gateway

    fake_mod.AgentGateway = AgentGateway
    sys.modules["webreaper.gateway.gateway"] = fake_mod


def _make_client():
    app = FastAPI()
    app.include_router(chat.router, prefix="/ws")
    return TestClient(app, raise_server_exceptions=False)


def test_chat_ws_normalizes_gateway_chunks_to_chat_messages():
    fake_gateway = _FakeGateway(connected=True)
    _install_fake_gateway_module(fake_gateway)

    with _make_client() as client:
        with client.websocket_connect("/ws/chat") as ws:
            ws.send_json({"type": "chat_message", "content": "hello"})

            assistant_1 = ws.receive_json()
            assistant_2 = ws.receive_json()
            tool_pending = ws.receive_json()
            tool_exec = ws.receive_json()
            tool_done = ws.receive_json()

    assert assistant_1["role"] == "agent"
    assert assistant_1["content"] == "Hi"
    assert assistant_2["role"] == "agent"
    assert assistant_2["id"] == assistant_1["id"]
    assert assistant_2["content"] == "Hi there"

    assert tool_pending["role"] == "tool"
    assert tool_pending["id"] == "tool-1"
    assert tool_pending["tool_name"] == "crawl"
    assert tool_pending["tool_status"] == "pending"
    assert tool_pending["tool_params"]["url"] == "https://example.com"

    assert tool_exec["role"] == "tool"
    assert tool_exec["id"] == "tool-1"
    assert tool_exec["tool_status"] == "approved"

    assert tool_done["role"] == "tool"
    assert tool_done["id"] == "tool-1"
    assert tool_done["tool_status"] == "completed"
    assert '"ok": true' in tool_done["tool_result"].lower()


def test_chat_ws_forwards_tool_approval_and_denial():
    fake_gateway = _FakeGateway(connected=True)
    _install_fake_gateway_module(fake_gateway)

    with _make_client() as client:
        with client.websocket_connect("/ws/chat") as ws:
            ws.send_json({"type": "tool_approve", "message_id": "tool-approve-1"})
            ws.send_json({"type": "tool_deny", "message_id": "tool-deny-1"})

    assert fake_gateway.approved == ["tool-approve-1"]
    assert fake_gateway.denied == ["tool-deny-1"]


def test_chat_ws_returns_system_message_when_not_connected():
    fake_gateway = _FakeGateway(connected=False)
    _install_fake_gateway_module(fake_gateway)

    with _make_client() as client:
        with client.websocket_connect("/ws/chat") as ws:
            ws.send_json({"type": "chat_message", "content": "hello"})
            msg = ws.receive_json()

    assert msg["role"] == "system"
    assert "No agent connected" in msg["content"]

