'use client';

import { useState, useCallback, useEffect } from 'react';
import {
  Database, Download, Search, ChevronUp, ChevronDown,
  ChevronLeft, ChevronRight, X, Globe, Clock, FileText,
  ExternalLink, RefreshCw,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { clsx } from 'clsx';
import { AnimateIn } from '@/components/shared/animate-in';
import { SkeletonCard, SkeletonTable } from '@/components/shared/skeleton';
import { useApi } from '@/hooks/use-api';
import api from '@/lib/api';
import { API_BASE_URL } from '@/lib/constants';

// ── Types ────────────────────────────────────────────────────

interface Crawl {
  id: string;
  target_url: string;
  status: string;
  genre: string | null;
  pages_crawled: number;
  pages_failed: number;
  total_bytes: number;
  external_links: number;
  requests_per_sec: number | null;
  started_at: string | null;
  completed_at: string | null;
}

interface PageRow {
  id: string;
  url: string;
  domain: string;
  path: string;
  status_code: number;
  title: string | null;
  h1: string | null;
  response_time_ms: number | null;
  word_count: number | null;
  links_count: number | null;
  external_links_count: number | null;
  depth: number;
  scraped_at: string;
}

interface PageDetail {
  id: string;
  url: string;
  canonical_url: string | null;
  domain: string;
  path: string;
  status_code: number;
  content_type: string | null;
  response_time_ms: number | null;
  title: string | null;
  meta_description: string | null;
  word_count: number | null;
  headings: Array<{ level: number; text: string }> | null;
  h1: string | null;
  h2s: string[] | null;
  links_count: number | null;
  external_links_count: number | null;
  images_count: number | null;
  depth: number;
  scraped_at: string;
  response_headers: Record<string, string> | null;
}

interface PageList {
  total: number;
  page: number;
  per_page: number;
  pages: PageRow[];
}

interface Stats {
  status_codes: Array<{ status_code: number; count: number }>;
  top_domains: Array<{ domain: string; count: number }>;
  response_times: Array<{ bucket: string; count: number }>;
  depth_distribution: Array<{ depth: number; count: number }>;
  totals: {
    total_pages: number;
    total_domains: number;
    avg_response_ms: number | null;
    total_words: number | null;
    total_internal_links: number | null;
    total_external_links: number | null;
  };
}

// ── Helpers ──────────────────────────────────────────────────

const statusColor = (code: number) => {
  if (code >= 500) return 'text-reaper-danger';
  if (code >= 400) return 'text-reaper-warning';
  if (code >= 300) return 'text-yellow-400';
  return 'text-reaper-success';
};

const barFill = (code: number) => {
  if (code >= 500) return '#ff4444';
  if (code >= 400) return '#ffaa00';
  if (code >= 300) return '#facc15';
  return '#00ff88';
};

const fmtMs = (ms: number | null) =>
  ms === null ? '—' : ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(2)}s`;

const fmtNum = (n: number | null | undefined) =>
  n === null || n === undefined ? '—' : n.toLocaleString();

const fmtBytes = (b: number) => {
  if (!b) return '0 B';
  if (b < 1024) return `${b} B`;
  if (b < 1048576) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1048576).toFixed(1)} MB`;
};

// ── Stat card ────────────────────────────────────────────────

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4 flex items-start gap-3">
      <div className="w-8 h-8 rounded bg-reaper-accent/10 flex items-center justify-center shrink-0">
        <Icon className="w-4 h-4 text-reaper-accent" />
      </div>
      <div>
        <div className="text-xs font-mono text-reaper-muted">{label}</div>
        <div className="text-lg font-mono text-white mt-0.5">{value}</div>
        {sub && <div className="text-xs font-mono text-reaper-muted mt-0.5">{sub}</div>}
      </div>
    </div>
  );
}

// ── Detail panel ─────────────────────────────────────────────

