'use client';

import { useState, useMemo } from 'react';
import { Shield, AlertTriangle, AlertCircle, Info, RefreshCw } from 'lucide-react';
import { clsx } from 'clsx';
import { AnimateIn } from '@/components/shared/animate-in';
import { Counter } from '@/components/shared/counter';
import { SkeletonCard, SkeletonTable } from '@/components/shared/skeleton';
import { useApi } from '@/hooks/use-api';
import type { SecurityFinding } from '@/lib/types';

const severityConfig = {
  critical: { color: 'text-reaper-danger', bg: 'bg-reaper-danger/10', border: 'border-reaper-danger/30', icon: AlertTriangle },
  high: { color: 'text-orange-400', bg: 'bg-orange-400/10', border: 'border-orange-400/30', icon: AlertTriangle },
  medium: { color: 'text-reaper-warning', bg: 'bg-reaper-warning/10', border: 'border-reaper-warning/30', icon: AlertCircle },
  low: { color: 'text-reaper-muted', bg: 'bg-reaper-muted/10', border: 'border-reaper-muted/30', icon: Info },
  info: { color: 'text-reaper-accent', bg: 'bg-reaper-accent/10', border: 'border-reaper-accent/30', icon: Info },
};

type SeverityFilter = 'all' | SecurityFinding['severity'];

export default function SecurityPage() {
  const { data: findings, loading, refetch } = useApi<SecurityFinding[]>('/api/security');
  const [filter, setFilter] = useState<SeverityFilter>('all');

  const counts = useMemo(() => {
    if (!findings) return { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
    return findings.reduce(
      (acc, f) => { acc[f.severity] = (acc[f.severity] || 0) + 1; return acc; },
      { critical: 0, high: 0, medium: 0, low: 0, info: 0 } as Record<string, number>
    );
  }, [findings]);

  const filtered = useMemo(() => {
    if (!findings) return [];
    if (filter === 'all') return findings;
    return findings.filter((f) => f.severity === filter);
  }, [findings, filter]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {loading ? (
          Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)
        ) : (
          (['critical', 'high', 'medium', 'low', 'info'] as const).map((sev, i) => {
            const cfg = severityConfig[sev];
            const Icon = cfg.icon;
            return (
              <AnimateIn key={sev} delay={i * 0.03}>
                <button
                  onClick={() => setFilter(filter === sev ? 'all' : sev)}
                  className={clsx(
                    'w-full bg-reaper-surface border rounded-lg p-3 text-left transition-colors duration-150',
                    filter === sev ? cfg.border : 'border-reaper-border hover:border-reaper-accent/20'
                  )}
                >
                  <div className="flex items-center gap-1.5 mb-1">
                    <Icon className={clsx('w-3.5 h-3.5', cfg.color)} />
                    <span className="text-[10px] font-mono text-reaper-muted uppercase">{sev}</span>
                  </div>
                  <Counter value={counts[sev]} className={clsx('text-lg font-mono font-bold', cfg.color)} />
                </button>
              </AnimateIn>
            );
          })
        )}
      </div>

      <AnimateIn delay={0.15}>
        <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-mono text-white flex items-center gap-2">
              <Shield className="w-4 h-4 text-reaper-accent" />
              Security Findings
              {filter !== 'all' && (
                <span className="text-xs text-reaper-muted">({filter})</span>
              )}
            </h2>
            <button onClick={refetch} className="text-reaper-muted hover:text-white transition-colors">
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>

          {loading ? (
            <SkeletonTable rows={8} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="border-b border-reaper-border text-reaper-muted">
                    <th className="text-left py-2 px-3 font-normal">Severity</th>
                    <th className="text-left py-2 px-3 font-normal">Title</th>
                    <th className="text-left py-2 px-3 font-normal">Category</th>
                    <th className="text-left py-2 px-3 font-normal">URL</th>
                    <th className="text-left py-2 px-3 font-normal">Found</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((f) => {
                    const cfg = severityConfig[f.severity];
                    return (
                      <tr key={f.id} className="border-b border-reaper-border/50 hover:bg-reaper-border/20">
                        <td className="py-2 px-3">
                          <span className={clsx('px-1.5 py-0.5 rounded text-[10px] uppercase', cfg.bg, cfg.color)}>
                            {f.severity}
                          </span>
                        </td>
                        <td className="py-2 px-3 text-white max-w-[200px] truncate">{f.title}</td>
                        <td className="py-2 px-3 text-reaper-muted">{f.category}</td>
                        <td className="py-2 px-3 text-gray-400 max-w-[180px] truncate">{f.url}</td>
                        <td className="py-2 px-3 text-reaper-muted">
                          {new Date(f.found_at).toLocaleDateString()}
                        </td>
                      </tr>
                    );
                  })}
                  {filtered.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-reaper-muted">
                        No findings{filter !== 'all' ? ` with severity "${filter}"` : ''}
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
