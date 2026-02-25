"""WebSocket endpoint for agent chat — bridges frontend to Agent Gateway."""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
logger = logging.getLogger("webreaper.chat")

connections: list[WebSocket] = []


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_tool_result(result):
    if isinstance(result, str):
        return result
    try:
        import json
        return json.dumps(result, indent=2, default=str)
    except Exception:
        return str(result)


def _chat_message(
    *,
    message_id: str,
    role: str,
    content: str,
    tool_name: str | None = None,
    tool_params: dict | None = None,
    tool_result: str | None = None,
    tool_status: str | None = None,
):
    msg = {
        "id": message_id,
        "role": role,
        "content": content,
        "timestamp": _now_iso(),
    }
    if tool_name is not None:
        msg["tool_name"] = tool_name
    if tool_params is not None:
        msg["tool_params"] = tool_params
    if tool_result is not None:
        msg["tool_result"] = tool_result
    if tool_status is not None:
        msg["tool_status"] = tool_status
    return msg


def _normalize_gateway_chunk(chunk: dict, assistant_state: dict) -> dict | None:
    """Translate gateway chunks into UI-consumable ChatMessage payloads."""
    chunk_type = chunk.get("type")

    if chunk_type == "token":
        assistant_state["content"] += chunk.get("content", "")
        return _chat_message(
            message_id=assistant_state["id"],
            role="agent",
            content=assistant_state["content"],
        )

    if chunk_type == "complete":
        # Tokens already stream as upserts. No-op to avoid duplicate final messages.
        return None

    if chunk_type == "error":
        return _chat_message(
            message_id=f"sys-{uuid4().hex[:12]}",
            role="system",
            content=chunk.get("content", "Agent error"),
        )

    if chunk_type == "tool_approval_request":
        tool_id = chunk.get("id") or f"tool-{uuid4().hex[:12]}"
        return _chat_message(
            message_id=tool_id,
            role="tool",
            content=f"Approval required for {chunk.get('tool', 'tool')}",
            tool_name=chunk.get("tool"),
            tool_params=chunk.get("params") or {},
            tool_status="pending",
        )

    if chunk_type == "tool_executing":
        tool_id = chunk.get("id") or f"tool-{uuid4().hex[:12]}"
        return _chat_message(
            message_id=tool_id,
            role="tool",
            content=f"Executing {chunk.get('tool', 'tool')}",
            tool_name=chunk.get("tool"),
            tool_params=chunk.get("params") or {},
            tool_status="approved",
        )

    if chunk_type == "tool_result":
        tool_id = chunk.get("id") or f"tool-{uuid4().hex[:12]}"
        tool_name = chunk.get("tool")
        result_text = _serialize_tool_result(chunk.get("result"))
        return _chat_message(
            message_id=tool_id,
            role="tool",
            content=f"{tool_name or 'Tool'} completed",
            tool_name=tool_name,
            tool_result=result_text,
            tool_status="completed",
        )

    if chunk_type == "tool_error":
        tool_id = chunk.get("id") or f"tool-{uuid4().hex[:12]}"
        tool_name = chunk.get("tool")
        return _chat_message(
            message_id=tool_id,
            role="tool",
            content=chunk.get("error", f"{tool_name or 'Tool'} failed"),
            tool_name=tool_name,
            tool_status="error",
        )

    if chunk_type == "tool_denied":
        tool_id = chunk.get("id") or f"tool-{uuid4().hex[:12]}"
        tool_name = chunk.get("tool")
        return _chat_message(
            message_id=tool_id,
            role="tool",
            content=chunk.get("reason", "Tool denied"),
            tool_name=tool_name,
            tool_status="denied",
        )

    # Unknown chunk types are surfaced as system messages to avoid silent drops.
    return _chat_message(
        message_id=f"sys-{uuid4().hex[:12]}",
        role="system",
        content=f"Unhandled gateway event: {chunk_type or 'unknown'}",
    )


@router.websocket("/chat")
async def websocket_chat(websocket: WebSocket):
    """Main chat WebSocket — bridges user <-> agent."""
    await websocket.accept()
    connections.append(websocket)
    logger.info(f"Chat client connected. Total: {len(connections)}")

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "chat_message":
                user_msg = data.get("content", "")
                from webreaper.gateway.gateway import AgentGateway
                gateway = AgentGateway.instance()

                if not gateway.is_connected():
                    await websocket.send_json(_chat_message(
                        message_id=f"sys-{uuid4().hex[:12]}",
                        role="system",
                        content="No agent connected. Go to Settings to configure an agent provider.",
                    ))
                    continue

                assistant_state = {"id": f"agent-{uuid4().hex[:12]}", "content": ""}
                async for chunk in gateway.send_message(user_msg):
                    normalized = _normalize_gateway_chunk(chunk, assistant_state)
                    if normalized:
                        await websocket.send_json(normalized)

            elif msg_type == "tool_approve":
                tool_id = data.get("message_id")
                from webreaper.gateway.gateway import AgentGateway
                gateway = AgentGateway.instance()
                await gateway.approve_tool(tool_id)

            elif msg_type == "tool_deny":
                tool_id = data.get("message_id")
                from webreaper.gateway.gateway import AgentGateway
                gateway = AgentGateway.instance()
                await gateway.deny_tool(tool_id)

    except WebSocketDisconnect:
        connections.remove(websocket)
        logger.info(f"Chat client disconnected. Total: {len(connections)}")
    except Exception as e:
        logger.error(f"Chat WebSocket error: {e}")
        if websocket in connections:
            connections.remove(websocket)


async def broadcast_to_chat(message: dict):
    """Send a message to all connected chat clients."""
    for conn in connections[:]:
        try:
            await conn.send_json(message)
        except Exception:
            connections.remove(conn)
