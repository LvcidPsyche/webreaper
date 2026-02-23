'use client';

import { useState } from 'react';
import { X, Plug } from 'lucide-react';

interface ConnectModalProps {
  open: boolean;
  onClose: () => void;
  onConnect: (config: ConnectionConfig) => void;
}

interface ConnectionConfig {
  name: string;
  type: string;
  base_url: string;
  api_key: string;
  model: string;
}

const providerDefaults: Record<string, { url: string; model: string }> = {
  openai: { url: 'https://api.openai.com/v1', model: 'gpt-4o' },
  anthropic: { url: 'https://api.anthropic.com', model: 'claude-sonnet-4-6' },
  ollama: { url: 'http://localhost:11434', model: 'llama3' },
  openclaw: { url: 'http://76.13.114.80', model: 'claude-sonnet-4-6' },
  custom: { url: '', model: '' },
};

export function ConnectModal({ open, onClose, onConnect }: ConnectModalProps) {
  const [config, setConfig] = useState<ConnectionConfig>({
    name: '',
    type: 'anthropic',
    base_url: providerDefaults.anthropic.url,
    api_key: '',
    model: providerDefaults.anthropic.model,
  });

  if (!open) return null;

  const handleTypeChange = (type: string) => {
    const defaults = providerDefaults[type] || providerDefaults.custom;
    setConfig((prev) => ({ ...prev, type, base_url: defaults.url, model: defaults.model }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onConnect(config);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-reaper-surface border border-reaper-border rounded-lg w-96 animate-fade-in">
        <div className="flex items-center justify-between px-4 py-3 border-b border-reaper-border">
          <div className="flex items-center gap-2">
            <Plug className="w-4 h-4 text-reaper-accent" />
            <span className="text-sm font-mono text-white">Connect Agent</span>
          </div>
          <button onClick={onClose} className="text-reaper-muted hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-3">
          <label className="block">
            <span className="text-xs font-mono text-reaper-muted">Name</span>
            <input
              value={config.name}
              onChange={(e) => setConfig((p) => ({ ...p, name: e.target.value }))}
              className="mt-1 w-full bg-reaper-bg border border-reaper-border rounded px-3 py-1.5 text-sm font-mono text-white focus:border-reaper-accent outline-none"
              placeholder="My Agent"
              required
            />
          </label>

          <label className="block">
            <span className="text-xs font-mono text-reaper-muted">Provider</span>
            <select
              value={config.type}
              onChange={(e) => handleTypeChange(e.target.value)}
              className="mt-1 w-full bg-reaper-bg border border-reaper-border rounded px-3 py-1.5 text-sm font-mono text-white focus:border-reaper-accent outline-none"
            >
              <option value="openclaw">OpenClaw (VPS Gateway)</option>
              <option value="anthropic">Anthropic</option>
              <option value="openai">OpenAI</option>
              <option value="ollama">Ollama</option>
              <option value="custom">Custom</option>
            </select>
          </label>

          <label className="block">
            <span className="text-xs font-mono text-reaper-muted">Base URL</span>
            <input
              value={config.base_url}
              onChange={(e) => setConfig((p) => ({ ...p, base_url: e.target.value }))}
              className="mt-1 w-full bg-reaper-bg border border-reaper-border rounded px-3 py-1.5 text-sm font-mono text-white focus:border-reaper-accent outline-none"
              required
            />
          </label>

          <label className="block">
            <span className="text-xs font-mono text-reaper-muted">API Key</span>
            <input
              type="password"
              value={config.api_key}
              onChange={(e) => setConfig((p) => ({ ...p, api_key: e.target.value }))}
              className="mt-1 w-full bg-reaper-bg border border-reaper-border rounded px-3 py-1.5 text-sm font-mono text-white focus:border-reaper-accent outline-none"
              placeholder="sk-..."
            />
          </label>

          <label className="block">
            <span className="text-xs font-mono text-reaper-muted">Model</span>
            <input
              value={config.model}
              onChange={(e) => setConfig((p) => ({ ...p, model: e.target.value }))}
              className="mt-1 w-full bg-reaper-bg border border-reaper-border rounded px-3 py-1.5 text-sm font-mono text-white focus:border-reaper-accent outline-none"
              required
            />
          </label>

          <button
            type="submit"
            className="w-full mt-2 bg-reaper-accent/10 text-reaper-accent border border-reaper-accent/30 rounded py-2 text-sm font-mono hover:bg-reaper-accent/20 transition-colors"
          >
            Connect
          </button>
        </form>
      </div>
    </div>
  );
}
