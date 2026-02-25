'use client';

import { useEffect, useMemo, useState } from 'react';
import { Crosshair, Play, Square, Plus, RefreshCw } from 'lucide-react';
import api from '@/lib/api';

interface IntruderJob {
  id: string;
  name: string;
  method: string;
  url: string;
  body?: string | null;
  payloads: string[] | string;
  status: string;
  total_attempts: number;
  completed_attempts: number;
  matched_attempts: number;
  match_substring?: string | null;
  rate_limit_rps?: number | null;
  timeout_ms?: number;
  stop_on_first_match?: boolean;
}

interface IntruderResult {
  id: string;
  attempt_index: number;
  payload: string;
  request_url: string;
  response_status: number | null;
  duration_ms: number | null;
  matched: boolean | number;
  match_reason?: string | null;
  error?: string | null;
  transaction?: { response_body?: string | null; url?: string };
}

interface IntruderResultResponse {
  total: number;
  results: IntruderResult[];
}

function payloadsToText(v: IntruderJob['payloads']) {
  if (Array.isArray(v)) return v.join('\n');
  if (!v) return '';
  try {
    const parsed = JSON.parse(v);
    return Array.isArray(parsed) ? parsed.join('\n') : String(v);
  } catch {
    return String(v);
  }
}

export default function IntruderPage() {
  const [jobs, setJobs] = useState<IntruderJob[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [results, setResults] = useState<IntruderResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const [name, setName] = useState('Fuzz endpoint');
  const [method, setMethod] = useState('GET');
  const [url, setUrl] = useState('https://example.com/search?q=§FUZZ§');
  const [body, setBody] = useState('');
  const [payloadsText, setPayloadsText] = useState('admin\nguest\ntest');
  const [matchSubstring, setMatchSubstring] = useState('admin');
  const [rateLimitRps, setRateLimitRps] = useState('5');
  const [timeoutMs, setTimeoutMs] = useState('10000');
  const [stopOnFirstMatch, setStopOnFirstMatch] = useState(true);
  const [waitForCompletion, setWaitForCompletion] = useState(false);

  useEffect(() => {
    api.get<Record<string, unknown>>('/api/governance/ui-preferences?page=intruder').then((prefs) => {
      const saved = prefs['intruder.builder'];
      if (saved && typeof saved === 'object') {
        const v = saved as Record<string, unknown>;
        if (typeof v.method === 'string') setMethod(v.method);
        if (typeof v.url === 'string') setUrl(v.url);
        if (typeof v.payloadsText === 'string') setPayloadsText(v.payloadsText);
        if (typeof v.matchSubstring === 'string') setMatchSubstring(v.matchSubstring);
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    api.put('/api/governance/ui-preferences', {
      page: 'intruder',
      key: 'intruder.builder',
      value: { method, url, payloadsText, matchSubstring },
    }).catch(() => {});
  }, [method, url, payloadsText, matchSubstring]);

  const selectedJob = useMemo(() => jobs.find((j) => j.id === selectedJobId) ?? null, [jobs, selectedJobId]);

  async function loadJobs(preserveSelection = true) {
    const data = await api.get<IntruderJob[]>('/api/intruder/jobs');
    setJobs(data);
    if (!preserveSelection) {
      setSelectedJobId(data[0]?.id ?? null);
      return;
    }
    if (!selectedJobId || !data.some((j) => j.id === selectedJobId)) {
      setSelectedJobId(data[0]?.id ?? null);
    }
  }

  async function loadResults(jobId: string) {
    const data = await api.get<IntruderResultResponse>(`/api/intruder/jobs/${jobId}/results`);
    setResults(data.results || []);
  }

  async function refreshAll() {
    try {
      setLoading(true);
      await loadJobs();
      if (selectedJobId) await loadResults(selectedJobId);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load intruder state');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void refreshAll(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (selectedJob) {
      setName(selectedJob.name || '');
      setMethod((selectedJob.method || 'GET').toUpperCase());
      setUrl(selectedJob.url || '');
      setBody(selectedJob.body || '');
      setPayloadsText(payloadsToText(selectedJob.payloads));
      setMatchSubstring(selectedJob.match_substring || '');
      setRateLimitRps(selectedJob.rate_limit_rps ? String(selectedJob.rate_limit_rps) : '');
      setTimeoutMs(String(selectedJob.timeout_ms || 10000));
      setStopOnFirstMatch(Boolean(selectedJob.stop_on_first_match));
      void loadResults(selectedJob.id).catch((e) => setError(e instanceof Error ? e.message : 'Failed to load results'));
    } else {
      setResults([]);
    }
  }, [selectedJob?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function createJob() {
    try {
      setBusy('create');
      const payloads = payloadsText.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
      const job = await api.post<IntruderJob>('/api/intruder/jobs', {
        name,
        method,
        url,
        body: body || null,
        payloads,
        match_substring: matchSubstring || null,
        rate_limit_rps: rateLimitRps ? Number(rateLimitRps) : null,
        timeout_ms: Number(timeoutMs) || 10000,
        stop_on_first_match: stopOnFirstMatch,
      });
      await loadJobs(false);
      setSelectedJobId(job.id);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create Intruder job');
    } finally {
      setBusy(null);
    }
  }

  async function runJob(wait = waitForCompletion) {
    if (!selectedJobId) return;
    try {
      setBusy('run');
      await api.post(`/api/intruder/jobs/${selectedJobId}/start`, { wait });
      await loadJobs();
      await loadResults(selectedJobId);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start Intruder job');
    } finally {
      setBusy(null);
    }
  }

  async function cancelJob() {
    if (!selectedJobId) return;
    try {
      setBusy('cancel');
      await api.post(`/api/intruder/jobs/${selectedJobId}/cancel`, {});
      await loadJobs();
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to cancel Intruder job');
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="h-full p-4 md:p-6 bg-reaper-bg text-white">
      <div className="flex items-center justify-between gap-3 mb-4">
        <div>
          <h1 className="text-xl font-mono text-purple-300 inline-flex items-center gap-2"><Crosshair className="w-5 h-5" /> INTRUDER</h1>
          <p className="text-xs font-mono text-reaper-muted">Queued payload fuzzing (MVP) with result triage</p>
        </div>
        <button onClick={() => void refreshAll()} className="px-3 py-2 rounded border border-reaper-border bg-reaper-surface text-xs font-mono inline-flex items-center gap-2"><RefreshCw className="w-3 h-3" /> Refresh</button>
      </div>

      {error && <div className="mb-4 rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs font-mono text-red-300">{error}</div>}

      <div className="grid grid-cols-1 xl:grid-cols-[320px_1fr_430px] gap-4 min-h-[72vh]">
        <div className="rounded-lg border border-reaper-border bg-reaper-surface overflow-hidden">
          <div className="px-3 py-2 border-b border-reaper-border text-xs font-mono text-reaper-muted">Jobs</div>
          <div className="max-h-[72vh] overflow-auto">
            {loading ? <div className="p-3 text-xs font-mono text-reaper-muted">Loading...</div> : jobs.length === 0 ? <div className="p-3 text-xs font-mono text-reaper-muted">No jobs yet.</div> : jobs.map((job) => (
              <button key={job.id} onClick={() => setSelectedJobId(job.id)} className={`w-full text-left px-3 py-2 border-b border-reaper-border/50 hover:bg-white/5 ${selectedJobId === job.id ? 'bg-purple-500/10' : ''}`}>
                <div className="flex items-center justify-between gap-2">
                  <div className="text-xs font-mono text-white truncate">{job.name || job.url}</div>
                  <span className={`text-[10px] font-mono ${job.status === 'completed' ? 'text-green-300' : job.status === 'running' ? 'text-blue-300' : job.status === 'cancelled' ? 'text-amber-300' : 'text-reaper-muted'}`}>{job.status}</span>
                </div>
                <div className="text-[10px] font-mono text-reaper-muted truncate mt-1">{job.completed_attempts}/{job.total_attempts} • matched {job.matched_attempts}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-reaper-border bg-reaper-surface p-4 flex flex-col gap-3">
          <div className="text-sm font-mono text-purple-200">Job Builder / Editor</div>
          <input value={name} onChange={(e) => setName(e.target.value)} className="px-3 py-2 rounded bg-black/20 border border-reaper-border text-sm font-mono" placeholder="Job name" />
          <div className="grid grid-cols-[120px_1fr] gap-3">
            <select value={method} onChange={(e) => setMethod(e.target.value)} className="px-3 py-2 rounded bg-black/20 border border-reaper-border text-xs font-mono">
              {['GET','POST','PUT','PATCH','DELETE'].map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
            <input value={url} onChange={(e) => setUrl(e.target.value)} className="px-3 py-2 rounded bg-black/20 border border-reaper-border text-xs font-mono" placeholder="https://target/path?q=§FUZZ§" />
          </div>
          <textarea value={body} onChange={(e) => setBody(e.target.value)} className="min-h-[90px] px-3 py-2 rounded bg-black/20 border border-reaper-border text-xs font-mono" placeholder="Optional body with §FUZZ§ markers" />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <div>
              <div className="text-xs font-mono text-reaper-muted mb-1">Payloads (one per line)</div>
              <textarea value={payloadsText} onChange={(e) => setPayloadsText(e.target.value)} className="w-full min-h-[140px] px-3 py-2 rounded bg-black/20 border border-reaper-border text-xs font-mono" />
            </div>
            <div className="space-y-2">
              <input value={matchSubstring} onChange={(e) => setMatchSubstring(e.target.value)} className="w-full px-3 py-2 rounded bg-black/20 border border-reaper-border text-xs font-mono" placeholder="Match substring (optional)" />
              <input value={rateLimitRps} onChange={(e) => setRateLimitRps(e.target.value)} className="w-full px-3 py-2 rounded bg-black/20 border border-reaper-border text-xs font-mono" placeholder="Rate limit rps (e.g. 5)" />
              <input value={timeoutMs} onChange={(e) => setTimeoutMs(e.target.value)} className="w-full px-3 py-2 rounded bg-black/20 border border-reaper-border text-xs font-mono" placeholder="Timeout ms" />
              <label className="inline-flex items-center gap-2 text-xs font-mono text-reaper-muted"><input type="checkbox" checked={stopOnFirstMatch} onChange={(e) => setStopOnFirstMatch(e.target.checked)} /> Stop on first match</label>
              <label className="inline-flex items-center gap-2 text-xs font-mono text-reaper-muted"><input type="checkbox" checked={waitForCompletion} onChange={(e) => setWaitForCompletion(e.target.checked)} /> Wait for completion on run</label>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 mt-auto">
            <button disabled={busy !== null} onClick={() => void createJob()} className="px-3 py-2 rounded border border-purple-500/30 bg-purple-500/10 text-purple-200 text-xs font-mono inline-flex items-center gap-2 disabled:opacity-50"><Plus className="w-3 h-3" /> Create</button>
            <button disabled={!selectedJobId || busy !== null} onClick={() => void runJob()} className="px-3 py-2 rounded border border-blue-500/30 bg-blue-500/10 text-blue-200 text-xs font-mono inline-flex items-center gap-2 disabled:opacity-50"><Play className="w-3 h-3" /> Run</button>
            <button disabled={!selectedJobId || busy !== null} onClick={() => void cancelJob()} className="px-3 py-2 rounded border border-amber-500/30 bg-amber-500/10 text-amber-200 text-xs font-mono inline-flex items-center gap-2 disabled:opacity-50"><Square className="w-3 h-3" /> Cancel</button>
          </div>
        </div>

        <div className="rounded-lg border border-reaper-border bg-reaper-surface p-4 flex flex-col gap-3">
          <div className="text-sm font-mono text-purple-200">Results {selectedJob ? `(${selectedJob.completed_attempts}/${selectedJob.total_attempts})` : ''}</div>
          {!selectedJob ? (
            <div className="text-xs font-mono text-reaper-muted">Select or create an Intruder job.</div>
          ) : (
            <div className="space-y-2 overflow-auto max-h-[68vh] pr-1">
              {results.length === 0 ? <div className="text-xs font-mono text-reaper-muted">No results yet.</div> : results.map((r) => (
                <div key={r.id} className={`rounded border p-2 ${Number(r.matched) ? 'border-green-500/30 bg-green-500/10' : 'border-reaper-border bg-black/20'}`}>
                  <div className="flex items-center justify-between gap-2 text-xs font-mono">
                    <span className={Number(r.matched) ? 'text-green-300' : 'text-white'}>#{r.attempt_index} payload={r.payload}</span>
                    <span className="text-reaper-muted">{r.response_status ?? 'ERR'} • {r.duration_ms ?? '—'}ms</span>
                  </div>
                  <div className="text-[10px] font-mono text-reaper-muted break-all mt-1">{r.request_url}</div>
                  {r.match_reason && <div className="text-[10px] font-mono text-green-200 mt-1">{r.match_reason}</div>}
                  {r.error && <div className="text-[10px] font-mono text-red-300 mt-1">{r.error}</div>}
                  {r.transaction?.response_body && (
                    <details className="mt-1">
                      <summary className="text-[10px] font-mono text-reaper-muted cursor-pointer">Response preview</summary>
                      <pre className="mt-1 text-[10px] font-mono whitespace-pre-wrap break-words text-emerald-100 max-h-32 overflow-auto">{r.transaction.response_body.slice(0, 2000)}</pre>
                    </details>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
