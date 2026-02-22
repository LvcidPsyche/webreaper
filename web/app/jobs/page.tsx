'use client';

import { useState, useCallback } from 'react';
import { Play, Square, RefreshCw, Globe, Layers, Zap, EyeOff } from 'lucide-react';
import { clsx } from 'clsx';
import { AnimateIn } from '@/components/shared/animate-in';
import { SkeletonTable } from '@/components/shared/skeleton';
import { useApi, useApiPost } from '@/hooks/use-api';
import api from '@/lib/api';
import type { CrawlJob } from '@/lib/types';

interface NewCrawlForm { url: string; depth: number; concurrency: number; stealth: boolean }

const statusColors: Record<string, string> = {
  queued: 'text-reaper-muted', running: 'text-reaper-accent', completed: 'text-reaper-success',
  failed: 'text-reaper-danger', cancelled: 'text-reaper-warning',
};
const inputCls = 'mt-1 w-full bg-reaper-bg border border-reaper-border rounded px-3 py-1.5 text-sm font-mono text-white focus:border-reaper-accent outline-none';
const thCls = 'text-left py-2 px-3 font-normal';
const tdCls = 'py-2 px-3';

export default function JobsPage() {
  const { data: jobs, loading, refetch } = useApi<CrawlJob[]>('/api/jobs');
  const { post, loading: submitting } = useApiPost<NewCrawlForm, CrawlJob>();
  const [form, setForm] = useState<NewCrawlForm>({ url: '', depth: 3, concurrency: 10, stealth: false });

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.url.trim()) return;
    await post('/api/jobs', form);
    setForm((f) => ({ ...f, url: '' }));
    refetch();
  }, [form, post, refetch]);

  const cancelJob = useCallback(async (id: string) => {
    await api.post(`/api/jobs/${id}/cancel`);
    refetch();
  }, [refetch]);

  return (
    <div className="space-y-4">
      <AnimateIn>
        <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
          <h2 className="text-sm font-mono text-white mb-3 flex items-center gap-2">
            <Play className="w-4 h-4 text-reaper-accent" /> Start New Crawl
          </h2>
          <form onSubmit={handleSubmit} className="flex flex-wrap gap-3 items-end">
            <label className="flex-1 min-w-[200px]">
              <span className="text-xs font-mono text-reaper-muted flex items-center gap-1"><Globe className="w-3 h-3" /> Target URL</span>
              <input value={form.url} onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))} placeholder="https://example.com" className={inputCls + ' placeholder:text-reaper-muted'} required />
            </label>
            <label className="w-24">
              <span className="text-xs font-mono text-reaper-muted flex items-center gap-1"><Layers className="w-3 h-3" /> Depth</span>
              <input type="number" value={form.depth} onChange={(e) => setForm((f) => ({ ...f, depth: Number(e.target.value) }))} min={1} max={10} className={inputCls} />
            </label>
            <label className="w-32">
              <span className="text-xs font-mono text-reaper-muted flex items-center gap-1"><Zap className="w-3 h-3" /> Concurrency</span>
              <input type="number" value={form.concurrency} onChange={(e) => setForm((f) => ({ ...f, concurrency: Number(e.target.value) }))} min={1} max={50} className={inputCls} />
            </label>
            <label className="flex items-center gap-2 pb-1">
              <input type="checkbox" checked={form.stealth} onChange={(e) => setForm((f) => ({ ...f, stealth: e.target.checked }))} className="accent-reaper-accent" />
              <span className="text-xs font-mono text-reaper-muted flex items-center gap-1"><EyeOff className="w-3 h-3" /> Stealth</span>
            </label>
            <button type="submit" disabled={submitting} className="px-4 py-1.5 bg-reaper-accent/10 text-reaper-accent border border-reaper-accent/30 rounded text-sm font-mono hover:bg-reaper-accent/20 transition-colors disabled:opacity-50">
              {submitting ? 'Starting...' : 'Start Crawl'}
            </button>
          </form>
        </div>
      </AnimateIn>

      <AnimateIn delay={0.1}>
        <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-mono text-white">Jobs</h2>
            <button onClick={refetch} className="text-reaper-muted hover:text-white transition-colors"><RefreshCw className="w-3.5 h-3.5" /></button>
          </div>
          {loading ? <SkeletonTable rows={5} /> : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="border-b border-reaper-border text-reaper-muted">
                    <th className={thCls}>URL</th><th className={thCls}>Status</th><th className={thCls}>Progress</th>
                    <th className={thCls}>Depth</th><th className={thCls}>Started</th><th className={thCls}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {(jobs || []).map((job) => (
                    <tr key={job.id} className="border-b border-reaper-border/50 hover:bg-reaper-border/20">
                      <td className={tdCls + ' text-gray-300 max-w-[200px] truncate'}>{job.url}</td>
                      <td className={clsx(tdCls, 'uppercase', statusColors[job.status])}>{job.status}</td>
                      <td className={tdCls + ' text-gray-300'}>{job.pages_crawled}/{job.pages_total || '?'}</td>
                      <td className={tdCls + ' text-gray-300'}>{job.depth}</td>
                      <td className={tdCls + ' text-reaper-muted'}>{job.started_at ? new Date(job.started_at).toLocaleTimeString() : '-'}</td>
                      <td className={tdCls}>
                        {job.status === 'running' && (
                          <button onClick={() => cancelJob(job.id)} className="text-reaper-danger hover:text-red-400 transition-colors"><Square className="w-3 h-3" /></button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {(!jobs || jobs.length === 0) && (
                    <tr><td colSpan={6} className="py-8 text-center text-reaper-muted">No jobs yet</td></tr>
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
