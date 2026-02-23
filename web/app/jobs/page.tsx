'use client';

import { useState, useCallback, useEffect } from 'react';
import { Play, Square, RefreshCw, Globe, Layers, Zap, EyeOff, Shield, Clock, CheckCircle2 } from 'lucide-react';
import { clsx } from 'clsx';
import { AnimateIn } from '@/components/shared/animate-in';
import { SkeletonTable } from '@/components/shared/skeleton';
import { useApi, useApiPost } from '@/hooks/use-api';
import api from '@/lib/api';
import type { CrawlJob } from '@/lib/types';

interface NewCrawlForm {
  url: string;
  depth: number;
  concurrency: number;
  stealth: boolean;
  security_scan: boolean;
}

const statusConfig: Record<string, { color: string; icon: React.FC<{ className?: string }> }> = {
  queued:    { color: 'text-reaper-muted',    icon: Clock },
  running:   { color: 'text-reaper-accent',   icon: RefreshCw },
  completed: { color: 'text-reaper-success',  icon: CheckCircle2 },
  failed:    { color: 'text-reaper-danger',   icon: Square },
  cancelled: { color: 'text-reaper-warning',  icon: Square },
};

const inputCls = 'mt-1 w-full bg-reaper-bg border border-reaper-border rounded px-3 py-1.5 text-sm font-mono text-white focus:border-reaper-accent outline-none';
const thCls = 'text-left py-2 px-3 font-normal text-reaper-muted';
const tdCls = 'py-2 px-3';

function ProgressBar({ crawled, total }: { crawled: number; total: number | null }) {
  const pct = total ? Math.min(100, Math.round((crawled / total) * 100)) : null;
  return (
    <div className="flex items-center gap-2">
      <span className="text-gray-300 whitespace-nowrap">{crawled}{total ? `/${total}` : ''}</span>
      {pct !== null && (
        <div className="w-16 h-1.5 bg-reaper-border rounded-full overflow-hidden">
          <div className="h-full bg-reaper-accent rounded-full transition-all" style={{ width: `${pct}%` }} />
        </div>
      )}
    </div>
  );
}

