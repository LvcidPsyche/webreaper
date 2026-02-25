'use client';

import { useState, useMemo, useCallback, useEffect } from 'react';
import { Shield, AlertTriangle, AlertCircle, Info, RefreshCw, Scan, ExternalLink, ChevronDown, ChevronRight } from 'lucide-react';
import { clsx } from 'clsx';
import { AnimateIn } from '@/components/shared/animate-in';
import { Counter } from '@/components/shared/counter';
import { SkeletonCard, SkeletonTable } from '@/components/shared/skeleton';
import { useApi } from '@/hooks/use-api';
import api from '@/lib/api';
import type { SecurityFinding } from '@/lib/types';

const severityConfig = {
  critical: { color: 'text-reaper-danger',  bg: 'bg-reaper-danger/10',  border: 'border-reaper-danger/30',  icon: AlertTriangle },
  high:     { color: 'text-orange-400',     bg: 'bg-orange-400/10',     border: 'border-orange-400/30',     icon: AlertTriangle },
  medium:   { color: 'text-reaper-warning', bg: 'bg-reaper-warning/10', border: 'border-reaper-warning/30', icon: AlertCircle },
  low:      { color: 'text-reaper-muted',   bg: 'bg-reaper-muted/10',   border: 'border-reaper-muted/30',   icon: Info },
  info:     { color: 'text-reaper-accent',  bg: 'bg-reaper-accent/10',  border: 'border-reaper-accent/30',  icon: Info },
};

type SeverityFilter = 'all' | keyof typeof severityConfig;

interface ScanResult {
  url: string;
  status_code: number;
  findings_count: number;
  findings: SecurityFinding[];
  technology: Record<string, unknown>;
}

