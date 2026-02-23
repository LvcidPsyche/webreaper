'use client';

import { useState, useCallback } from 'react';
import { Settings, Plus, Trash2, RefreshCw, Eye, EyeOff, CheckCircle, XCircle, Loader2, Key, ShieldCheck, AlertTriangle } from 'lucide-react';
import { clsx } from 'clsx';
import { AnimateIn } from '@/components/shared/animate-in';
import { SkeletonCard } from '@/components/shared/skeleton';
import { useApi } from '@/hooks/use-api';
import api from '@/lib/api';
import type { AgentProvider, LicenseStatus } from '@/lib/types';

interface ProviderForm { name: string; type: string; base_url: string; api_key: string; model: string }
const emptyForm: ProviderForm = { name: '', type: 'anthropic', base_url: '', api_key: '', model: '' };
const inputCls = 'mt-1 w-full bg-reaper-bg border border-reaper-border rounded px-3 py-1.5 text-sm font-mono text-white focus:border-reaper-accent outline-none';

function LicensePanel() {
  const { data: license, loading, refetch } = useApi<LicenseStatus>('/api/license');
  const [keyInput, setKeyInput] = useState('');
  const [activating, setActivating] = useState(false);
  const [activateError, setActivateError] = useState<string | null>(null);
  const [activateSuccess, setActivateSuccess] = useState(false);

  const handleActivate = useCallback(async () => {
    if (!keyInput.trim()) return;
    setActivating(true);
    setActivateError(null);
    setActivateSuccess(false);
    try {
      await api.post('/api/license/activate', { key: keyInput.trim() });
      setActivateSuccess(true);
      setKeyInput('');
      refetch();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Activation failed';
      setActivateError(msg.replace('API 400: ', ''));
    } finally {
      setActivating(false);
    }
  }, [keyInput, refetch]);

  const handleDeactivate = useCallback(async () => {
    await api.delete('/api/license');
    refetch();
  }, [refetch]);

  const tierColor = (tier: string) => {
    if (tier === 'PRO') return 'text-reaper-accent border-reaper-accent/40 bg-reaper-accent/10';
    if (tier === 'LITE') return 'text-yellow-400 border-yellow-400/40 bg-yellow-400/10';
    return 'text-reaper-muted border-reaper-border bg-reaper-surface';
  };

  if (loading) return <SkeletonCard />;

  const pctUsed = license?.pct_used ?? 0;
  const barColor = pctUsed > 80 ? 'bg-reaper-danger' : pctUsed > 50 ? 'bg-yellow-400' : 'bg-reaper-success';

  return (
    <AnimateIn>
      <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-mono text-white flex items-center gap-2">
            <Key className="w-4 h-4 text-reaper-accent" /> License
          </h2>
          {license?.installed && (
            <span className={clsx('text-xs font-mono px-2 py-0.5 rounded border', tierColor(license.tier))}>
              {license.tier}
            </span>
          )}
        </div>

        {license?.installed ? (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3 text-xs font-mono">
              <div>
                <div className="text-reaper-muted mb-0.5">Key</div>
                <div className="text-white">{license.key_preview}</div>
              </div>
              <div>
                <div className="text-reaper-muted mb-0.5">Activated</div>
                <div className="text-white">{license.installed_at?.slice(0, 10) ?? '—'}</div>
              </div>
              <div>
                <div className="text-reaper-muted mb-0.5">Plan</div>
                <div className="text-white">{license.tier_description}</div>
              </div>
              <div>
                <div className="text-reaper-muted mb-0.5">Month</div>
                <div className="text-white">{license.month}</div>
              </div>
            </div>

            {license.pages_limit !== null && (
              <div className="space-y-1">
                <div className="flex justify-between text-xs font-mono text-reaper-muted">
                  <span>Pages this month</span>
                  <span>{license.pages_used} / {license.pages_limit}</span>
                </div>
                <div className="h-1.5 bg-reaper-bg rounded-full overflow-hidden">
                  <div
                    className={clsx('h-full rounded-full transition-all', barColor)}
                    style={{ width: `${Math.min(pctUsed, 100)}%` }}
                  />
                </div>
                <div className="text-xs font-mono text-reaper-muted text-right">
                  {license.pages_remaining} remaining
                </div>
              </div>
            )}

            {license.pages_limit === null && (
              <div className="flex items-center gap-2 text-xs font-mono text-reaper-success">
                <ShieldCheck className="w-3.5 h-3.5" /> Unlimited pages
              </div>
            )}

            <button
              onClick={handleDeactivate}
              className="text-xs font-mono text-reaper-muted hover:text-reaper-danger transition-colors"
            >
              Remove license
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-start gap-2 text-xs font-mono text-yellow-400/80 bg-yellow-400/5 border border-yellow-400/20 rounded p-2.5">
              <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <span>No license installed. The API is running but crawl jobs are blocked until you activate a license.</span>
            </div>

            <div className="space-y-2">
              <div className="text-xs font-mono text-reaper-muted">Enter your license key</div>
              <div className="flex gap-2">
                <input
                  value={keyInput}
                  onChange={(e) => setKeyInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleActivate()}
                  placeholder="WR-LITE-XXXXXXXX-YYYYYYYY"
                  className="flex-1 bg-reaper-bg border border-reaper-border rounded px-3 py-1.5 text-sm font-mono text-white focus:border-reaper-accent outline-none"
                />
                <button
                  onClick={handleActivate}
                  disabled={activating || !keyInput.trim()}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-reaper-accent/10 text-reaper-accent border border-reaper-accent/30 rounded text-xs font-mono hover:bg-reaper-accent/20 transition-colors disabled:opacity-50"
                >
                  {activating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Key className="w-3.5 h-3.5" />}
                  Activate
                </button>
              </div>
              {activateError && (
                <div className="flex items-center gap-1.5 text-xs font-mono text-reaper-danger">
                  <XCircle className="w-3.5 h-3.5" /> {activateError}
                </div>
              )}
              {activateSuccess && (
                <div className="flex items-center gap-1.5 text-xs font-mono text-reaper-success">
                  <CheckCircle className="w-3.5 h-3.5" /> License activated successfully!
                </div>
              )}
            </div>

            <div className="border-t border-reaper-border pt-3 space-y-2">
              <div className="text-xs font-mono text-reaper-muted">Available plans:</div>
              <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                <div className="border border-yellow-400/20 rounded p-2.5 space-y-1">
                  <div className="text-yellow-400 font-bold">LITE</div>
                  <div className="text-white">$19.99 / month</div>
                  <div className="text-reaper-muted">500 pages/month</div>
                </div>
                <div className="border border-reaper-accent/20 rounded p-2.5 space-y-1">
                  <div className="text-reaper-accent font-bold">PRO</div>
                  <div className="text-white">$119.99 one-time</div>
                  <div className="text-reaper-muted">Unlimited forever</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </AnimateIn>
  );
}

export default function SettingsPage() {
  const { data: providers, loading, refetch } = useApi<AgentProvider[]>('/api/agents');
  const [editing, setEditing] = useState<ProviderForm | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<Record<string, boolean>>({});

  const handleSave = useCallback(async () => {
    if (!editing) return;
    if (editingId) await api.put(`/api/agents/${editingId}`, editing);
    else await api.post('/api/agents', editing);
    setEditing(null); setEditingId(null); refetch();
  }, [editing, editingId, refetch]);

  const handleDelete = useCallback(async (id: string) => { await api.delete(`/api/agents/${id}`); refetch(); }, [refetch]);

  const handleTest = useCallback(async (id: string) => {
    setTesting(id);
    try { const r = await api.post<{ ok: boolean }>(`/api/agents/${id}/test`); setTestResult((p) => ({ ...p, [id]: r.ok })); }
    catch { setTestResult((p) => ({ ...p, [id]: false })); }
    setTesting(null);
  }, []);

  const startEdit = (p: AgentProvider) => {
    setEditingId(p.id);
    setEditing({ name: p.name, type: p.type, base_url: p.base_url, api_key: '', model: p.model });
  };

  return (
    <div className="space-y-4 max-w-3xl">
      <LicensePanel />

      <AnimateIn>
        <div className="flex items-center justify-between">
          <h1 className="text-sm font-mono text-white flex items-center gap-2">
            <Settings className="w-4 h-4 text-reaper-accent" /> Agent Providers
          </h1>
          <button onClick={() => { setEditing({ ...emptyForm }); setEditingId(null); }} className="flex items-center gap-1.5 px-3 py-1.5 bg-reaper-accent/10 text-reaper-accent border border-reaper-accent/30 rounded text-xs font-mono hover:bg-reaper-accent/20 transition-colors">
            <Plus className="w-3 h-3" /> Add Provider
          </button>
        </div>
      </AnimateIn>

      {editing && (
        <AnimateIn>
          <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4 space-y-3">
            <h3 className="text-xs font-mono text-white">{editingId ? 'Edit Provider' : 'New Provider'}</h3>
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="text-xs font-mono text-reaper-muted">Name</span>
                <input value={editing.name} onChange={(e) => setEditing((p) => p && ({ ...p, name: e.target.value }))} className={inputCls} />
              </label>
              <label className="block">
                <span className="text-xs font-mono text-reaper-muted">Type</span>
                <select value={editing.type} onChange={(e) => setEditing((p) => p && ({ ...p, type: e.target.value }))} className={inputCls}>
                  <option value="openclaw">OpenClaw (VPS Gateway)</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="openai">OpenAI</option>
                  <option value="ollama">Ollama</option>
                  <option value="custom">Custom</option>
                </select>
              </label>
              <label className="block">
                <span className="text-xs font-mono text-reaper-muted">Base URL</span>
                <input value={editing.base_url} onChange={(e) => setEditing((p) => p && ({ ...p, base_url: e.target.value }))} className={inputCls} />
              </label>
              <label className="block">
                <span className="text-xs font-mono text-reaper-muted">Model</span>
                <input value={editing.model} onChange={(e) => setEditing((p) => p && ({ ...p, model: e.target.value }))} className={inputCls} />
              </label>
            </div>
            <label className="block relative">
              <span className="text-xs font-mono text-reaper-muted">API Key</span>
              <div className="relative mt-1">
                <input type={showKey ? 'text' : 'password'} value={editing.api_key} onChange={(e) => setEditing((p) => p && ({ ...p, api_key: e.target.value }))} placeholder={editingId ? '(unchanged)' : 'sk-...'} className={inputCls + ' pr-8'} />
                <button type="button" onClick={() => setShowKey(!showKey)} className="absolute right-2 top-1/2 -translate-y-1/2 text-reaper-muted hover:text-white">
                  {showKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>
            </label>
            <div className="flex gap-2 pt-1">
              <button onClick={handleSave} className="px-3 py-1.5 bg-reaper-accent/10 text-reaper-accent border border-reaper-accent/30 rounded text-xs font-mono hover:bg-reaper-accent/20 transition-colors">Save</button>
              <button onClick={() => { setEditing(null); setEditingId(null); }} className="px-3 py-1.5 text-reaper-muted text-xs font-mono hover:text-white transition-colors">Cancel</button>
            </div>
          </div>
        </AnimateIn>
      )}

      {loading ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}</div>
      ) : (
        <div className="space-y-2">
          {(providers || []).map((p, i) => (
            <AnimateIn key={p.id} delay={i * 0.03}>
              <div className="bg-reaper-surface border border-reaper-border rounded-lg p-3 flex items-center gap-3">
                <div className={clsx('w-2 h-2 rounded-full', p.status === 'connected' ? 'bg-reaper-success' : p.status === 'error' ? 'bg-reaper-danger' : 'bg-reaper-muted')} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-mono text-white">{p.name}</div>
                  <div className="text-xs font-mono text-reaper-muted">{p.type} - {p.model}</div>
                </div>
                <div className="flex items-center gap-2">
                  {testResult[p.id] !== undefined && (testResult[p.id] ? <CheckCircle className="w-3.5 h-3.5 text-reaper-success" /> : <XCircle className="w-3.5 h-3.5 text-reaper-danger" />)}
                  <button onClick={() => handleTest(p.id)} disabled={testing === p.id} className="p-1.5 text-reaper-muted hover:text-reaper-accent transition-colors">
                    {testing === p.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                  </button>
                  <button onClick={() => startEdit(p)} className="p-1.5 text-reaper-muted hover:text-white transition-colors"><Settings className="w-3.5 h-3.5" /></button>
                  <button onClick={() => handleDelete(p.id)} className="p-1.5 text-reaper-muted hover:text-reaper-danger transition-colors"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              </div>
            </AnimateIn>
          ))}
          {(!providers || providers.length === 0) && !editing && (
            <div className="text-center py-8 text-reaper-muted font-mono text-sm">No providers configured</div>
          )}
        </div>
      )}
    </div>
  );
}