function DetailPanel({
  pageId,
  onClose,
}: {
  pageId: string;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<PageDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .get<PageDetail>(`/api/data/pages/${pageId}`)
      .then((d) => setDetail(d))
      .catch(() => setDetail(null))
      .finally(() => setLoading(false));
  }, [pageId]);

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div
        className="flex-1 bg-black/40"
        onClick={onClose}
      />
      <div className="w-[480px] h-full bg-reaper-surface border-l border-reaper-border overflow-y-auto flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-reaper-border sticky top-0 bg-reaper-surface z-10">
          <span className="text-sm font-mono text-white">Page Detail</span>
          <button onClick={onClose} className="text-reaper-muted hover:text-white">
            <X className="w-4 h-4" />
          </button>
        </div>

        {loading ? (
          <div className="p-4 space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        ) : !detail ? (
          <div className="p-4 text-sm font-mono text-reaper-muted">Failed to load page detail.</div>
        ) : (
          <div className="p-4 space-y-4">
            {/* URL */}
            <div>
              <div className="text-xs font-mono text-reaper-muted mb-1">URL</div>
              <a
                href={detail.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-mono text-reaper-accent break-all hover:underline flex items-start gap-1"
              >
                {detail.url}
                <ExternalLink className="w-3 h-3 mt-0.5 shrink-0" />
              </a>
            </div>

            {/* Meta grid */}
            <div className="grid grid-cols-2 gap-3 text-xs font-mono">
              <div>
                <div className="text-reaper-muted mb-0.5">Status</div>
                <div className={clsx('font-bold', statusColor(detail.status_code))}>
                  {detail.status_code}
                </div>
              </div>
              <div>
                <div className="text-reaper-muted mb-0.5">Depth</div>
                <div className="text-white">{detail.depth}</div>
              </div>
              <div>
                <div className="text-reaper-muted mb-0.5">Response Time</div>
                <div className="text-white">{fmtMs(detail.response_time_ms)}</div>
              </div>
              <div>
                <div className="text-reaper-muted mb-0.5">Content Type</div>
                <div className="text-white truncate">{detail.content_type ?? '—'}</div>
              </div>
              <div>
                <div className="text-reaper-muted mb-0.5">Words</div>
                <div className="text-white">{fmtNum(detail.word_count)}</div>
              </div>
              <div>
                <div className="text-reaper-muted mb-0.5">Images</div>
                <div className="text-white">{fmtNum(detail.images_count)}</div>
              </div>
              <div>
                <div className="text-reaper-muted mb-0.5">Internal Links</div>
                <div className="text-white">{fmtNum(detail.links_count)}</div>
              </div>
              <div>
                <div className="text-reaper-muted mb-0.5">External Links</div>
                <div className="text-white">{fmtNum(detail.external_links_count)}</div>
              </div>
            </div>

            {/* Title + H1 */}
            {(detail.title || detail.h1) && (
              <div className="space-y-2">
                {detail.title && (
                  <div>
                    <div className="text-xs font-mono text-reaper-muted mb-0.5">Title</div>
                    <div className="text-sm font-mono text-white">{detail.title}</div>
                  </div>
                )}
                {detail.h1 && (
                  <div>
                    <div className="text-xs font-mono text-reaper-muted mb-0.5">H1</div>
                    <div className="text-sm font-mono text-white">{detail.h1}</div>
                  </div>
                )}
                {detail.meta_description && (
                  <div>
                    <div className="text-xs font-mono text-reaper-muted mb-0.5">Meta Description</div>
                    <div className="text-xs font-mono text-white/80">{detail.meta_description}</div>
                  </div>
                )}
              </div>
            )}

            {/* H2s */}
            {detail.h2s && detail.h2s.length > 0 && (
              <div>
                <div className="text-xs font-mono text-reaper-muted mb-1">H2 Headings</div>
                <div className="space-y-1">
                  {detail.h2s.slice(0, 8).map((h, i) => (
                    <div key={i} className="text-xs font-mono text-white/70 border-l-2 border-reaper-border pl-2">
                      {h}
                    </div>
                  ))}
                  {detail.h2s.length > 8 && (
                    <div className="text-xs font-mono text-reaper-muted">
                      +{detail.h2s.length - 8} more
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Response headers */}
            {detail.response_headers && Object.keys(detail.response_headers).length > 0 && (
              <div>
                <div className="text-xs font-mono text-reaper-muted mb-1">Response Headers</div>
                <div className="bg-reaper-bg rounded p-2 space-y-1 max-h-48 overflow-y-auto">
                  {Object.entries(detail.response_headers)
                    .slice(0, 20)
                    .map(([k, v]) => (
                      <div key={k} className="text-xs font-mono flex gap-2">
                        <span className="text-reaper-accent shrink-0">{k}:</span>
                        <span className="text-white/70 break-all">{String(v)}</span>
                      </div>
                    ))}
                </div>
              </div>
            )}

            <div className="text-xs font-mono text-reaper-muted">
              Scraped {new Date(detail.scraped_at).toLocaleString()}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Sort header ──────────────────────────────────────────────

function SortHeader({
  col,
  label,
  sort,
  order,
  onSort,
}: {
  col: string;
  label: string;
  sort: string;
  order: string;
  onSort: (col: string) => void;
}) {
  const active = sort === col;
  return (
    <th
      className="px-3 py-2 text-left text-xs font-mono text-reaper-muted cursor-pointer hover:text-white select-none whitespace-nowrap"
      onClick={() => onSort(col)}
    >
      <span className="flex items-center gap-1">
        {label}
        {active ? (
          order === 'asc' ? (
            <ChevronUp className="w-3 h-3 text-reaper-accent" />
          ) : (
            <ChevronDown className="w-3 h-3 text-reaper-accent" />
          )
        ) : (
          <ChevronDown className="w-3 h-3 opacity-30" />
        )}
      </span>
    </th>
  );
}

// ── Main page ────────────────────────────────────────────────

export default function DataPage() {
  const { data: crawls, loading: crawlsLoading, refetch: refetchCrawls } = useApi<Crawl[]>('/api/data/crawls');
  const [selectedCrawl, setSelectedCrawl] = useState<string>('');
  const [stats, setStats] = useState<Stats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  // Table state
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [sort, setSort] = useState('scraped_at');
  const [order, setOrder] = useState('desc');
  const [page, setPage] = useState(1);
  const [pageData, setPageData] = useState<PageList | null>(null);
  const [tableLoading, setTableLoading] = useState(false);

  // Detail panel
  const [detailId, setDetailId] = useState<string | null>(null);

  // Debounce search input
  useEffect(() => {
    const t = setTimeout(() => { setDebouncedSearch(search); setPage(1); }, 350);
    return () => clearTimeout(t);
  }, [search]);

  // Auto-select first crawl
  useEffect(() => {
    if (crawls && crawls.length > 0 && !selectedCrawl) {
      setSelectedCrawl(crawls[0].id);
    }
  }, [crawls, selectedCrawl]);

  // Load stats when crawl changes
  useEffect(() => {
    if (!selectedCrawl) return;
    setStatsLoading(true);
    api
      .get<Stats>(`/api/data/stats/${selectedCrawl}`)
      .then((d) => setStats(d))
      .catch(() => setStats(null))
      .finally(() => setStatsLoading(false));
  }, [selectedCrawl]);

  // Load pages
  useEffect(() => {
    if (!selectedCrawl) return;
    setTableLoading(true);
    const params = new URLSearchParams({
      crawl_id: selectedCrawl,
      sort,
      order,
      page: String(page),
      per_page: '50',
    });
    if (debouncedSearch) params.set('search', debouncedSearch);
    if (filterStatus) params.set('status_code', filterStatus);

    api
      .get<PageList>(`/api/data/pages?${params}`)
      .then((d) => setPageData(d))
      .catch(() => setPageData(null))
      .finally(() => setTableLoading(false));
  }, [selectedCrawl, sort, order, page, debouncedSearch, filterStatus]);

  const handleSort = useCallback(
    (col: string) => {
      if (sort === col) setOrder((o) => (o === 'asc' ? 'desc' : 'asc'));
      else { setSort(col); setOrder('desc'); }
      setPage(1);
    },
    [sort],
  );

  const handleCrawlChange = (id: string) => {
    setSelectedCrawl(id);
    setSearch('');
    setDebouncedSearch('');
    setFilterStatus('');
    setPage(1);
    setPageData(null);
    setStats(null);
  };

  const selectedCrawlObj = crawls?.find((c) => c.id === selectedCrawl);
  const totalPages = pageData ? Math.ceil(pageData.total / pageData.per_page) : 1;

  const exportUrl = (fmt: string) =>
    selectedCrawl ? `${API_BASE_URL}/api/data/export/${selectedCrawl}?fmt=${fmt}` : '#';

  return (
    <div className="space-y-4">
      {/* Header row */}
      <AnimateIn className="flex items-center justify-between">
        <h1 className="text-sm font-mono text-white flex items-center gap-2">
          <Database className="w-4 h-4 text-reaper-accent" />
          Data Explorer
        </h1>
        <div className="flex items-center gap-2">
          <button
            onClick={refetchCrawls}
            className="p-1.5 text-reaper-muted hover:text-white transition-colors"
            title="Refresh crawl list"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          {selectedCrawl && (
            <>
              <a
                href={exportUrl('csv')}
                download
                className="flex items-center gap-1.5 px-3 py-1.5 bg-reaper-surface border border-reaper-border rounded text-xs font-mono text-reaper-muted hover:text-white hover:border-reaper-accent/30 transition-colors"
              >
                <Download className="w-3 h-3" /> CSV
              </a>
              <a
                href={exportUrl('json')}
                download
                className="flex items-center gap-1.5 px-3 py-1.5 bg-reaper-surface border border-reaper-border rounded text-xs font-mono text-reaper-muted hover:text-white hover:border-reaper-accent/30 transition-colors"
              >
                <Download className="w-3 h-3" /> JSON
              </a>
            </>
          )}
        </div>
      </AnimateIn>

      {/* Crawl selector */}
      <AnimateIn delay={0.03}>
        {crawlsLoading ? (
          <SkeletonCard />
        ) : !crawls || crawls.length === 0 ? (
          <div className="bg-reaper-surface border border-reaper-border rounded-lg p-6 text-center">
            <Database className="w-8 h-8 text-reaper-muted mx-auto mb-2" />
            <p className="text-sm font-mono text-reaper-muted">No crawls in database yet.</p>
            <p className="text-xs font-mono text-reaper-muted/60 mt-1">
              Run a crawl job first — results will appear here.
            </p>
          </div>
        ) : (
          <div className="bg-reaper-surface border border-reaper-border rounded-lg p-3">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-xs font-mono text-reaper-muted shrink-0">Crawl</span>
              <select
                value={selectedCrawl}
                onChange={(e) => handleCrawlChange(e.target.value)}
                className="flex-1 min-w-0 bg-reaper-bg border border-reaper-border rounded px-3 py-1.5 text-sm font-mono text-white focus:border-reaper-accent outline-none"
              >
                {crawls.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.target_url} — {c.pages_crawled} pages — {c.status} — {c.started_at?.slice(0, 10) ?? '?'}
                  </option>
                ))}
              </select>
              {selectedCrawlObj && (
                <span
                  className={clsx(
                    'text-xs font-mono px-2 py-0.5 rounded border shrink-0',
                    selectedCrawlObj.status === 'completed'
                      ? 'text-reaper-success border-reaper-success/30 bg-reaper-success/10'
                      : selectedCrawlObj.status === 'running'
                      ? 'text-reaper-accent border-reaper-accent/30 bg-reaper-accent/10'
                      : 'text-reaper-muted border-reaper-border',
                  )}
                >
                  {selectedCrawlObj.status}
                </span>
              )}
            </div>
          </div>
        )}
      </AnimateIn>

      {/* Stats cards */}
      {selectedCrawl && (
        <AnimateIn delay={0.06}>
          {statsLoading ? (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
            </div>
          ) : stats ? (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <StatCard
                icon={FileText}
                label="Pages Crawled"
                value={fmtNum(stats.totals.total_pages)}
                sub={`${fmtNum(stats.totals.total_domains)} domains`}
              />
              <StatCard
                icon={Clock}
                label="Avg Response"
                value={fmtMs(stats.totals.avg_response_ms)}
              />
              <StatCard
                icon={FileText}
                label="Total Words"
                value={fmtNum(stats.totals.total_words)}
              />
              <StatCard
                icon={ExternalLink}
                label="External Links"
                value={fmtNum(stats.totals.total_external_links)}
                sub={`${fmtNum(stats.totals.total_internal_links)} internal`}
              />
            </div>
          ) : null}
        </AnimateIn>
      )}

      {/* Charts row */}
      {selectedCrawl && stats && !statsLoading && (
        <AnimateIn delay={0.09}>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {/* Status codes */}
            <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
              <div className="text-xs font-mono text-reaper-muted mb-3">Status Code Distribution</div>
              <ResponsiveContainer width="100%" height={140}>
                <BarChart data={stats.status_codes} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                  <XAxis dataKey="status_code" tick={{ fontSize: 10, fontFamily: 'monospace', fill: '#666680' }} />
                  <YAxis tick={{ fontSize: 10, fontFamily: 'monospace', fill: '#666680' }} />
                  <Tooltip
                    contentStyle={{ background: '#12121a', border: '1px solid #1e1e2e', borderRadius: 6, fontFamily: 'monospace', fontSize: 12 }}
                    labelStyle={{ color: '#fff' }}
                    itemStyle={{ color: '#00d4ff' }}
                  />
                  <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                    {stats.status_codes.map((entry, index) => (
                      <Cell key={index} fill={barFill(entry.status_code)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Top domains */}
            <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
              <div className="text-xs font-mono text-reaper-muted mb-3">Top Domains</div>
              <ResponsiveContainer width="100%" height={140}>
                <BarChart
                  data={stats.top_domains}
                  layout="vertical"
                  margin={{ top: 0, right: 0, left: 0, bottom: 0 }}
                >
                  <XAxis type="number" tick={{ fontSize: 10, fontFamily: 'monospace', fill: '#666680' }} />
                  <YAxis
                    type="category"
                    dataKey="domain"
                    width={100}
                    tick={{ fontSize: 9, fontFamily: 'monospace', fill: '#666680' }}
                    tickFormatter={(v: string) => (v.length > 14 ? v.slice(0, 13) + '…' : v)}
                  />
                  <Tooltip
                    contentStyle={{ background: '#12121a', border: '1px solid #1e1e2e', borderRadius: 6, fontFamily: 'monospace', fontSize: 12 }}
                    labelStyle={{ color: '#fff' }}
                    itemStyle={{ color: '#00d4ff' }}
                  />
                  <Bar dataKey="count" fill="#00d4ff" radius={[0, 2, 2, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </AnimateIn>
      )}

      {/* Filter bar */}
      {selectedCrawl && (
        <AnimateIn delay={0.12}>
          <div className="flex items-center gap-2 flex-wrap">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-reaper-muted" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search URL or title…"
                className="w-full bg-reaper-surface border border-reaper-border rounded pl-8 pr-3 py-1.5 text-sm font-mono text-white focus:border-reaper-accent outline-none"
              />
              {search && (
                <button
                  onClick={() => setSearch('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-reaper-muted hover:text-white"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>
            <select
              value={filterStatus}
              onChange={(e) => { setFilterStatus(e.target.value); setPage(1); }}
              className="bg-reaper-surface border border-reaper-border rounded px-3 py-1.5 text-sm font-mono text-white focus:border-reaper-accent outline-none"
            >
              <option value="">All status</option>
              <option value="200">200</option>
              <option value="301">301</option>
              <option value="302">302</option>
              <option value="404">404</option>
              <option value="500">500</option>
            </select>
          </div>
        </AnimateIn>
      )}

      {/* Pages table */}
      {selectedCrawl && (
        <AnimateIn delay={0.15}>
          <div className="bg-reaper-surface border border-reaper-border rounded-lg overflow-hidden">
            {tableLoading && !pageData ? (
              <SkeletonTable rows={8} />
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="border-b border-reaper-border bg-reaper-bg/50">
                      <tr>
                        <SortHeader col="status_code" label="Status" sort={sort} order={order} onSort={handleSort} />
                        <th className="px-3 py-2 text-left text-xs font-mono text-reaper-muted">URL</th>
                        <SortHeader col="title" label="Title" sort={sort} order={order} onSort={handleSort} />
                        <SortHeader col="response_time_ms" label="Time" sort={sort} order={order} onSort={handleSort} />
                        <SortHeader col="word_count" label="Words" sort={sort} order={order} onSort={handleSort} />
                        <SortHeader col="links_count" label="Links" sort={sort} order={order} onSort={handleSort} />
                        <SortHeader col="depth" label="Depth" sort={sort} order={order} onSort={handleSort} />
                      </tr>
                    </thead>
                    <tbody>
                      {tableLoading ? (
                        Array.from({ length: 8 }).map((_, i) => (
                          <tr key={i} className="border-b border-reaper-border/50">
                            {Array.from({ length: 7 }).map((__, j) => (
                              <td key={j} className="px-3 py-2">
                                <div className="h-3 bg-reaper-border/40 rounded animate-pulse" />
                              </td>
                            ))}
                          </tr>
                        ))
                      ) : pageData && pageData.pages.length > 0 ? (
                        pageData.pages.map((p) => (
                          <tr
                            key={p.id}
                            onClick={() => setDetailId(p.id)}
                            className="border-b border-reaper-border/50 hover:bg-reaper-border/20 cursor-pointer transition-colors"
                          >
                            <td className="px-3 py-2">
                              <span className={clsx('text-xs font-mono font-bold', statusColor(p.status_code))}>
                                {p.status_code}
                              </span>
                            </td>
                            <td className="px-3 py-2 max-w-[280px]">
                              <div className="text-xs font-mono text-reaper-accent truncate" title={p.url}>
                                {p.url}
                              </div>
                            </td>
                            <td className="px-3 py-2 max-w-[200px]">
                              <div className="text-xs font-mono text-white/80 truncate" title={p.title ?? ''}>
                                {p.title ?? p.h1 ?? <span className="text-reaper-muted italic">—</span>}
                              </div>
                            </td>
                            <td className="px-3 py-2 text-xs font-mono text-reaper-muted whitespace-nowrap">
                              {fmtMs(p.response_time_ms)}
                            </td>
                            <td className="px-3 py-2 text-xs font-mono text-reaper-muted">
                              {fmtNum(p.word_count)}
                            </td>
                            <td className="px-3 py-2 text-xs font-mono text-reaper-muted">
                              {fmtNum(p.links_count)}
                            </td>
                            <td className="px-3 py-2 text-xs font-mono text-reaper-muted">
                              {p.depth}
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={7} className="px-3 py-8 text-center text-sm font-mono text-reaper-muted">
                            No pages found
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                {pageData && pageData.total > pageData.per_page && (
                  <div className="flex items-center justify-between px-3 py-2 border-t border-reaper-border text-xs font-mono text-reaper-muted">
                    <span>
                      {(page - 1) * pageData.per_page + 1}–
                      {Math.min(page * pageData.per_page, pageData.total)} of {fmtNum(pageData.total)}
                    </span>
                    <div className="flex items-center gap-1">
                      <button
                        disabled={page <= 1}
                        onClick={() => setPage((p) => p - 1)}
                        className="p-1 disabled:opacity-30 hover:text-white transition-colors"
                      >
                        <ChevronLeft className="w-3.5 h-3.5" />
                      </button>
                      <span className="px-2">
                        {page} / {totalPages}
                      </span>
                      <button
                        disabled={page >= totalPages}
                        onClick={() => setPage((p) => p + 1)}
                        className="p-1 disabled:opacity-30 hover:text-white transition-colors"
                      >
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </AnimateIn>
      )}

      {/* Detail panel */}
      {detailId && (
        <DetailPanel pageId={detailId} onClose={() => setDetailId(null)} />
      )}
    </div>
  );
}
