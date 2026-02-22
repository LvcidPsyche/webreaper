"""Agent provider registry and API key vault."""

import json
import os
import logging
from pathlib import Path
from typing import Optional

from .adapters.base import AgentAdapter
from .adapters.openclaw import OpenClawAdapter
from .adapters.claude_api import ClaudeAPIAdapter
from .adapters.openai_api import OpenAIAPIAdapter
from .adapters.ollama import OllamaAdapter
from .adapters.custom_ws import CustomWSAdapter

logger = logging.getLogger("webreaper.gateway.registry")

VAULT_PATH = Path.home() / ".config" / "webreaper" / "agent_vault.json"


class ProviderRegistry:
    """Registry of available agent providers."""

    def __init__(self):
        self._adapters = {
            "openclaw": OpenClawAdapter,
            "claude_api": ClaudeAPIAdapter,
            "openai_api": OpenAIAPIAdapter,
            "ollama": OllamaAdapter,
            "custom_ws": CustomWSAdapter,
        }
        self._configs: dict[str, dict] = {}
        self._load_vault()

    def get_adapter(self, name: str) -> Optional[AgentAdapter]:
        cls = self._adapters.get(name)
        if cls:
            return cls()
        return None

    def list_providers(self) -> list[dict]:
        return [
            {"name": name, "configured": name in self._configs}
            for name in self._adapters
        ]

    def save_config(self, provider: str, config: dict):
        """Save provider config (API keys stored in vault)."""
        self._configs[provider] = config
        self._save_vault()

    def get_config(self, provider: str) -> Optional[dict]:
        return self._configs.get(provider)

    def _load_vault(self):
        if VAULT_PATH.exists():
            try:
                self._configs = json.loads(VAULT_PATH.read_text())
            except Exception as e:
                logger.error(f"Failed to load vault: {e}")

    def _save_vault(self):
        VAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        VAULT_PATH.write_text(json.dumps(self._configs, indent=2))
        os.chmod(VAULT_PATH, 0o600)
