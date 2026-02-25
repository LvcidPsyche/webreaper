'use client';

import { useState, useCallback, useEffect, useMemo } from 'react';
import {
  Database, Download, Search, ChevronUp, ChevronDown,
  ChevronLeft, ChevronRight, X, Globe, Clock, FileText,
  ExternalLink, RefreshCw, Shield, Code, Mail, BarChart3,
  Layers, Link2, Image, AlertTriangle, CheckCircle, Eye,
  Hash, Cpu, Zap, Type, Languages, AtSign,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, RadarChart, Radar, PolarGrid, PolarAngleAxis,
  PolarRadiusAxis, Treemap,
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
  id: string; url: string; domain: string; path: string;
  status_code: number; title: string | null; h1: string | null;
  response_time_ms: number | null; word_count: number | null;
  links_count: number | null; external_links_count: number | null;
  depth: number; scraped_at: string; seo_score?: number | null;
  readability_score?: number | null; language?: string | null;
}

interface PageList {
  total: number; page: number; per_page: number; pages: PageRow[];
}

interface Stats {
  status_codes: Array<{ status_code: number; count: number }>;
  top_domains: Array<{ domain: string; count: number }>;
  response_times: Array<{ bucket: string; count: number }>;
  depth_distribution: Array<{ depth: number; count: number }>;
  totals: {
    total_pages: number; total_domains: number;
    avg_response_ms: number | null; total_words: number | null;
    total_internal_links: number | null; total_external_links: number | null;
  };
}

interface TechData {
  total_technologies: number;
  by_category: Record<string, Array<{ category: string; name: string; domain_count: number; page_count: number; avg_confidence: number }>>;
  flat: Array<{ category: string; name: string; domain_count: number; page_count: number }>;
}

interface SEOData {
  overview: { avg_seo_score: number; pages_with_canonical: number; pages_with_lang: number; total_pages: number; avg_readability: number; avg_word_count: number };
  score_distribution: Array<{ grade: string; count: number; avg_score: number }>;
  common_issues: Array<{ issue: string; count: number }>;
  worst_pages: Array<{ id: string; url: string; title: string; seo_score: number; seo_issues: string[] }>;
}

interface ContentData {
  readability_distribution: Array<{ reading_level: string; count: number; avg_score: number }>;
  word_count_distribution: Array<{ bucket: string; count: number; avg_words: number }>;
  content_to_html_ratio: { avg_ratio: number; min_ratio: number; max_ratio: number };
  top_words: Array<{ word: string; count: number }>;
  languages: Array<{ language: string; count: number }>;
}

interface ContactData {
  emails: Array<{ email: string; domain: string; found_on: number }>;
  phones: Array<{ number: string; domain: string; found_on: number }>;
  social_profiles: Record<string, string>;
  addresses: string[];
  totals: { emails: number; phones: number; social_profiles: number; addresses: number };
}

