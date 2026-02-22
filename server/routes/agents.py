"""REST endpoints for agent provider management."""

import logging
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from webreaper.gateway.gateway import AgentGateway
from webreaper.gateway.registry import ProviderRegistry

router = APIRouter()
logger = logging.getLogger("webreaper.agents")


class ConnectRequest(BaseModel):
    provider: str
    config: dict


class SaveConfigRequest(BaseModel):
    provider: str
    config: dict


@router.get("/providers")
async def list_providers():
    """List available agent providers and their status."""
    registry = ProviderRegistry()
    providers = registry.list_providers()
    gateway = AgentGateway.instance()
    return {
        "providers": providers,
        "connected": gateway.is_connected(),
        "active_provider": gateway._adapter.provider_name() if gateway._adapter else None,
    }


@router.post("/connect")
async def connect_provider(req: ConnectRequest):
    """Connect to an agent provider."""
    gateway = AgentGateway.instance()
    success = await gateway.connect(req.provider, req.config)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to connect to {req.provider}")
    return {"status": "connected", "provider": req.provider}


@router.post("/disconnect")
async def disconnect_provider():
    """Disconnect from current agent provider."""
    gateway = AgentGateway.instance()
    await gateway.disconnect()
    return {"status": "disconnected"}


@router.post("/config")
async def save_provider_config(req: SaveConfigRequest):
    """Save provider configuration (API keys stored securely)."""
    registry = ProviderRegistry()
    registry.save_config(req.provider, req.config)
    return {"status": "saved", "provider": req.provider}


@router.get("/config/{provider}")
async def get_provider_config(provider: str):
    """Get saved provider config (API keys masked)."""
    registry = ProviderRegistry()
    config = registry.get_config(provider)
    if not config:
        raise HTTPException(status_code=404, detail="No config for this provider")
    masked = {}
    for k, v in config.items():
        if "key" in k.lower() or "token" in k.lower() or "password" in k.lower():
            masked[k] = v[:4] + "..." + v[-4:] if len(str(v)) > 8 else "***"
        else:
            masked[k] = v
    return masked
