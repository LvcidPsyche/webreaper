"""REST endpoints for agent provider management (CRUD)."""

import json
import uuid
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()
logger = logging.getLogger("webreaper.agents")

PROVIDERS_FILE = Path.home() / ".config" / "webreaper" / "providers.json"


def _load_providers() -> list[dict]:
    if PROVIDERS_FILE.exists():
        try:
            return json.loads(PROVIDERS_FILE.read_text())
        except Exception:
            pass
    return []


def _save_providers(providers: list[dict]):
    PROVIDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROVIDERS_FILE.write_text(json.dumps(providers, indent=2))
    os.chmod(PROVIDERS_FILE, 0o600)


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "***"
    return key[:4] + "..." + key[-4:]


def _provider_response(p: dict) -> dict:
    """Return provider dict with API key masked."""
    return {
        "id": p["id"],
        "name": p["name"],
        "type": p["type"],
        "base_url": p.get("base_url", ""),
        "api_key_set": bool(p.get("api_key", "")),
        "model": p.get("model", ""),
        "status": p.get("status", "disconnected"),
        "last_checked": p.get("last_checked"),
    }


class ProviderCreate(BaseModel):
    name: str
    type: str
    base_url: str = ""
    api_key: str = ""
    model: str = ""


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None


@router.get("")
async def list_providers():
    """List configured agent providers."""
    providers = _load_providers()
    return [_provider_response(p) for p in providers]


@router.post("")
async def create_provider(req: ProviderCreate):
    """Add a new agent provider."""
    providers = _load_providers()
    provider = {
        "id": str(uuid.uuid4()),
        "name": req.name,
        "type": req.type,
        "base_url": req.base_url,
        "api_key": req.api_key,
        "model": req.model,
        "status": "disconnected",
        "last_checked": None,
    }
    providers.append(provider)
    _save_providers(providers)
    return _provider_response(provider)


@router.put("/{provider_id}")
async def update_provider(provider_id: str, req: ProviderUpdate):
    """Update an existing agent provider."""
    providers = _load_providers()
    for p in providers:
        if p["id"] == provider_id:
            if req.name is not None:
                p["name"] = req.name
            if req.type is not None:
                p["type"] = req.type
            if req.base_url is not None:
                p["base_url"] = req.base_url
            if req.api_key:  # only update if a new key was provided (empty = unchanged)
                p["api_key"] = req.api_key
            if req.model is not None:
                p["model"] = req.model
            p["status"] = "disconnected"
            _save_providers(providers)
            return _provider_response(p)
    raise HTTPException(status_code=404, detail="Provider not found")


@router.delete("/{provider_id}")
async def delete_provider(provider_id: str):
    """Delete an agent provider."""
    providers = _load_providers()
    updated = [p for p in providers if p["id"] != provider_id]
    if len(updated) == len(providers):
        raise HTTPException(status_code=404, detail="Provider not found")
    _save_providers(updated)
    return {"status": "deleted", "id": provider_id}


@router.post("/{provider_id}/test")
async def test_provider(provider_id: str):
    """Test connectivity to an agent provider."""
    providers = _load_providers()
    provider = next((p for p in providers if p["id"] == provider_id), None)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    ok = False
    try:
        ptype = provider.get("type", "")
        api_key = provider.get("api_key", "")
        base_url = provider.get("base_url", "")
        model = provider.get("model", "")

        import httpx
        if ptype == "anthropic":
            if not api_key:
                ok = False
            else:
                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                        json={"model": model, "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]},
                    )
                    ok = r.status_code in (200, 400)  # 400 = auth ok but bad params
        elif ptype == "openai":
            url = base_url.rstrip("/") or "https://api.openai.com/v1"
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{url}/models", headers={"Authorization": f"Bearer {api_key}"})
                ok = r.status_code == 200
        elif ptype == "ollama":
            url = base_url.rstrip("/") or "http://localhost:11434"
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(f"{url}/api/tags")
                ok = r.status_code == 200
        elif ptype == "openclaw":
            # OpenClaw VPS gateway — check health endpoint
            url = base_url.rstrip("/") if base_url else "http://76.13.114.80"
            async with httpx.AsyncClient(timeout=10) as client:
                try:
                    r = await client.get(f"{url}/health")
                    ok = r.status_code < 500
                except Exception:
                    # Fall back to models list (OpenAI-compatible)
                    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                    r = await client.get(f"{url}/v1/models", headers=headers)
                    ok = r.status_code < 500
        else:
            # custom — just try a HEAD on base_url
            if base_url:
                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.head(base_url)
                    ok = r.status_code < 500
    except Exception as e:
        logger.debug(f"Provider test failed: {e}")
        ok = False

    # Update status in storage
    now = datetime.now(timezone.utc).isoformat()
    for p in providers:
        if p["id"] == provider_id:
            p["status"] = "connected" if ok else "error"
            p["last_checked"] = now
    _save_providers(providers)

    return {"ok": ok}