export default function SecurityPage() {
  const { data: findings, loading, refetch } = useApi<SecurityFinding[]>('/api/security');
  const [filter, setFilter] = useState<SeverityFilter>('all');
  const [scanUrl, setScanUrl] = useState('');
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [triageSaving, setTriageSaving] = useState<string | null>(null);
  const [exporting, setExporting] = useState<'json' | 'markdown' | null>(null);

  useEffect(() => {
    api.get<Record<string, unknown>>('/api/governance/ui-preferences?page=security').then((prefs) => {
      const savedFilter = prefs['severity.filter'];
      if (typeof savedFilter === 'string' && (savedFilter === 'all' || savedFilter in severityConfig)) {
        setFilter(savedFilter as SeverityFilter);
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    api.put('/api/governance/ui-preferences', {
      page: 'security',
      key: 'severity.filter',
      value: filter,
    }).catch(() => {});
  }, [filter]);

  const counts = useMemo(() => {
    if (!findings) return { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
    return findings.reduce(
      (acc, f) => { acc[f.severity] = (acc[f.severity] || 0) + 1; return acc; },
      { critical: 0, high: 0, medium: 0, low: 0, info: 0 } as Record<string, number>
    );
  }, [findings]);

  const filtered = useMemo(() => {
    if (!findings) return [];
    return filter === 'all' ? findings : findings.filter((f) => f.severity === filter);
  }, [findings, filter]);

  const handleScan = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!scanUrl.trim()) return;
    setScanning(true);
    setScanResult(null);
    try {
      const result = await api.post<ScanResult>('/api/security/scan', { url: scanUrl });
      setScanResult(result);
      refetch();
    } catch {
      // error surfaced in scan result
    } finally {
      setScanning(false);
    }
  }, [scanUrl, refetch]);

  const updateTriage = useCallback(async (finding: SecurityFinding, status: string) => {
    setTriageSaving(finding.id);
    try {
      await api.patch(`/api/security/findings/${finding.id}/triage`, {
        status,
        assignee: finding.triage_assignee || null,
        tags: finding.triage_tags || [],
        notes: finding.triage_notes || null,
      });
      await refetch();
    } finally {
      setTriageSaving(null);
    }
  }, [refetch]);

  const exportReport = useCallback(async (format: 'json' | 'markdown') => {
    setExporting(format);
    try {
      const res = await api.get<{ content?: string; total: number } | { total: number }>(`/api/security/report/export?format=${format}`);
      if (format === 'markdown' && 'content' in res && res.content) {
        const blob = new Blob([res.content], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'webreaper-security-report.md';
        a.click();
        URL.revokeObjectURL(url);
      } else {
        const blob = new Blob([JSON.stringify(res, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'webreaper-security-report.json';
        a.click();
        URL.revokeObjectURL(url);
      }
    } finally {
      setExporting(null);
    }
  }, []);

  return (
    <div className="space-y-4">
      {/* Severity counters */}
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
                    'w-full bg-reaper-surface border rounded-lg p-3 text-left transition-colors',
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

      {/* On-demand scanner */}
      <AnimateIn delay={0.1}>
        <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
          <h2 className="text-sm font-mono text-white mb-3 flex items-center gap-2">
            <Scan className="w-4 h-4 text-reaper-accent" /> On-Demand Security Scan
          </h2>
          <form onSubmit={handleScan} className="flex gap-2">
            <input
              value={scanUrl}
              onChange={(e) => setScanUrl(e.target.value)}
              placeholder="https://target.com"
              className="flex-1 bg-reaper-bg border border-reaper-border rounded px-3 py-1.5 text-sm font-mono text-white focus:border-reaper-accent outline-none placeholder:text-reaper-muted/50"
              required
            />
            <button
              type="submit"
              disabled={scanning}
              className="px-4 py-1.5 bg-reaper-accent/10 text-reaper-accent border border-reaper-accent/30 rounded text-sm font-mono hover:bg-reaper-accent/20 transition-colors disabled:opacity-50 whitespace-nowrap"
            >
              {scanning ? 'Scanning...' : 'Scan'}
            </button>
          </form>

          {scanResult && (
            <div className="mt-3 pt-3 border-t border-reaper-border space-y-2">
              <div className="flex items-center gap-3 text-xs font-mono">
                <span className="text-reaper-muted">{scanResult.url}</span>
                <span className="text-reaper-muted">HTTP {scanResult.status_code}</span>
                <span className={clsx(scanResult.findings_count > 0 ? 'text-reaper-warning' : 'text-reaper-success')}>
                  {scanResult.findings_count} finding{scanResult.findings_count !== 1 ? 's' : ''}
                </span>
              </div>

              {/* Technology stack */}
              {Object.keys(scanResult.technology).length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(scanResult.technology).flatMap(([cat, items]) =>
                    (Array.isArray(items) ? items : [items]).filter(Boolean).map((item) => (
                      <span key={`${cat}-${item}`} className="px-1.5 py-0.5 rounded bg-reaper-border text-[10px] font-mono text-reaper-muted">
                        {String(item)}
                      </span>
                    ))
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </AnimateIn>

      {/* Findings table */}
      <AnimateIn delay={0.15}>
        <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-mono text-white flex items-center gap-2">
              <Shield className="w-4 h-4 text-reaper-accent" />
              Security Findings
              {filter !== 'all' && <span className="text-xs text-reaper-muted">({filter})</span>}
            </h2>
            <button onClick={refetch} className="text-reaper-muted hover:text-white transition-colors">
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="flex gap-2 mb-3">
            <button onClick={() => void exportReport('json')} disabled={!!exporting} className="px-2 py-1 rounded border border-reaper-border text-xs font-mono text-reaper-muted hover:text-white disabled:opacity-50">
              {exporting === 'json' ? 'Exporting...' : 'Export JSON'}
            </button>
            <button onClick={() => void exportReport('markdown')} disabled={!!exporting} className="px-2 py-1 rounded border border-reaper-border text-xs font-mono text-reaper-muted hover:text-white disabled:opacity-50">
              {exporting === 'markdown' ? 'Exporting...' : 'Export MD'}
            </button>
          </div>

          {loading ? (
            <SkeletonTable rows={8} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="border-b border-reaper-border text-reaper-muted">
                    <th className="text-left py-2 px-3 font-normal w-4"></th>
                    <th className="text-left py-2 px-3 font-normal">Severity</th>
                    <th className="text-left py-2 px-3 font-normal">Title</th>
                    <th className="text-left py-2 px-3 font-normal">Category</th>
                    <th className="text-left py-2 px-3 font-normal">URL</th>
                    <th className="text-left py-2 px-3 font-normal">Found</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((f) => {
                    const cfg = severityConfig[f.severity] ?? severityConfig.info;
                    const isExpanded = expandedRow === f.id;
                    return (
                      <>
                        <tr
                          key={f.id}
                          className="border-b border-reaper-border/50 hover:bg-reaper-border/20 cursor-pointer"
                          onClick={() => setExpandedRow(isExpanded ? null : f.id)}
                        >
                          <td className="py-2 px-3 text-reaper-muted">
                            {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                          </td>
                          <td className="py-2 px-3">
                            <span className={clsx('px-1.5 py-0.5 rounded text-[10px] uppercase', cfg.bg, cfg.color)}>
                              {f.severity}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-white max-w-[200px] truncate">{f.title}</td>
                          <td className="py-2 px-3 text-reaper-muted">{f.category}</td>
                          <td className="py-2 px-3 text-gray-400 max-w-[180px]">
                            <span className="flex items-center gap-1">
                              <span className="truncate">{f.url}</span>
                              <a href={f.url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}>
                                <ExternalLink className="w-3 h-3 shrink-0 hover:text-reaper-accent" />
                              </a>
                            </span>
                          </td>
                          <td className="py-2 px-3 text-reaper-muted">
                            {f.found_at ? new Date(f.found_at).toLocaleDateString() : '—'}
                          </td>
                        </tr>
                        {isExpanded && (
                          <tr key={`${f.id}-detail`} className="bg-reaper-bg/40 border-b border-reaper-border/50">
                            <td colSpan={6} className="px-4 py-3 space-y-2">
                              {f.evidence && (
                                <div>
                                  <span className="text-reaper-muted text-[10px] uppercase tracking-wider">Evidence</span>
                                  <p className="mt-0.5 text-gray-300 break-all">{f.evidence}</p>
                                </div>
                              )}
                              {(f as SecurityFinding & { remediation?: string }).remediation && (
                                <div>
                                  <span className="text-reaper-muted text-[10px] uppercase tracking-wider">Remediation</span>
                                  <p className="mt-0.5 text-gray-300">{(f as SecurityFinding & { remediation?: string }).remediation}</p>
                                </div>
                              )}
                              {(f as SecurityFinding & { parameter?: string }).parameter && (
                                <div>
                                  <span className="text-reaper-muted text-[10px] uppercase tracking-wider">Parameter</span>
                                  <code className="mt-0.5 text-reaper-accent">{(f as SecurityFinding & { parameter?: string }).parameter}</code>
                                </div>
                              )}
                              <div className="pt-2 border-t border-reaper-border/40 flex flex-wrap items-center gap-2">
                                <span className="text-reaper-muted text-[10px] uppercase tracking-wider">Triage</span>
                                <select
                                  value={f.triage_status || 'open'}
                                  disabled={triageSaving === f.id}
                                  onChange={(e) => void updateTriage(f, e.target.value)}
                                  className="bg-reaper-surface border border-reaper-border rounded px-2 py-1 text-[10px] font-mono text-white"
                                >
                                  {['open', 'in_progress', 'resolved', 'false_positive', 'risk_accepted'].map((s) => (
                                    <option key={s} value={s}>{s}</option>
                                  ))}
                                </select>
                                {f.triage_assignee && <span className="text-[10px] text-reaper-muted">assignee: {f.triage_assignee}</span>}
                              </div>
                            </td>
                          </tr>
                        )}
                      </>
                    );
                  })}
                  {filtered.length === 0 && (
                    <tr>
                      <td colSpan={6} className="py-10 text-center text-reaper-muted">
                        {findings?.length === 0
                          ? 'No findings yet — run a crawl with "Security Scan" enabled or use the scanner above'
                          : `No ${filter !== 'all' ? filter + ' ' : ''}findings`
                        }
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
