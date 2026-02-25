'use client';

import { useEffect, useMemo, useState } from 'react';
import { RefreshCw, Play, Save, Plus, Wand2 } from 'lucide-react';
import api from '@/lib/api';

interface RepeaterTab {
  id: string;
  workspace_id: string | null;
  source_transaction_id: string | null;
  name: string;
  method: string;
  url: string;
  headers: Record<string, string> | string | null;
  body: string | null;
  created_at: string | null;
  updated_at: string | null;
  last_run_at: string | null;
}

interface HttpTx {
  id: string;
  method: string;
  url: string;
  response_status: number | null;
  duration_ms: number | null;
  request_headers?: Record<string, string>;
  request_body?: string | null;
  response_headers?: Record<string, string>;
  response_body?: string | null;
}

interface RepeaterRun {
  id: string;
  status: string;
  response_status: number | null;
  duration_ms: number | null;
  error?: string | null;
  diff_summary?: Record<string, any> | null;
  created_at: string | null;
  transaction?: HttpTx;
}

const decoderOps = [
  'url_encode', 'url_decode', 'base64_encode', 'base64_decode',
  'html_encode', 'html_decode', 'hex_encode', 'hex_decode', 'jwt_parse',
] as const;

function headersToText(headers: RepeaterTab['headers']) {
  if (!headers) return '';
  if (typeof headers === 'string') return headers;
  return Object.entries(headers).map(([k, v]) => `${k}: ${v}`).join('\n');
}

function headersFromText(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const idx = trimmed.indexOf(':');
    if (idx <= 0) continue;
    out[trimmed.slice(0, idx).trim()] = trimmed.slice(idx + 1).trim();
  }
  return out;
}