interface PageDetail {
  id: string; url: string; canonical_url: string | null; domain: string;
  path: string; status_code: number; content_type: string | null;
  response_time_ms: number | null; title: string | null;
  meta_description: string | null; word_count: number | null;
  headings: Array<{ level: number; text: string }> | null;
  h1: string | null; h2s: string[] | null;
  links_count: number | null; external_links_count: number | null;
  images_count: number | null; depth: number; scraped_at: string;
  response_headers: Record<string, string> | null;
  // Deep fields
  meta_tags?: Record<string, string>;
  og_data?: Record<string, string>;
  twitter_card?: Record<string, string>;
  structured_data?: any[];
  technologies?: Array<{ category: string; name: string; confidence: number }>;
  emails_found?: string[];
  phone_numbers?: string[];
  social_links?: Record<string, string>;
  seo_score?: number;
  seo_issues?: string[];
  seo_passes?: string[];
  readability_score?: number;
  reading_level?: string;
  content_to_html_ratio?: number;
  top_words?: Array<{ word: string; count: number }>;
  language?: string;
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

const seoColor = (score: number) => {
  if (score >= 80) return 'text-reaper-success';
  if (score >= 60) return 'text-yellow-400';
  if (score >= 40) return 'text-reaper-warning';
  return 'text-reaper-danger';
};

const seoBg = (score: number) => {
  if (score >= 80) return 'bg-reaper-success/10 border-reaper-success/30';
  if (score >= 60) return 'bg-yellow-400/10 border-yellow-400/30';
  if (score >= 40) return 'bg-reaper-warning/10 border-reaper-warning/30';
  return 'bg-reaper-danger/10 border-reaper-danger/30';
};

const gradeColor: Record<string, string> = {
  excellent: '#00ff88', good: '#00d4ff', needs_work: '#facc15', poor: '#ffaa00', critical: '#ff4444',
};

const TECH_CATEGORY_ICONS: Record<string, string> = {
  framework: '⚛', cms: '📝', analytics: '📊', payments: '💳',
  infrastructure: '☁', server: '🖥', widget: '💬', auth: '🔐', fonts: '🔤',
};

const fmtMs = (ms: number | null) =>
  ms === null ? '—' : ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(2)}s`;

const fmtNum = (n: number | null | undefined) =>
  n === null || n === undefined ? '—' : n.toLocaleString();

const fmtPct = (n: number | null | undefined) =>
  n === null || n === undefined ? '—' : `${(n * 100).toFixed(1)}%`;

const tooltipStyle = {
  background: '#12121a', border: '1px solid #1e1e2e', borderRadius: 6, fontFamily: 'monospace', fontSize: 12,
};

// ── Tab definitions ─────────────────────────────────────────

type Tab = 'overview' | 'pages' | 'seo' | 'tech' | 'content' | 'contacts' | 'links';

const TABS: Array<{ id: Tab; label: string; icon: React.ElementType }> = [
  { id: 'overview', label: 'Overview', icon: BarChart3 },
  { id: 'pages', label: 'Pages', icon: FileText },
  { id: 'seo', label: 'SEO Audit', icon: Shield },
  { id: 'tech', label: 'Tech Stack', icon: Cpu },
  { id: 'content', label: 'Content', icon: Type },
  { id: 'contacts', label: 'Contacts', icon: AtSign },
  { id: 'links', label: 'Links', icon: Link2 },
];

// ── Stat Card ───────────────────────────────────────────────

function StatCard({ icon: Icon, label, value, sub, accent }: {
  icon: React.ElementType; label: string; value: string; sub?: string; accent?: string;
}) {
  return (
    <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4 flex items-start gap-3">
      <div className="w-8 h-8 rounded bg-reaper-accent/10 flex items-center justify-center shrink-0">
        <Icon className={clsx('w-4 h-4', accent || 'text-reaper-accent')} />
      </div>
      <div>
        <div className="text-xs font-mono text-reaper-muted">{label}</div>
        <div className={clsx('text-lg font-mono mt-0.5', accent || 'text-white')}>{value}</div>
        {sub && <div className="text-xs font-mono text-reaper-muted mt-0.5">{sub}</div>}
      </div>
    </div>
  );
}

// ── Sort Header ─────────────────────────────────────────────

function SortHeader({ col, label, sort, order, onSort }: {
  col: string; label: string; sort: string; order: string; onSort: (col: string) => void;
}) {
  const active = sort === col;
  return (
    <th className="px-3 py-2 text-left text-xs font-mono text-reaper-muted cursor-pointer hover:text-white select-none whitespace-nowrap" onClick={() => onSort(col)}>
      <span className="flex items-center gap-1">
        {label}
        {active ? (order === 'asc' ? <ChevronUp className="w-3 h-3 text-reaper-accent" /> : <ChevronDown className="w-3 h-3 text-reaper-accent" />) : <ChevronDown className="w-3 h-3 opacity-30" />}
      </span>
    </th>
  );
}

// ── Section Header ──────────────────────────────────────────

function SectionHeader({ icon: Icon, title, subtitle }: { icon: React.ElementType; title: string; subtitle?: string }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <Icon className="w-4 h-4 text-reaper-accent" />
      <span className="text-sm font-mono text-white">{title}</span>
      {subtitle && <span className="text-xs font-mono text-reaper-muted">— {subtitle}</span>}
    </div>
  );
}

// ── Deep Detail Panel ───────────────────────────────────────

function DetailPanel({ pageId, onClose }: { pageId: string; onClose: () => void }) {
  const [detail, setDetail] = useState<PageDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'meta' | 'seo' | 'tech' | 'raw'>('meta');

  useEffect(() => {
    setLoading(true);
    api.get<PageDetail>(`/api/analysis/page/${pageId}`)
      .then(d => setDetail(d))
      .catch(() => api.get<PageDetail>(`/api/data/pages/${pageId}`).then(d => setDetail(d)).catch(() => setDetail(null)))
      .finally(() => setLoading(false));
  }, [pageId]);

  if (loading) return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="flex-1 bg-black/40" onClick={onClose} />
      <div className="w-[560px] h-full bg-reaper-surface border-l border-reaper-border p-4">
        {Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)}
      </div>
    </div>
  );

  if (!detail) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="flex-1 bg-black/40" onClick={onClose} />
      <div className="w-[560px] h-full bg-reaper-surface border-l border-reaper-border overflow-y-auto flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-reaper-border sticky top-0 bg-reaper-surface z-10">
          <div className="flex items-center gap-3 min-w-0">
            <span className={clsx('text-sm font-mono font-bold', statusColor(detail.status_code))}>{detail.status_code}</span>
            {detail.seo_score != null && (
              <span className={clsx('text-xs font-mono px-2 py-0.5 rounded border', seoBg(detail.seo_score), seoColor(detail.seo_score))}>
                SEO {detail.seo_score}
              </span>
            )}
            <span className="text-xs font-mono text-reaper-muted truncate">{detail.domain}</span>
          </div>
          <button onClick={onClose} className="text-reaper-muted hover:text-white"><X className="w-4 h-4" /></button>
        </div>

        {/* URL */}
        <div className="px-4 py-2 border-b border-reaper-border/50">
          <a href={detail.url} target="_blank" rel="noopener noreferrer" className="text-xs font-mono text-reaper-accent break-all hover:underline flex items-start gap-1">
            {detail.url}<ExternalLink className="w-3 h-3 mt-0.5 shrink-0" />
          </a>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-reaper-border px-4">
          {(['meta', 'seo', 'tech', 'raw'] as const).map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className={clsx('px-3 py-2 text-xs font-mono border-b-2 transition-colors', activeTab === tab ? 'border-reaper-accent text-white' : 'border-transparent text-reaper-muted hover:text-white')}>
              {tab === 'meta' ? 'Meta & Content' : tab === 'seo' ? 'SEO' : tab === 'tech' ? 'Tech' : 'Raw Data'}
            </button>
          ))}
        </div>

        <div className="p-4 space-y-4 flex-1">
          {activeTab === 'meta' && (
            <>
              {/* Core meta */}
              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div><div className="text-reaper-muted mb-0.5">Title</div><div className="text-white">{detail.title ?? '—'}</div></div>
                <div><div className="text-reaper-muted mb-0.5">Language</div><div className="text-white">{detail.language ?? '—'}</div></div>
                <div><div className="text-reaper-muted mb-0.5">Words</div><div className="text-white">{fmtNum(detail.word_count)}</div></div>
                <div><div className="text-reaper-muted mb-0.5">Response</div><div className="text-white">{fmtMs(detail.response_time_ms)}</div></div>
                <div><div className="text-reaper-muted mb-0.5">Readability</div><div className="text-white">{detail.readability_score?.toFixed(1) ?? '—'} ({detail.reading_level ?? '—'})</div></div>
                <div><div className="text-reaper-muted mb-0.5">Content Ratio</div><div className="text-white">{detail.content_to_html_ratio ? fmtPct(detail.content_to_html_ratio) : '—'}</div></div>
              </div>

              {/* Meta description */}
              {detail.meta_description && (
                <div><div className="text-xs font-mono text-reaper-muted mb-1">Meta Description ({detail.meta_description.length} chars)</div>
                  <div className="text-xs font-mono text-white/80 bg-reaper-bg rounded p-2">{detail.meta_description}</div></div>
              )}

              {/* OG data */}
              {detail.og_data && Object.keys(detail.og_data).length > 0 && (
                <div><div className="text-xs font-mono text-reaper-muted mb-1">Open Graph</div>
                  <div className="bg-reaper-bg rounded p-2 space-y-1">
                    {Object.entries(detail.og_data).map(([k, v]) => (
                      <div key={k} className="text-xs font-mono flex gap-2"><span className="text-reaper-accent shrink-0">og:{k}</span><span className="text-white/70 break-all">{v}</span></div>
                    ))}
                  </div></div>
              )}

              {/* Headings */}
              {detail.headings && detail.headings.length > 0 && (
                <div><div className="text-xs font-mono text-reaper-muted mb-1">Heading Structure ({detail.headings.length})</div>
                  <div className="space-y-1 max-h-48 overflow-y-auto">
                    {detail.headings.map((h, i) => (
                      <div key={i} className="text-xs font-mono text-white/70 flex items-start gap-2" style={{ paddingLeft: `${(h.level - 1) * 12}px` }}>
                        <span className="text-reaper-accent shrink-0 w-5">H{h.level}</span>{h.text}
                      </div>
                    ))}
                  </div></div>
              )}

              {/* Contact info */}
              {((detail.emails_found?.length ?? 0) > 0 || (detail.phone_numbers?.length ?? 0) > 0) && (
                <div><div className="text-xs font-mono text-reaper-muted mb-1">Contact Info</div>
                  <div className="bg-reaper-bg rounded p-2 space-y-1">
                    {detail.emails_found?.map(e => <div key={e} className="text-xs font-mono text-reaper-accent">{e}</div>)}
                    {detail.phone_numbers?.map(p => <div key={p} className="text-xs font-mono text-white/70">{p}</div>)}
                  </div></div>
              )}

              {/* Top words */}
              {detail.top_words && detail.top_words.length > 0 && (
                <div><div className="text-xs font-mono text-reaper-muted mb-1">Top Keywords</div>
                  <div className="flex flex-wrap gap-1">
                    {detail.top_words.slice(0, 15).map(w => (
                      <span key={w.word} className="text-xs font-mono px-2 py-0.5 rounded bg-reaper-accent/10 text-reaper-accent border border-reaper-accent/20">
                        {w.word} <span className="text-reaper-muted">({w.count})</span>
                      </span>
                    ))}
                  </div></div>
              )}
            </>
          )}

          {activeTab === 'seo' && (
            <>
              {detail.seo_score != null && (
                <div className={clsx('text-center py-4 rounded-lg border', seoBg(detail.seo_score))}>
                  <div className={clsx('text-4xl font-mono font-bold', seoColor(detail.seo_score))}>{detail.seo_score}</div>
                  <div className="text-xs font-mono text-reaper-muted mt-1">SEO Score</div>
                </div>
              )}
              {detail.seo_passes && detail.seo_passes.length > 0 && (
                <div><div className="text-xs font-mono text-reaper-success mb-1 flex items-center gap-1"><CheckCircle className="w-3 h-3" /> Passing ({detail.seo_passes.length})</div>
                  <div className="space-y-1">{detail.seo_passes.map((p, i) => <div key={i} className="text-xs font-mono text-white/70 pl-4">✓ {p}</div>)}</div></div>
              )}
              {detail.seo_issues && detail.seo_issues.length > 0 && (
                <div><div className="text-xs font-mono text-reaper-warning mb-1 flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> Issues ({detail.seo_issues.length})</div>
                  <div className="space-y-1">{detail.seo_issues.map((p, i) => <div key={i} className="text-xs font-mono text-white/70 pl-4">✗ {p}</div>)}</div></div>
              )}
              {detail.structured_data && detail.structured_data.length > 0 && (
                <div><div className="text-xs font-mono text-reaper-muted mb-1">Structured Data ({detail.structured_data.length} blocks)</div>
                  <div className="bg-reaper-bg rounded p-2 max-h-48 overflow-y-auto">
                    {detail.structured_data.map((sd, i) => (
                      <div key={i} className="text-xs font-mono text-white/70 mb-2">
                        <span className="text-reaper-accent">@type: {sd['@type'] ?? 'unknown'}</span>
                        <pre className="text-[10px] mt-1 text-white/50 overflow-x-auto">{JSON.stringify(sd, null, 2).slice(0, 500)}</pre>
                      </div>
                    ))}
                  </div></div>
              )}
            </>
          )}

          {activeTab === 'tech' && (
            <>
              {detail.technologies && detail.technologies.length > 0 ? (
                <div className="space-y-3">
                  {Object.entries(
                    detail.technologies.reduce((acc, t) => {
                      if (!acc[t.category]) acc[t.category] = [];
                      acc[t.category].push(t);
                      return acc;
                    }, {} as Record<string, typeof detail.technologies>)
                  ).map(([cat, techs]) => (
                    <div key={cat}>
                      <div className="text-xs font-mono text-reaper-muted mb-1 capitalize">{TECH_CATEGORY_ICONS[cat] ?? '🔧'} {cat}</div>
                      <div className="flex flex-wrap gap-1">
                        {techs.map(t => (
                          <span key={t.name} className="text-xs font-mono px-2 py-1 rounded bg-reaper-bg border border-reaper-border text-white">
                            {t.name} <span className="text-reaper-muted">({Math.round(t.confidence * 100)}%)</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-xs font-mono text-reaper-muted text-center py-8">No technologies detected</div>
              )}

              {detail.social_links && Object.keys(detail.social_links).length > 0 && (
                <div><div className="text-xs font-mono text-reaper-muted mb-1">Social Links</div>
                  <div className="space-y-1">
                    {Object.entries(detail.social_links).map(([platform, url]) => (
                      <a key={platform} href={url} target="_blank" rel="noopener noreferrer" className="text-xs font-mono text-reaper-accent hover:underline block">
                        {platform}: {url}
                      </a>
                    ))}
                  </div></div>
              )}
            </>
          )}

          {activeTab === 'raw' && (
            <div className="bg-reaper-bg rounded p-3 max-h-[70vh] overflow-auto">
              <pre className="text-[10px] font-mono text-white/60 whitespace-pre-wrap">
                {JSON.stringify(detail, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Overview Tab ─────────────────────────────────────────────

function OverviewTab({ crawlId, stats, statsLoading }: { crawlId: string; stats: Stats | null; statsLoading: boolean }) {
  if (statsLoading) return <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">{Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)}</div>;
  if (!stats) return null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard icon={FileText} label="Pages Crawled" value={fmtNum(stats.totals.total_pages)} sub={`${fmtNum(stats.totals.total_domains)} domains`} />
        <StatCard icon={Clock} label="Avg Response" value={fmtMs(stats.totals.avg_response_ms)} />
        <StatCard icon={Hash} label="Total Words" value={fmtNum(stats.totals.total_words)} />
        <StatCard icon={ExternalLink} label="External Links" value={fmtNum(stats.totals.total_external_links)} sub={`${fmtNum(stats.totals.total_internal_links)} internal`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
          <div className="text-xs font-mono text-reaper-muted mb-3">Status Code Distribution</div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={stats.status_codes} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="status_code" tick={{ fontSize: 10, fontFamily: 'monospace', fill: '#666680' }} />
              <YAxis tick={{ fontSize: 10, fontFamily: 'monospace', fill: '#666680' }} />
              <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#fff' }} />
              <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                {stats.status_codes.map((entry, i) => <Cell key={i} fill={barFill(entry.status_code)} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
          <div className="text-xs font-mono text-reaper-muted mb-3">Response Time Distribution</div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={stats.response_times} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="bucket" tick={{ fontSize: 9, fontFamily: 'monospace', fill: '#666680' }} />
              <YAxis tick={{ fontSize: 10, fontFamily: 'monospace', fill: '#666680' }} />
              <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#fff' }} />
              <Bar dataKey="count" fill="#00d4ff" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
          <div className="text-xs font-mono text-reaper-muted mb-3">Top Domains</div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={stats.top_domains} layout="vertical" margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
              <XAxis type="number" tick={{ fontSize: 10, fontFamily: 'monospace', fill: '#666680' }} />
              <YAxis type="category" dataKey="domain" width={110} tick={{ fontSize: 9, fontFamily: 'monospace', fill: '#666680' }} tickFormatter={(v: string) => v.length > 14 ? v.slice(0, 13) + '…' : v} />
              <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#fff' }} />
              <Bar dataKey="count" fill="#00d4ff" radius={[0, 2, 2, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
          <div className="text-xs font-mono text-reaper-muted mb-3">Crawl Depth</div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={stats.depth_distribution} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="depth" tick={{ fontSize: 10, fontFamily: 'monospace', fill: '#666680' }} />
              <YAxis tick={{ fontSize: 10, fontFamily: 'monospace', fill: '#666680' }} />
              <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#fff' }} />
              <Bar dataKey="count" fill="#a855f7" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

// ── SEO Tab ─────────────────────────────────────────────────

function SEOTab({ crawlId }: { crawlId: string }) {
  const [data, setData] = useState<SEOData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get<SEOData>(`/api/analysis/seo/${crawlId}`).then(setData).catch(() => setData(null)).finally(() => setLoading(false));
  }, [crawlId]);

  if (loading) return <div className="space-y-3">{Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}</div>;
  if (!data) return <div className="text-sm font-mono text-reaper-muted text-center py-8">No SEO data available. Run a crawl first.</div>;

  return (
    <div className="space-y-4">
      {/* Score overview */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard icon={Shield} label="Avg SEO Score" value={`${data.overview.avg_seo_score ?? '—'}`}
          accent={data.overview.avg_seo_score >= 70 ? 'text-reaper-success' : data.overview.avg_seo_score >= 50 ? 'text-yellow-400' : 'text-reaper-danger'} />
        <StatCard icon={CheckCircle} label="Has Canonical" value={`${data.overview.pages_with_canonical}`} sub={`of ${data.overview.total_pages} pages`} />
        <StatCard icon={Languages} label="Has Language" value={`${data.overview.pages_with_lang}`} sub={`of ${data.overview.total_pages} pages`} />
        <StatCard icon={FileText} label="Avg Words" value={`${data.overview.avg_word_count ?? '—'}`} sub={`Readability: ${data.overview.avg_readability ?? '—'}`} />
      </div>

      {/* Score distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
          <div className="text-xs font-mono text-reaper-muted mb-3">Score Distribution</div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={data.score_distribution} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="grade" tick={{ fontSize: 10, fontFamily: 'monospace', fill: '#666680' }} />
              <YAxis tick={{ fontSize: 10, fontFamily: 'monospace', fill: '#666680' }} />
              <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#fff' }} />
              <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                {data.score_distribution.map((e, i) => <Cell key={i} fill={gradeColor[e.grade] ?? '#666'} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
          <div className="text-xs font-mono text-reaper-muted mb-3">Most Common Issues</div>
          <div className="space-y-2 max-h-[200px] overflow-y-auto">
            {data.common_issues.slice(0, 10).map((issue, i) => (
              <div key={i} className="flex items-center justify-between text-xs font-mono">
                <span className="text-white/80 truncate mr-2">{issue.issue}</span>
                <span className="text-reaper-warning shrink-0 bg-reaper-warning/10 px-2 py-0.5 rounded">{issue.count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Worst pages */}
      {data.worst_pages.length > 0 && (
        <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
          <div className="text-xs font-mono text-reaper-muted mb-3">Lowest Scoring Pages</div>
          <div className="space-y-2">
            {data.worst_pages.map(p => (
              <div key={p.id} className="flex items-center gap-3 text-xs font-mono">
                <span className={clsx('font-bold w-8 text-right', seoColor(p.seo_score))}>{p.seo_score}</span>
                <span className="text-reaper-accent truncate flex-1" title={p.url}>{p.url}</span>
                <span className="text-reaper-muted shrink-0">{p.seo_issues?.length ?? 0} issues</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Tech Tab ────────────────────────────────────────────────

function TechTab({ crawlId }: { crawlId: string }) {
  const [data, setData] = useState<TechData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get<TechData>(`/api/analysis/technologies/${crawlId}`).then(setData).catch(() => setData(null)).finally(() => setLoading(false));
  }, [crawlId]);

  if (loading) return <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}</div>;
  if (!data || data.total_technologies === 0) return <div className="text-sm font-mono text-reaper-muted text-center py-8">No technologies detected. Run a crawl first.</div>;

  return (
    <div className="space-y-4">
      <StatCard icon={Cpu} label="Technologies Detected" value={`${data.total_technologies}`} sub={`across ${Object.keys(data.by_category).length} categories`} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {Object.entries(data.by_category).map(([category, techs]) => (
          <div key={category} className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
            <div className="text-xs font-mono text-reaper-muted mb-3 capitalize flex items-center gap-2">
              <span>{TECH_CATEGORY_ICONS[category] ?? '🔧'}</span>
              {category}
              <span className="text-reaper-accent">({techs.length})</span>
            </div>
            <div className="space-y-2">
              {techs.map(tech => (
                <div key={tech.name} className="flex items-center justify-between text-xs font-mono">
                  <span className="text-white">{tech.name}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-reaper-muted">{tech.page_count} pages</span>
                    <span className="text-reaper-accent">{tech.domain_count} domains</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Content Tab ─────────────────────────────────────────────

function ContentTab({ crawlId }: { crawlId: string }) {
  const [data, setData] = useState<ContentData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get<ContentData>(`/api/analysis/content/${crawlId}`).then(setData).catch(() => setData(null)).finally(() => setLoading(false));
  }, [crawlId]);

  if (loading) return <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}</div>;
  if (!data) return <div className="text-sm font-mono text-reaper-muted text-center py-8">No content analysis data. Run a crawl first.</div>;

  const maxWordCount = Math.max(...(data.top_words.map(w => w.count) || [1]));

  return (
    <div className="space-y-4">
      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
        <StatCard icon={Type} label="Avg Content Ratio" value={data.content_to_html_ratio.avg_ratio ? fmtPct(data.content_to_html_ratio.avg_ratio) : '—'} />
        <StatCard icon={Languages} label="Languages" value={`${data.languages.length}`} sub={data.languages[0]?.language ?? '—'} />
        <StatCard icon={FileText} label="Word Count Range" value={`${data.word_count_distribution.length} buckets`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* Word count distribution */}
        <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
          <div className="text-xs font-mono text-reaper-muted mb-3">Word Count Distribution</div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={data.word_count_distribution} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="bucket" tick={{ fontSize: 8, fontFamily: 'monospace', fill: '#666680' }} />
              <YAxis tick={{ fontSize: 10, fontFamily: 'monospace', fill: '#666680' }} />
              <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#fff' }} />
              <Bar dataKey="count" fill="#a855f7" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Readability distribution */}
        <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
          <div className="text-xs font-mono text-reaper-muted mb-3">Readability Levels</div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={data.readability_distribution} layout="vertical" margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
              <XAxis type="number" tick={{ fontSize: 10, fontFamily: 'monospace', fill: '#666680' }} />
              <YAxis type="category" dataKey="reading_level" width={80} tick={{ fontSize: 8, fontFamily: 'monospace', fill: '#666680' }} />
              <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#fff' }} />
              <Bar dataKey="count" fill="#00d4ff" radius={[0, 2, 2, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Word cloud (bar-based) */}
      {data.top_words.length > 0 && (
        <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
          <div className="text-xs font-mono text-reaper-muted mb-3">Top Keywords Across All Pages</div>
          <div className="space-y-1">
            {data.top_words.slice(0, 20).map(w => (
              <div key={w.word} className="flex items-center gap-2 text-xs font-mono">
                <span className="text-white w-24 text-right truncate">{w.word}</span>
                <div className="flex-1 h-4 bg-reaper-bg rounded overflow-hidden">
                  <div className="h-full bg-reaper-accent/40 rounded" style={{ width: `${(w.count / maxWordCount) * 100}%` }} />
                </div>
                <span className="text-reaper-muted w-10 text-right">{w.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Contacts Tab ────────────────────────────────────────────

function ContactsTab({ crawlId }: { crawlId: string }) {
  const [data, setData] = useState<ContactData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get<ContactData>(`/api/analysis/contacts/${crawlId}`).then(setData).catch(() => setData(null)).finally(() => setLoading(false));
  }, [crawlId]);

  if (loading) return <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}</div>;
  if (!data) return <div className="text-sm font-mono text-reaper-muted text-center py-8">No contact data. Run a crawl first.</div>;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard icon={Mail} label="Emails" value={`${data.totals.emails}`} />
        <StatCard icon={Hash} label="Phone Numbers" value={`${data.totals.phones}`} />
        <StatCard icon={Globe} label="Social Profiles" value={`${data.totals.social_profiles}`} />
        <StatCard icon={FileText} label="Addresses" value={`${data.totals.addresses}`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* Emails */}
        {data.emails.length > 0 && (
          <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
            <SectionHeader icon={Mail} title="Emails" subtitle={`${data.emails.length} found`} />
            <div className="space-y-1.5 max-h-64 overflow-y-auto">
              {data.emails.map(e => (
                <div key={e.email} className="flex items-center justify-between text-xs font-mono">
                  <span className="text-reaper-accent">{e.email}</span>
                  <span className="text-reaper-muted">{e.domain} ({e.found_on} pages)</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Social profiles */}
        {Object.keys(data.social_profiles).length > 0 && (
          <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
            <SectionHeader icon={Globe} title="Social Profiles" />
            <div className="space-y-1.5">
              {Object.entries(data.social_profiles).map(([platform, url]) => (
                <div key={platform} className="flex items-center gap-2 text-xs font-mono">
                  <span className="text-white capitalize w-20">{platform}</span>
                  <a href={url} target="_blank" rel="noopener noreferrer" className="text-reaper-accent hover:underline truncate">{url}</a>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Phones */}
        {data.phones.length > 0 && (
          <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
            <SectionHeader icon={Hash} title="Phone Numbers" />
            <div className="space-y-1.5">
              {data.phones.map(p => (
                <div key={p.number} className="flex items-center justify-between text-xs font-mono">
                  <span className="text-white">{p.number}</span>
                  <span className="text-reaper-muted">{p.domain}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Addresses */}
        {data.addresses.length > 0 && (
          <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
            <SectionHeader icon={FileText} title="Physical Addresses" />
            <div className="space-y-1.5">
              {data.addresses.map((a, i) => <div key={i} className="text-xs font-mono text-white/80">{a}</div>)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Pages Table Tab ─────────────────────────────────────────

function PagesTab({ crawlId }: { crawlId: string }) {
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [sort, setSort] = useState('scraped_at');
  const [order, setOrder] = useState('desc');
  const [page, setPage] = useState(1);
  const [pageData, setPageData] = useState<PageList | null>(null);
  const [tableLoading, setTableLoading] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => { setDebouncedSearch(search); setPage(1); }, 350);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    if (!crawlId) return;
    setTableLoading(true);
    const params = new URLSearchParams({ crawl_id: crawlId, sort, order, page: String(page), per_page: '50' });
    if (debouncedSearch) params.set('search', debouncedSearch);
    if (filterStatus) params.set('status_code', filterStatus);
    api.get<PageList>(`/api/data/pages?${params}`).then(setPageData).catch(() => setPageData(null)).finally(() => setTableLoading(false));
  }, [crawlId, sort, order, page, debouncedSearch, filterStatus]);

  const handleSort = useCallback((col: string) => {
    if (sort === col) setOrder(o => o === 'asc' ? 'desc' : 'asc');
    else { setSort(col); setOrder('desc'); }
    setPage(1);
  }, [sort]);

  const totalPages = pageData ? Math.ceil(pageData.total / pageData.per_page) : 1;

  return (
    <div className="space-y-3">
      {/* Filter bar */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-reaper-muted" />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search URL or title…"
            className="w-full bg-reaper-surface border border-reaper-border rounded pl-8 pr-3 py-1.5 text-sm font-mono text-white focus:border-reaper-accent outline-none" />
          {search && <button onClick={() => setSearch('')} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-reaper-muted hover:text-white"><X className="w-3 h-3" /></button>}
        </div>
        <select value={filterStatus} onChange={e => { setFilterStatus(e.target.value); setPage(1); }}
          className="bg-reaper-surface border border-reaper-border rounded px-3 py-1.5 text-sm font-mono text-white focus:border-reaper-accent outline-none">
          <option value="">All status</option>
          <option value="200">200</option><option value="301">301</option><option value="302">302</option>
          <option value="404">404</option><option value="500">500</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-reaper-surface border border-reaper-border rounded-lg overflow-hidden">
        {tableLoading && !pageData ? <SkeletonTable rows={8} /> : (
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
                  {tableLoading ? Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="border-b border-reaper-border/50">{Array.from({ length: 7 }).map((__, j) => (
                      <td key={j} className="px-3 py-2"><div className="h-3 bg-reaper-border/40 rounded animate-pulse" /></td>
                    ))}</tr>
                  )) : pageData && pageData.pages.length > 0 ? pageData.pages.map(p => (
                    <tr key={p.id} onClick={() => setDetailId(p.id)} className="border-b border-reaper-border/50 hover:bg-reaper-border/20 cursor-pointer transition-colors">
                      <td className="px-3 py-2"><span className={clsx('text-xs font-mono font-bold', statusColor(p.status_code))}>{p.status_code}</span></td>
                      <td className="px-3 py-2 max-w-[280px]"><div className="text-xs font-mono text-reaper-accent truncate" title={p.url}>{p.url}</div></td>
                      <td className="px-3 py-2 max-w-[200px]"><div className="text-xs font-mono text-white/80 truncate">{p.title ?? p.h1 ?? <span className="text-reaper-muted italic">—</span>}</div></td>
                      <td className="px-3 py-2 text-xs font-mono text-reaper-muted whitespace-nowrap">{fmtMs(p.response_time_ms)}</td>
                      <td className="px-3 py-2 text-xs font-mono text-reaper-muted">{fmtNum(p.word_count)}</td>
                      <td className="px-3 py-2 text-xs font-mono text-reaper-muted">{fmtNum(p.links_count)}</td>
                      <td className="px-3 py-2 text-xs font-mono text-reaper-muted">{p.depth}</td>
                    </tr>
                  )) : (
                    <tr><td colSpan={7} className="px-3 py-8 text-center text-sm font-mono text-reaper-muted">No pages found</td></tr>
                  )}
                </tbody>
              </table>
            </div>

            {pageData && pageData.total > pageData.per_page && (
              <div className="flex items-center justify-between px-3 py-2 border-t border-reaper-border text-xs font-mono text-reaper-muted">
                <span>{(page - 1) * pageData.per_page + 1}–{Math.min(page * pageData.per_page, pageData.total)} of {fmtNum(pageData.total)}</span>
                <div className="flex items-center gap-1">
                  <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} className="p-1 disabled:opacity-30 hover:text-white"><ChevronLeft className="w-3.5 h-3.5" /></button>
                  <span className="px-2">{page} / {totalPages}</span>
                  <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)} className="p-1 disabled:opacity-30 hover:text-white"><ChevronRight className="w-3.5 h-3.5" /></button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {detailId && <DetailPanel pageId={detailId} onClose={() => setDetailId(null)} />}
    </div>
  );
}

// ── Links Tab ───────────────────────────────────────────────

function LinksTab({ crawlId }: { crawlId: string }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get(`/api/analysis/links/${crawlId}`).then(setData).catch(() => setData(null)).finally(() => setLoading(false));
  }, [crawlId]);

  if (loading) return <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}</div>;
  if (!data) return <div className="text-sm font-mono text-reaper-muted text-center py-8">No link data available.</div>;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard icon={Link2} label="Total Links" value={fmtNum(data.summary?.total_links)} />
        <StatCard icon={ExternalLink} label="External" value={fmtNum(data.summary?.external_links)} />
        <StatCard icon={AlertTriangle} label="Broken" value={fmtNum(data.summary?.broken_links)} accent={data.summary?.broken_links > 0 ? 'text-reaper-danger' : undefined} />
        <StatCard icon={Globe} label="Unique Domains" value={fmtNum(data.summary?.unique_domains)} />
      </div>

      {data.top_external_domains?.length > 0 && (
        <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
          <div className="text-xs font-mono text-reaper-muted mb-3">Top External Domains</div>
          <ResponsiveContainer width="100%" height={Math.min(data.top_external_domains.length * 28 + 20, 300)}>
            <BarChart data={data.top_external_domains.slice(0, 10)} layout="vertical" margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
              <XAxis type="number" tick={{ fontSize: 10, fontFamily: 'monospace', fill: '#666680' }} />
              <YAxis type="category" dataKey="target_domain" width={160} tick={{ fontSize: 9, fontFamily: 'monospace', fill: '#666680' }} tickFormatter={(v: string) => v.length > 20 ? v.slice(0, 19) + '…' : v} />
              <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: '#fff' }} />
              <Bar dataKey="link_count" fill="#00d4ff" radius={[0, 2, 2, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

// ── Main Page ───────────────────────────────────────────────

export default function DataPage() {
  const { data: crawls, loading: crawlsLoading, refetch: refetchCrawls } = useApi<Crawl[]>('/api/data/crawls');
  const [selectedCrawl, setSelectedCrawl] = useState<string>('');
  const [stats, setStats] = useState<Stats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>('overview');

  useEffect(() => {
    if (crawls && crawls.length > 0 && !selectedCrawl) setSelectedCrawl(crawls[0].id);
  }, [crawls, selectedCrawl]);

  useEffect(() => {
    if (!selectedCrawl) return;
    setStatsLoading(true);
    api.get<Stats>(`/api/data/stats/${selectedCrawl}`).then(setStats).catch(() => setStats(null)).finally(() => setStatsLoading(false));
  }, [selectedCrawl]);

  const handleCrawlChange = (id: string) => {
    setSelectedCrawl(id);
    setStats(null);
  };

  const selectedCrawlObj = crawls?.find(c => c.id === selectedCrawl);
  const exportUrl = (fmt: string) => selectedCrawl ? `${API_BASE_URL}/api/data/export/${selectedCrawl}?fmt=${fmt}` : '#';

  return (
    <div className="space-y-4">
      {/* Header */}
      <AnimateIn className="flex items-center justify-between">
        <h1 className="text-sm font-mono text-white flex items-center gap-2">
          <Database className="w-4 h-4 text-reaper-accent" />
          Data Explorer
        </h1>
        <div className="flex items-center gap-2">
          <button onClick={refetchCrawls} className="p-1.5 text-reaper-muted hover:text-white transition-colors" title="Refresh"><RefreshCw className="w-3.5 h-3.5" /></button>
          {selectedCrawl && (
            <>
              <a href={exportUrl('csv')} download className="flex items-center gap-1.5 px-3 py-1.5 bg-reaper-surface border border-reaper-border rounded text-xs font-mono text-reaper-muted hover:text-white hover:border-reaper-accent/30 transition-colors">
                <Download className="w-3 h-3" /> CSV
              </a>
              <a href={exportUrl('json')} download className="flex items-center gap-1.5 px-3 py-1.5 bg-reaper-surface border border-reaper-border rounded text-xs font-mono text-reaper-muted hover:text-white hover:border-reaper-accent/30 transition-colors">
                <Download className="w-3 h-3" /> JSON
              </a>
            </>
          )}
        </div>
      </AnimateIn>

      {/* Crawl selector */}
      <AnimateIn delay={0.03}>
        {crawlsLoading ? <SkeletonCard /> : !crawls || crawls.length === 0 ? (
          <div className="bg-reaper-surface border border-reaper-border rounded-lg p-6 text-center">
            <Database className="w-8 h-8 text-reaper-muted mx-auto mb-2" />
            <p className="text-sm font-mono text-reaper-muted">No crawls in database yet.</p>
            <p className="text-xs font-mono text-reaper-muted/60 mt-1">Run a crawl job first — results will appear here.</p>
          </div>
        ) : (
          <div className="bg-reaper-surface border border-reaper-border rounded-lg p-3">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-xs font-mono text-reaper-muted shrink-0">Crawl</span>
              <select value={selectedCrawl} onChange={e => handleCrawlChange(e.target.value)}
                className="flex-1 min-w-0 bg-reaper-bg border border-reaper-border rounded px-3 py-1.5 text-sm font-mono text-white focus:border-reaper-accent outline-none">
                {crawls.map(c => (
                  <option key={c.id} value={c.id}>{c.target_url} — {c.pages_crawled} pages — {c.status} — {c.started_at?.slice(0, 10) ?? '?'}</option>
                ))}
              </select>
              {selectedCrawlObj && (
                <span className={clsx('text-xs font-mono px-2 py-0.5 rounded border shrink-0',
                  selectedCrawlObj.status === 'completed' ? 'text-reaper-success border-reaper-success/30 bg-reaper-success/10' :
                  selectedCrawlObj.status === 'running' ? 'text-reaper-accent border-reaper-accent/30 bg-reaper-accent/10' :
                  'text-reaper-muted border-reaper-border')}>
                  {selectedCrawlObj.status}
                </span>
              )}
            </div>
          </div>
        )}
      </AnimateIn>

      {/* Tab navigation */}
      {selectedCrawl && (
        <AnimateIn delay={0.06}>
          <div className="flex gap-1 bg-reaper-surface border border-reaper-border rounded-lg p-1 overflow-x-auto">
            {TABS.map(tab => (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                className={clsx('flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-mono transition-all whitespace-nowrap',
                  activeTab === tab.id ? 'bg-reaper-accent/10 text-reaper-accent border border-reaper-accent/30' : 'text-reaper-muted hover:text-white hover:bg-reaper-border/30 border border-transparent')}>
                <tab.icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            ))}
          </div>
        </AnimateIn>
      )}

      {/* Tab content */}
      {selectedCrawl && (
        <AnimateIn delay={0.09} key={activeTab}>
          {activeTab === 'overview' && <OverviewTab crawlId={selectedCrawl} stats={stats} statsLoading={statsLoading} />}
          {activeTab === 'pages' && <PagesTab crawlId={selectedCrawl} />}
          {activeTab === 'seo' && <SEOTab crawlId={selectedCrawl} />}
          {activeTab === 'tech' && <TechTab crawlId={selectedCrawl} />}
          {activeTab === 'content' && <ContentTab crawlId={selectedCrawl} />}
          {activeTab === 'contacts' && <ContactsTab crawlId={selectedCrawl} />}
          {activeTab === 'links' && <LinksTab crawlId={selectedCrawl} />}
        </AnimateIn>
      )}
    </div>
  );
}
