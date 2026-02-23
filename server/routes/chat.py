"""WebSocket endpoint for agent chat — bridges frontend to Agent Gateway."""

import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
logger = logging.getLogger("webreaper.chat")

connections: list[WebSocket] = []


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
                    await websocket.send_json({
                        "type": "error",
                        "content": "No agent connected. Go to Settings to configure an agent provider."
                    })
                    continue

                async for chunk in gateway.send_message(user_msg):
                    await websocket.send_json(chunk)

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
