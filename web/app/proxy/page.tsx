'use client';

import { useEffect, useMemo, useState } from 'react';
import { Play, Square, RefreshCw, ShieldAlert, ShieldCheck } from 'lucide-react';
import api from '@/lib/api';

interface ProxySession {
  id: string;
  name: string;
  host: string;
  port: number;
  status: string;
  intercept_enabled: boolean;
  tls_intercept_enabled?: boolean;
  body_capture_limit_kb?: number;
  started_at?: string | null;
  updated_at?: string | null;
}

interface ProxyTx {
  id: string;
  source: string;
  method: string;
  host: string;
  path: string;
  url: string;
  response_status: number | null;
  duration_ms: number | null;
  created_at: string | null;
  request_headers?: Record<string, string> | string;
  request_body?: string | null;
  response_headers?: Record<string, string> | string;
  response_body?: string | null;
  intercept_state?: string;
}

interface ProxyHistoryResponse {
  total: number;
  offset: number;
  limit: number;
  transactions: ProxyTx[];
}

export default function ProxyPage() {
  const [sessions, setSessions] = useState<ProxySession[]>([]);
  const [history, setHistory] = useState<ProxyHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [selectedTx, setSelectedTx] = useState<ProxyTx | null>(null);
  const [methodFilter, setMethodFilter] = useState('');
  const [hostFilter, setHostFilter] = useState('');

  const activeSession = useMemo(() => sessions.find((s) => s.id === selectedSessionId) ?? null, [sessions, selectedSessionId]);

  async function loadSessions() {
    const data = await api.get<ProxySession[]>('/api/proxy/sessions');
    setSessions(data);
    if (!selectedSessionId && data[0]) setSelectedSessionId(data[0].id);
  }

  async function loadHistory() {
    const params = new URLSearchParams();
    if (selectedSessionId) params.set('session_id', selectedSessionId);
    if (methodFilter) params.set('method', methodFilter);
    if (hostFilter) params.set('host', hostFilter);
    const q = params.toString();
    const data = await api.get<ProxyHistoryResponse>(`/api/proxy/history${q ? `?${q}` : ''}`);
    setHistory(data);
    setSelectedTx(data.transactions[0] ?? null);
  }

  async function refreshAll() {
    try {
      setLoading(true);
      await loadSessions();
      await loadHistory();
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load proxy data');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void refreshAll(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (!loading) void loadHistory().catch((e) => setError(e instanceof Error ? e.message : 'Failed to load history')); }, [selectedSessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function startSession() {
    try {
      await api.post<ProxySession>('/api/proxy/sessions', {
        name: `Proxy ${sessions.length + 1}`,
        host: '127.0.0.1',
        port: 8080 + sessions.length,
        intercept_enabled: false,
        tls_intercept_enabled: false,
        body_capture_limit_kb: 512,
      });
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start proxy session');
    }
  }

  async function stopSession(sessionId: string) {
    try {
      await api.post(`/api/proxy/sessions/${sessionId}/stop`, {});
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to stop proxy session');
    }
  }

  async function toggleIntercept(sessionId: string, enabled: boolean) {
    try {
      await api.post(`/api/proxy/sessions/${sessionId}/intercept`, { enabled });
      await refreshAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to toggle intercept');
    }
  }

  return (
    <div className="h-full p-4 md:p-6 bg-reaper-bg text-white">
      <div className="flex items-center justify-between mb-4 gap-3">
        <div>
          <h1 className="text-xl font-mono text-reaper-accent">PROXY</h1>
          <p className="text-xs text-reaper-muted font-mono">Session control + HTTP transaction history</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => void refreshAll()} className="px-3 py-2 rounded border border-reaper-border bg-reaper-surface text-xs font-mono inline-flex items-center gap-2">
            <RefreshCw className="w-3 h-3" /> Refresh
          </button>
          <button onClick={() => void startSession()} className="px-3 py-2 rounded border border-reaper-accent/30 bg-reaper-accent/10 text-reaper-accent text-xs font-mono inline-flex items-center gap-2">
            <Play className="w-3 h-3" /> Start Session
          </button>
        </div>
      </div>

      {error && <div className="mb-4 rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs font-mono text-red-300">{error}</div>}

      <div className="grid grid-cols-1 xl:grid-cols-[340px_1fr_420px] gap-4 min-h-[72vh]">
        <div className="rounded-lg border border-reaper-border bg-reaper-surface overflow-hidden">
          <div className="px-3 py-2 border-b border-reaper-border text-xs font-mono text-reaper-muted">Proxy Sessions</div>
          <div className="max-h-[72vh] overflow-auto">
            {loading ? (
              <div className="p-3 text-xs font-mono text-reaper-muted">Loading...</div>
            ) : sessions.length === 0 ? (
              <div className="p-3 text-xs font-mono text-reaper-muted">No sessions started yet.</div>
            ) : sessions.map((s) => (
              <div key={s.id} className={`p-3 border-b border-reaper-border/60 ${selectedSessionId === s.id ? 'bg-reaper-accent/5' : ''}`}>
                <button onClick={() => setSelectedSessionId(s.id)} className="w-full text-left">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-xs font-mono text-white truncate">{s.name || `${s.host}:${s.port}`}</div>
                    <span className={`text-[10px] font-mono ${s.status === 'running' ? 'text-reaper-success' : 'text-reaper-muted'}`}>{s.status}</span>
                  </div>
                  <div className="mt-1 text-[10px] font-mono text-reaper-muted truncate">{s.host}:{s.port} • intercept {s.intercept_enabled ? 'on' : 'off'}</div>
                </button>
                <div className="mt-2 flex gap-2">
                  <button onClick={() => void toggleIntercept(s.id, !s.intercept_enabled)} className={`px-2 py-1 rounded border text-[10px] font-mono inline-flex items-center gap-1 ${s.intercept_enabled ? 'border-amber-400/40 text-amber-300 bg-amber-400/10' : 'border-reaper-border text-reaper-muted bg-black/20'}`}>
                    {s.intercept_enabled ? <ShieldAlert className="w-3 h-3" /> : <ShieldCheck className="w-3 h-3" />} {s.intercept_enabled ? 'Disable Intercept' : 'Enable Intercept'}
                  </button>
                  <button onClick={() => void stopSession(s.id)} disabled={s.status !== 'running'} className="px-2 py-1 rounded border border-red-500/30 text-red-300 bg-red-500/10 text-[10px] font-mono inline-flex items-center gap-1 disabled:opacity-40">
                    <Square className="w-3 h-3" /> Stop
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-reaper-border bg-reaper-surface p-4 flex flex-col">
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <input value={hostFilter} onChange={(e) => setHostFilter(e.target.value)} placeholder="Filter host" className="px-3 py-2 rounded bg-black/20 border border-reaper-border text-xs font-mono" />
            <select value={methodFilter} onChange={(e) => setMethodFilter(e.target.value)} className="px-3 py-2 rounded bg-black/20 border border-reaper-border text-xs font-mono">
              <option value="">All methods</option>
              {['GET','POST','PUT','PATCH','DELETE','OPTIONS','HEAD'].map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
            <button onClick={() => void loadHistory()} className="px-3 py-2 rounded border border-reaper-border bg-black/20 text-xs font-mono">Apply</button>
          </div>
          <div className="text-xs font-mono text-reaper-muted mb-2">History {history ? `(${history.total})` : ''}</div>
          <div className="overflow-auto border border-reaper-border rounded flex-1">
            <table className="w-full text-xs font-mono">
              <thead className="bg-black/20 text-reaper-muted sticky top-0">
                <tr>
                  <th className="px-2 py-2 text-left">Method</th>
                  <th className="px-2 py-2 text-left">Host/Path</th>
                  <th className="px-2 py-2 text-left">Status</th>
                  <th className="px-2 py-2 text-left">ms</th>
                </tr>
              </thead>
              <tbody>
                {(history?.transactions || []).map((tx) => (
                  <tr key={tx.id} onClick={() => setSelectedTx(tx)} className={`border-t border-reaper-border/50 cursor-pointer hover:bg-white/5 ${selectedTx?.id === tx.id ? 'bg-reaper-accent/10' : ''}`}>
                    <td className="px-2 py-2">{tx.method}</td>
                    <td className="px-2 py-2">
                      <div className="truncate max-w-[28rem]">{tx.host}{tx.path}</div>
                      <div className="text-[10px] text-reaper-muted truncate">{tx.intercept_state || tx.source}</div>
                    </td>
                    <td className="px-2 py-2">{tx.response_status ?? '—'}</td>
                    <td className="px-2 py-2">{tx.duration_ms ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-lg border border-reaper-border bg-reaper-surface p-4 flex flex-col gap-3">
          <div className="text-sm font-mono text-reaper-accent">Transaction Inspector</div>
          {!selectedTx ? (
            <div className="text-xs font-mono text-reaper-muted">Select a transaction to inspect raw request/response.</div>
          ) : (
            <>
              <div className="rounded border border-reaper-border bg-black/20 p-3 text-xs font-mono">
                <div className="text-reaper-muted mb-1">Request</div>
                <div className="text-white break-all">{selectedTx.method} {selectedTx.url}</div>
                <pre className="mt-2 whitespace-pre-wrap break-words text-[11px] text-reaper-muted max-h-32 overflow-auto">{typeof selectedTx.request_headers === 'string' ? selectedTx.request_headers : JSON.stringify(selectedTx.request_headers || {}, null, 2)}</pre>
                {selectedTx.request_body && <pre className="mt-2 whitespace-pre-wrap break-words text-[11px] text-emerald-100 max-h-32 overflow-auto">{selectedTx.request_body.slice(0, 3000)}</pre>}
              </div>
              <div className="rounded border border-reaper-border bg-black/20 p-3 text-xs font-mono flex-1">
                <div className="text-reaper-muted mb-1">Response</div>
                <div className="text-white">Status {selectedTx.response_status ?? '—'} • {selectedTx.duration_ms ?? '—'}ms</div>
                <pre className="mt-2 whitespace-pre-wrap break-words text-[11px] text-reaper-muted max-h-32 overflow-auto">{typeof selectedTx.response_headers === 'string' ? selectedTx.response_headers : JSON.stringify(selectedTx.response_headers || {}, null, 2)}</pre>
                {selectedTx.response_body && <pre className="mt-2 whitespace-pre-wrap break-words text-[11px] text-emerald-100 max-h-52 overflow-auto">{selectedTx.response_body.slice(0, 5000)}</pre>}
              </div>
            </>
          )}
          {activeSession && (
            <div className="text-[10px] font-mono text-reaper-muted">Active filter session: {activeSession.name} ({activeSession.host}:{activeSession.port})</div>
          )}
        </div>
      </div>
    </div>
  );
}