export default function JobsPage() {
  const { data: jobs, loading, refetch } = useApi<CrawlJob[]>('/api/jobs');
  const { post, loading: submitting } = useApiPost<NewCrawlForm, { job_id: string }>();
  const [form, setForm] = useState<NewCrawlForm>({
    url: '', depth: 3, concurrency: 10, stealth: false, security_scan: false,
  });

  // Auto-refresh every 3s while any job is running
  const hasRunning = (jobs || []).some((j) => j.status === 'running');
  useEffect(() => {
    if (!hasRunning) return;
    const t = setInterval(refetch, 3000);
    return () => clearInterval(t);
  }, [hasRunning, refetch]);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.url.trim()) return;
    await post('/api/jobs', form);
    setForm((f) => ({ ...f, url: '' }));
    setTimeout(refetch, 500);
  }, [form, post, refetch]);

  const cancelJob = useCallback(async (id: string) => {
    await api.post(`/api/jobs/${id}/cancel`);
    refetch();
  }, [refetch]);

  const toggleOpt = (key: keyof NewCrawlForm) =>
    setForm((f) => ({ ...f, [key]: !f[key] }));

  return (
    <div className="space-y-4">
      <AnimateIn>
        <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
          <h2 className="text-sm font-mono text-white mb-4 flex items-center gap-2">
            <Play className="w-4 h-4 text-reaper-accent" /> Start New Crawl
          </h2>
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="flex flex-wrap gap-3 items-end">
              <label className="flex-1 min-w-[240px]">
                <span className="text-xs font-mono text-reaper-muted flex items-center gap-1">
                  <Globe className="w-3 h-3" /> Target URL
                </span>
                <input
                  value={form.url}
                  onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))}
                  placeholder="https://example.com"
                  className={inputCls + ' placeholder:text-reaper-muted/50'}
                  required
                />
              </label>
              <label className="w-24">
                <span className="text-xs font-mono text-reaper-muted flex items-center gap-1">
                  <Layers className="w-3 h-3" /> Depth
                </span>
                <input
                  type="number"
                  value={form.depth}
                  onChange={(e) => setForm((f) => ({ ...f, depth: Number(e.target.value) }))}
                  min={1} max={10}
                  className={inputCls}
                />
              </label>
              <label className="w-32">
                <span className="text-xs font-mono text-reaper-muted flex items-center gap-1">
                  <Zap className="w-3 h-3" /> Concurrency
                </span>
                <input
                  type="number"
                  value={form.concurrency}
                  onChange={(e) => setForm((f) => ({ ...f, concurrency: Number(e.target.value) }))}
                  min={1} max={100}
                  className={inputCls}
                />
              </label>
            </div>

            <div className="flex flex-wrap items-center gap-4 pt-1">
              <label
                className={clsx(
                  'flex items-center gap-2 px-3 py-1.5 rounded border cursor-pointer transition-colors text-xs font-mono',
                  form.stealth
                    ? 'border-reaper-accent/40 bg-reaper-accent/10 text-reaper-accent'
                    : 'border-reaper-border text-reaper-muted hover:border-reaper-accent/20'
                )}
              >
                <input type="checkbox" checked={form.stealth} onChange={() => toggleOpt('stealth')} className="hidden" />
                <EyeOff className="w-3 h-3" /> Stealth Mode
              </label>

              <label
                className={clsx(
                  'flex items-center gap-2 px-3 py-1.5 rounded border cursor-pointer transition-colors text-xs font-mono',
                  form.security_scan
                    ? 'border-reaper-warning/40 bg-reaper-warning/10 text-reaper-warning'
                    : 'border-reaper-border text-reaper-muted hover:border-reaper-warning/20'
                )}
              >
                <input type="checkbox" checked={form.security_scan} onChange={() => toggleOpt('security_scan')} className="hidden" />
                <Shield className="w-3 h-3" /> Security Scan After Crawl
              </label>

              <button
                type="submit"
                disabled={submitting}
                className="ml-auto px-5 py-1.5 bg-reaper-accent/10 text-reaper-accent border border-reaper-accent/30 rounded text-sm font-mono hover:bg-reaper-accent/20 transition-colors disabled:opacity-50"
              >
                {submitting ? 'Starting...' : '▶ Start Crawl'}
              </button>
            </div>
          </form>
        </div>
      </AnimateIn>

      <AnimateIn delay={0.1}>
        <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-mono text-white flex items-center gap-2">
              Jobs
              {hasRunning && (
                <span className="w-1.5 h-1.5 rounded-full bg-reaper-accent animate-pulse-soft" />
              )}
            </h2>
            <button onClick={refetch} className="text-reaper-muted hover:text-white transition-colors">
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>

          {loading ? (
            <SkeletonTable rows={5} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="border-b border-reaper-border">
                    <th className={thCls}>URL</th>
                    <th className={thCls}>Status</th>
                    <th className={thCls}>Progress</th>
                    <th className={thCls}>Depth</th>
                    <th className={thCls}>Flags</th>
                    <th className={thCls}>Started</th>
                    <th className={thCls}></th>
                  </tr>
                </thead>
                <tbody>
                  {(jobs || []).map((job) => {
                    const cfg = statusConfig[job.status] ?? statusConfig.queued;
                    const Icon = cfg.icon;
                    return (
                      <tr key={job.id} className="border-b border-reaper-border/50 hover:bg-reaper-border/20">
                        <td className={tdCls + ' text-gray-300 max-w-[220px]'}>
                          <span className="truncate block" title={job.url}>{job.url || '—'}</span>
                        </td>
                        <td className={clsx(tdCls, cfg.color)}>
                          <span className="flex items-center gap-1">
                            <Icon className={clsx('w-3 h-3', job.status === 'running' && 'animate-spin')} />
                            {job.status}
                          </span>
                        </td>
                        <td className={tdCls}>
                          <ProgressBar crawled={job.pages_crawled} total={job.pages_total} />
                        </td>
                        <td className={tdCls + ' text-gray-400'}>{job.depth}</td>
                        <td className={tdCls}>
                          <div className="flex gap-1">
                            {job.stealth && <span className="px-1 py-0.5 rounded bg-reaper-accent/10 text-reaper-accent text-[9px]">STEALTH</span>}
                            {(job as CrawlJob & { security_scan?: boolean }).security_scan && <span className="px-1 py-0.5 rounded bg-reaper-warning/10 text-reaper-warning text-[9px]">SCAN</span>}
                          </div>
                        </td>
                        <td className={tdCls + ' text-reaper-muted'}>
                          {job.started_at ? new Date(job.started_at).toLocaleTimeString() : '—'}
                        </td>
                        <td className={tdCls}>
                          {job.status === 'running' && (
                            <button
                              onClick={() => cancelJob(job.id)}
                              className="text-reaper-danger hover:text-red-400 transition-colors p-1 rounded hover:bg-reaper-danger/10"
                              title="Stop job"
                            >
                              <Square className="w-3 h-3" />
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                  {(!jobs || jobs.length === 0) && (
                    <tr>
                      <td colSpan={7} className="py-10 text-center text-reaper-muted">
                        No jobs yet — start a crawl above
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </AnimateIn>
    </div>
  );
}