export default function RepeaterPage() {
  const [tabs, setTabs] = useState<RepeaterTab[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runs, setRuns] = useState<RepeaterRun[]>([]);

  const [name, setName] = useState('');
  const [method, setMethod] = useState('GET');
  const [url, setUrl] = useState('');
  const [headersText, setHeadersText] = useState('');
  const [body, setBody] = useState('');
  const [followRedirects, setFollowRedirects] = useState(true);
  const [timeoutMs, setTimeoutMs] = useState(15000);

  const [decoderInput, setDecoderInput] = useState('');
  const [decoderOp, setDecoderOp] = useState<typeof decoderOps[number]>('base64_decode');
  const [decoderOutput, setDecoderOutput] = useState('');
  const [decoderError, setDecoderError] = useState<string | null>(null);

  const selectedTab = useMemo(() => tabs.find((t) => t.id === selectedId) ?? null, [tabs, selectedId]);

  async function loadTabs(selectLatest = false) {
    try {
      setLoading(true);
      const data = await api.get<RepeaterTab[]>('/api/repeater/tabs');
      setTabs(data);
      const nextId = selectLatest ? data[0]?.id : (selectedId && data.some((t) => t.id === selectedId) ? selectedId : data[0]?.id);
      setSelectedId(nextId ?? null);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load repeater tabs');
    } finally {
      setLoading(false);
    }
  }

  async function loadRuns(tabId: string) {
    try {
      const data = await api.get<RepeaterRun[]>(`/api/repeater/tabs/${tabId}/runs`);
      setRuns(data);
    } catch (e) {
      setRuns([]);
      setError(e instanceof Error ? e.message : 'Failed to load runs');
    }
  }

  useEffect(() => { void loadTabs(); }, []);
  useEffect(() => {
    if (!selectedTab) {
      setRuns([]);
      setName(''); setMethod('GET'); setUrl(''); setHeadersText(''); setBody('');
      return;
    }
    setName(selectedTab.name || '');
    setMethod((selectedTab.method || 'GET').toUpperCase());
    setUrl(selectedTab.url || '');
    setHeadersText(headersToText(selectedTab.headers));
    setBody(selectedTab.body || '');
    void loadRuns(selectedTab.id);
  }, [selectedTab?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function createTab() {
    try {
      setSaving(true);
      const tab = await api.post<RepeaterTab>('/api/repeater/tabs', {
        name: 'New Repeater Tab', method: 'GET', url: 'https://example.com', headers: {}, body: null,
      });
      await loadTabs(true);
      setSelectedId(tab.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create tab');
    } finally {
      setSaving(false);
    }
  }

  async function saveTab() {
    if (!selectedId) return;
    try {
      setSaving(true);
      const updated = await api.put<RepeaterTab>(`/api/repeater/tabs/${selectedId}`, {
        name,
        method,
        url,
        headers: headersFromText(headersText),
        body: body || null,
      });
      setTabs((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save tab');
    } finally {
      setSaving(false);
    }
  }

  async function sendTab() {
    if (!selectedId) return;
    try {
      setSending(true);
      const result = await api.post<{ tab: RepeaterTab; run: RepeaterRun }>(`/api/repeater/tabs/${selectedId}/send`, {
        timeout_ms: timeoutMs,
        follow_redirects: followRedirects,
      });
      setTabs((prev) => prev.map((t) => (t.id === result.tab.id ? result.tab : t)));
      await loadRuns(selectedId);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to send request');
    } finally {
      setSending(false);
    }
  }

  async function runDecoder() {
    try {
      setDecoderError(null);
      const res = await api.post<{ ok: boolean; output?: unknown; error?: string }>('/api/repeater/decode', {
        operation: decoderOp,
        input: decoderInput,
      });
      if (!res.ok) {
        setDecoderOutput('');
        setDecoderError(res.error || 'Decoder failed');
        return;
      }
      const out = typeof res.output === 'string' ? res.output : JSON.stringify(res.output, null, 2);
      setDecoderOutput(out);
    } catch (e) {
      setDecoderError(e instanceof Error ? e.message : 'Decoder failed');
    }
  }

  const latestRun = runs[0];

  return (
    <div className="h-full p-4 md:p-6 bg-reaper-bg text-white">
      <div className="flex items-center justify-between mb-4 gap-3">
        <div>
          <h1 className="text-xl font-mono text-reaper-accent">REPEATER</h1>
          <p className="text-xs text-reaper-muted font-mono">Manual request replay + decoder utilities</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => void loadTabs()} className="px-3 py-2 rounded border border-reaper-border bg-reaper-surface text-xs font-mono inline-flex items-center gap-2">
            <RefreshCw className="w-3 h-3" /> Refresh
          </button>
          <button disabled={saving} onClick={() => void createTab()} className="px-3 py-2 rounded border border-reaper-accent/30 bg-reaper-accent/10 text-xs font-mono inline-flex items-center gap-2 text-reaper-accent disabled:opacity-50">
            <Plus className="w-3 h-3" /> New Tab
          </button>
        </div>
      </div>

      {error && <div className="mb-4 rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs font-mono text-red-300">{error}</div>}

      <div className="grid grid-cols-1 xl:grid-cols-[260px_1fr_380px] gap-4 min-h-[70vh]">
        <div className="rounded-lg border border-reaper-border bg-reaper-surface overflow-hidden">
          <div className="px-3 py-2 border-b border-reaper-border text-xs font-mono text-reaper-muted">Tabs</div>
          <div className="max-h-[70vh] overflow-auto">
            {loading ? (
              <div className="p-3 text-xs font-mono text-reaper-muted">Loading...</div>
            ) : tabs.length === 0 ? (
              <div className="p-3 text-xs font-mono text-reaper-muted">No tabs yet.</div>
            ) : (
              tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setSelectedId(tab.id)}
                  className={`w-full text-left px-3 py-2 border-b border-reaper-border/60 hover:bg-white/5 ${selectedId === tab.id ? 'bg-reaper-accent/10' : ''}`}
                >
                  <div className="text-xs font-mono text-white truncate">{tab.name || `${tab.method} ${tab.url}`}</div>
                  <div className="mt-1 text-[10px] font-mono text-reaper-muted truncate">{tab.method} {tab.url}</div>
                </button>
              ))
            )}
          </div>
        </div>

        <div className="rounded-lg border border-reaper-border bg-reaper-surface p-4 flex flex-col gap-3">
          <div className="grid grid-cols-1 md:grid-cols-[1fr_120px] gap-3">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Tab name" className="px-3 py-2 rounded bg-black/20 border border-reaper-border text-sm font-mono" />
            <select value={method} onChange={(e) => setMethod(e.target.value.toUpperCase())} className="px-3 py-2 rounded bg-black/20 border border-reaper-border text-sm font-mono">
              {['GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS'].map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://target.tld/path" className="px-3 py-2 rounded bg-black/20 border border-reaper-border text-sm font-mono" />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 flex-1">
            <div className="flex flex-col min-h-[240px]">
              <div className="text-xs font-mono text-reaper-muted mb-1">Headers</div>
              <textarea value={headersText} onChange={(e) => setHeadersText(e.target.value)} className="flex-1 min-h-[220px] px-3 py-2 rounded bg-black/20 border border-reaper-border text-xs font-mono" placeholder={'Content-Type: application/json\nAuthorization: Bearer ...'} />
            </div>
            <div className="flex flex-col min-h-[240px]">
              <div className="text-xs font-mono text-reaper-muted mb-1">Body</div>
              <textarea value={body} onChange={(e) => setBody(e.target.value)} className="flex-1 min-h-[220px] px-3 py-2 rounded bg-black/20 border border-reaper-border text-xs font-mono" placeholder="Request body" />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs font-mono">
            <label className="inline-flex items-center gap-2 text-reaper-muted">
              <input type="checkbox" checked={followRedirects} onChange={(e) => setFollowRedirects(e.target.checked)} /> Follow redirects
            </label>
            <label className="inline-flex items-center gap-2 text-reaper-muted">
              Timeout ms
              <input type="number" min={100} max={120000} value={timeoutMs} onChange={(e) => setTimeoutMs(Number(e.target.value) || 15000)} className="w-28 px-2 py-1 rounded bg-black/20 border border-reaper-border" />
            </label>
            <div className="ml-auto flex gap-2">
              <button disabled={!selectedId || saving} onClick={() => void saveTab()} className="px-3 py-2 rounded border border-reaper-border bg-black/20 inline-flex items-center gap-2 disabled:opacity-50">
                <Save className="w-3 h-3" /> Save
              </button>
              <button disabled={!selectedId || sending} onClick={() => void sendTab()} className="px-3 py-2 rounded border border-reaper-accent/30 bg-reaper-accent/10 text-reaper-accent inline-flex items-center gap-2 disabled:opacity-50">
                <Play className="w-3 h-3" /> Send
              </button>
            </div>
          </div>

          {latestRun && (
            <div className="rounded border border-reaper-border bg-black/20 p-3 text-xs font-mono">
              <div className="flex items-center justify-between mb-2">
                <span className={`${latestRun.status === 'success' ? 'text-reaper-success' : 'text-red-300'}`}>Latest run: {latestRun.status}</span>
                <span className="text-reaper-muted">{latestRun.response_status ?? '—'} • {latestRun.duration_ms ?? '—'}ms</span>
              </div>
              {latestRun.error && <div className="text-red-300 mb-2">{latestRun.error}</div>}
              <pre className="whitespace-pre-wrap break-words text-[11px] text-reaper-muted">{JSON.stringify(latestRun.diff_summary || {}, null, 2)}</pre>
              {latestRun.transaction?.response_body && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-white">Response body preview</summary>
                  <pre className="mt-2 whitespace-pre-wrap break-words text-[11px] text-emerald-100 max-h-40 overflow-auto">{latestRun.transaction.response_body.slice(0, 4000)}</pre>
                </details>
              )}
            </div>
          )}
        </div>

        <div className="flex flex-col gap-4">
          <div className="rounded-lg border border-reaper-border bg-reaper-surface p-4">
            <div className="flex items-center gap-2 mb-2 text-sm font-mono text-reaper-accent"><Wand2 className="w-4 h-4" /> Decoder</div>
            <div className="space-y-2">
              <select value={decoderOp} onChange={(e) => setDecoderOp(e.target.value as typeof decoderOps[number])} className="w-full px-3 py-2 rounded bg-black/20 border border-reaper-border text-xs font-mono">
                {decoderOps.map((op) => <option key={op} value={op}>{op}</option>)}
              </select>
              <textarea value={decoderInput} onChange={(e) => setDecoderInput(e.target.value)} className="w-full min-h-[140px] px-3 py-2 rounded bg-black/20 border border-reaper-border text-xs font-mono" placeholder="Paste encoded/decoded value" />
              <button onClick={() => void runDecoder()} className="px-3 py-2 rounded border border-reaper-accent/30 bg-reaper-accent/10 text-reaper-accent text-xs font-mono">Transform</button>
              {decoderError && <div className="text-xs font-mono text-red-300">{decoderError}</div>}
              <textarea readOnly value={decoderOutput} className="w-full min-h-[140px] px-3 py-2 rounded bg-black/20 border border-reaper-border text-xs font-mono text-emerald-100" placeholder="Output" />
            </div>
          </div>

          <div className="rounded-lg border border-reaper-border bg-reaper-surface p-4 flex-1 min-h-[240px]">
            <div className="text-sm font-mono text-reaper-accent mb-2">Run History</div>
            <div className="space-y-2 max-h-[42vh] overflow-auto pr-1">
              {runs.length === 0 ? (
                <div className="text-xs font-mono text-reaper-muted">No runs yet.</div>
              ) : runs.map((run) => (
                <div key={run.id} className="rounded border border-reaper-border bg-black/20 p-2">
                  <div className="flex justify-between gap-2 text-xs font-mono">
                    <span className={run.status === 'success' ? 'text-reaper-success' : 'text-red-300'}>{run.status}</span>
                    <span className="text-reaper-muted">{run.response_status ?? '—'} • {run.duration_ms ?? '—'}ms</span>
                  </div>
                  <div className="mt-1 text-[10px] font-mono text-reaper-muted break-all">{run.transaction?.url || run.created_at}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
