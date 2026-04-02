'use client';

import { useEffect, useState } from 'react';
import {
  Download,
  ExternalLink,
  FolderOpen,
  Globe,
  Plus,
  RefreshCw,
  Save,
  Search,
  Sparkles,
  Star,
} from 'lucide-react';
import { clsx } from 'clsx';
import { AnimateIn } from '@/components/shared/animate-in';
import { SkeletonCard, SkeletonTable } from '@/components/shared/skeleton';
import api from '@/lib/api';
import { API_BASE_URL } from '@/lib/constants';
import type {
  Workspace,
  WorkspaceLibraryItem,
  WorkspaceLibraryListResponse,
  WorkspaceLibrarySummaryResponse,
} from '@/lib/types';

const CATEGORY_OPTIONS = [
  'api',
  'article',
  'careers',
  'company',
  'contact',
  'documentation',
  'download',
  'general',
  'landing',
  'legal',
  'pricing',
  'product',
  'research',
];

const panelCls = 'bg-reaper-surface border border-reaper-border rounded-lg';
const inputCls = 'mt-1 w-full bg-reaper-bg border border-reaper-border rounded px-3 py-2 text-sm font-mono text-white placeholder:text-reaper-muted/50 focus:border-reaper-accent outline-none';
const buttonCls = 'inline-flex items-center gap-2 rounded border px-3 py-2 text-xs font-mono transition-colors';

type LibraryFilters = {
  search: string;
  category: string;
  domain: string;
  starredOnly: boolean;
};

function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded border border-reaper-border bg-black/20 p-3">
      <div className="text-[10px] font-mono uppercase tracking-widest text-reaper-muted">{label}</div>
      <div className="mt-2 text-xl font-mono text-white">{value}</div>
      {hint ? <div className="mt-1 text-[11px] font-mono text-reaper-muted">{hint}</div> : null}
    </div>
  );
}

export default function WorkspacesPage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState('');
  const [summary, setSummary] = useState<WorkspaceLibrarySummaryResponse | null>(null);
  const [library, setLibrary] = useState<WorkspaceLibraryListResponse | null>(null);
  const [selectedItemId, setSelectedItemId] = useState('');
  const [filters, setFilters] = useState<LibraryFilters>({
    search: '',
    category: '',
    domain: '',
    starredOnly: false,
  });
  const [workspaceForm, setWorkspaceForm] = useState({ name: '', description: '' });
  const [crawlForm, setCrawlForm] = useState({ url: '', depth: 2, concurrency: 12, browser_render: true });
  const [editor, setEditor] = useState({ category: '', folder: '', labels: '', notes: '', starred: false });
  const [loadingWorkspaces, setLoadingWorkspaces] = useState(true);
  const [loadingLibrary, setLoadingLibrary] = useState(false);
  const [creatingWorkspace, setCreatingWorkspace] = useState(false);
  const [startingCrawl, setStartingCrawl] = useState(false);
  const [savingItem, setSavingItem] = useState(false);
  const [autoFiling, setAutoFiling] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedItem = library?.items.find((item) => item.page_id === selectedItemId) ?? null;

  function buildLibraryPath(workspaceId: string, nextFilters: LibraryFilters) {
    const params = new URLSearchParams();
    if (nextFilters.search.trim()) params.set('search', nextFilters.search.trim());
    if (nextFilters.category.trim()) params.set('category', nextFilters.category.trim());
    if (nextFilters.domain.trim()) params.set('domain', nextFilters.domain.trim());
    if (nextFilters.starredOnly) params.set('starred', 'true');
    return `/api/workspaces/${workspaceId}/library/items?${params.toString()}`;
  }

  async function loadWorkspaces(preferredWorkspaceId?: string) {
    setLoadingWorkspaces(true);
    setError(null);
    try {
      const rows = await api.get<Workspace[]>('/api/workspaces');
      setWorkspaces(rows);
      const nextWorkspaceId = preferredWorkspaceId || selectedWorkspaceId || rows[0]?.id || '';
      setSelectedWorkspaceId(nextWorkspaceId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workspaces');
    } finally {
      setLoadingWorkspaces(false);
    }
  }

  async function loadWorkspaceLibrary(workspaceId: string, nextFilters: LibraryFilters = filters) {
    setLoadingLibrary(true);
    setError(null);
    try {
      const [summaryPayload, libraryPayload] = await Promise.all([
        api.get<WorkspaceLibrarySummaryResponse>(`/api/workspaces/${workspaceId}/library/summary`),
        api.get<WorkspaceLibraryListResponse>(buildLibraryPath(workspaceId, nextFilters)),
      ]);
      setSummary(summaryPayload);
      setLibrary(libraryPayload);
      if (libraryPayload.items.length === 0) {
        setSelectedItemId('');
        return;
      }
      const stillExists = libraryPayload.items.some((item) => item.page_id === selectedItemId);
      setSelectedItemId(stillExists ? selectedItemId : libraryPayload.items[0].page_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workspace library');
    } finally {
      setLoadingLibrary(false);
    }
  }

  async function handleCreateWorkspace(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspaceForm.name.trim()) return;
    setCreatingWorkspace(true);
    setError(null);
    setMessage(null);
    try {
      const workspace = await api.post<Workspace>('/api/workspaces', {
        name: workspaceForm.name.trim(),
        description: workspaceForm.description.trim() || null,
        tags: ['scraper'],
        risk_policy: {},
      });
      setWorkspaceForm({ name: '', description: '' });
      setMessage(`Workspace ready: ${workspace.name}`);
      await loadWorkspaces(workspace.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create workspace');
    } finally {
      setCreatingWorkspace(false);
    }
  }

  async function handleStartWorkspaceCrawl(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedWorkspaceId || !crawlForm.url.trim()) return;
    setStartingCrawl(true);
    setError(null);
    setMessage(null);
    try {
      await api.post('/api/jobs', {
        url: crawlForm.url.trim(),
        depth: crawlForm.depth,
        concurrency: crawlForm.concurrency,
        browser_render: crawlForm.browser_render,
        workspace_id: selectedWorkspaceId,
      });
      setMessage('Workspace crawl started. Watch Jobs for live progress.');
      setCrawlForm((current) => ({ ...current, url: '' }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start workspace crawl');
    } finally {
      setStartingCrawl(false);
    }
  }

  async function handleAutoFile() {
    if (!selectedWorkspaceId) return;
    setAutoFiling(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api.post<{ created: number; updated: number; skipped: number }>(
        `/api/workspaces/${selectedWorkspaceId}/library/auto-file`,
        {},
      );
      setMessage(
        `Auto-filed library. Created ${result.created}, updated ${result.updated}, skipped ${result.skipped}.`,
      );
      await loadWorkspaceLibrary(selectedWorkspaceId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to auto-file workspace');
    } finally {
      setAutoFiling(false);
    }
  }

  async function handleSaveSelectedItem(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedWorkspaceId || !selectedItem) return;
    setSavingItem(true);
    setError(null);
    setMessage(null);
    try {
      await api.put(`/api/workspaces/${selectedWorkspaceId}/library/pages/${selectedItem.page_id}`, {
        category: editor.category.trim() || null,
        folder: editor.folder.trim() || null,
        labels: editor.labels.split(',').map((label) => label.trim()).filter(Boolean),
        notes: editor.notes.trim() || null,
        starred: editor.starred,
      });
      setMessage(`Saved filing for ${selectedItem.domain}${selectedItem.path}`);
      await loadWorkspaceLibrary(selectedWorkspaceId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save page filing');
    } finally {
      setSavingItem(false);
    }
  }

  function handleExport(fmt: 'json' | 'csv') {
    if (!selectedWorkspaceId) return;
    const params = new URLSearchParams();
    if (filters.search.trim()) params.set('search', filters.search.trim());
    if (filters.category.trim()) params.set('category', filters.category.trim());
    if (filters.domain.trim()) params.set('domain', filters.domain.trim());
    params.set('fmt', fmt);
    window.open(
      `${API_BASE_URL}/api/workspaces/${selectedWorkspaceId}/library/export?${params.toString()}`,
      '_blank',
      'noopener,noreferrer',
    );
  }

  useEffect(() => {
    void loadWorkspaces();
  }, []);

  useEffect(() => {
    if (!selectedWorkspaceId) {
      setSummary(null);
      setLibrary(null);
      setSelectedItemId('');
      return;
    }
    void loadWorkspaceLibrary(selectedWorkspaceId);
  }, [selectedWorkspaceId]);

  useEffect(() => {
    if (!selectedItem) {
      setEditor({ category: '', folder: '', labels: '', notes: '', starred: false });
      return;
    }
    setEditor({
      category: selectedItem.category,
      folder: selectedItem.folder,
      labels: selectedItem.labels.join(', '),
      notes: selectedItem.notes ?? '',
      starred: selectedItem.starred,
    });
  }, [selectedItem]);

  return (
    <div className="space-y-4">
      <AnimateIn>
        <div className={panelCls}>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-reaper-border px-4 py-3">
            <div>
              <div className="flex items-center gap-2 text-sm font-mono text-white">
                <FolderOpen className="h-4 w-4 text-reaper-accent" />
                Workspace Library
              </div>
              <div className="mt-1 text-xs font-mono text-reaper-muted">
                Crawl into a workspace, auto-file scraped pages, then manually star and categorize what matters.
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => void loadWorkspaces(selectedWorkspaceId || undefined)}
                className={clsx(buttonCls, 'border-reaper-border text-reaper-muted hover:text-white')}
                type="button"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Refresh
              </button>
              <button
                onClick={() => void handleAutoFile()}
                disabled={!selectedWorkspaceId || autoFiling}
                className={clsx(buttonCls, 'border-reaper-accent/30 bg-reaper-accent/10 text-reaper-accent disabled:opacity-50')}
                type="button"
              >
                <Sparkles className="h-3.5 w-3.5" />
                {autoFiling ? 'Auto-Filing...' : 'Auto-File'}
              </button>
              <button
                onClick={() => handleExport('json')}
                disabled={!selectedWorkspaceId}
                className={clsx(buttonCls, 'border-reaper-border text-reaper-muted hover:text-white disabled:opacity-50')}
                type="button"
              >
                <Download className="h-3.5 w-3.5" />
                JSON
              </button>
              <button
                onClick={() => handleExport('csv')}
                disabled={!selectedWorkspaceId}
                className={clsx(buttonCls, 'border-reaper-border text-reaper-muted hover:text-white disabled:opacity-50')}
                type="button"
              >
                <Download className="h-3.5 w-3.5" />
                CSV
              </button>
            </div>
          </div>
          {(message || error) ? (
            <div className="px-4 py-3 text-xs font-mono">
              {message ? <div className="text-reaper-success">{message}</div> : null}
              {error ? <div className="text-reaper-danger">{error}</div> : null}
            </div>
          ) : null}
        </div>
      </AnimateIn>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
        <div className="space-y-4">
          <AnimateIn delay={0.05}>
            <form onSubmit={handleCreateWorkspace} className={clsx(panelCls, 'p-4')}>
              <div className="text-xs font-mono uppercase tracking-widest text-reaper-muted">New Workspace</div>
              <label className="mt-3 block text-xs font-mono text-reaper-muted">
                Name
                <input
                  value={workspaceForm.name}
                  onChange={(event) => setWorkspaceForm((current) => ({ ...current, name: event.target.value }))}
                  className={inputCls}
                  placeholder="Acme Prospecting"
                  required
                />
              </label>
              <label className="mt-3 block text-xs font-mono text-reaper-muted">
                Description
                <textarea
                  value={workspaceForm.description}
                  onChange={(event) => setWorkspaceForm((current) => ({ ...current, description: event.target.value }))}
                  className={clsx(inputCls, 'min-h-24 resize-y')}
                  placeholder="What this workspace is collecting and why."
                />
              </label>
              <button
                type="submit"
                disabled={creatingWorkspace}
                className={clsx(buttonCls, 'mt-4 border-reaper-accent/30 bg-reaper-accent/10 text-reaper-accent disabled:opacity-50')}
              >
                <Plus className="h-3.5 w-3.5" />
                {creatingWorkspace ? 'Creating...' : 'Create Workspace'}
              </button>
            </form>
          </AnimateIn>

          <AnimateIn delay={0.1}>
            <div className={clsx(panelCls, 'p-4')}>
              <div className="text-xs font-mono uppercase tracking-widest text-reaper-muted">Workspaces</div>
              <div className="mt-3 space-y-2">
                {loadingWorkspaces ? (
                  Array.from({ length: 4 }).map((_, index) => <SkeletonCard key={index} />)
                ) : workspaces.length > 0 ? (
                  workspaces.map((workspace) => {
                    const active = workspace.id === selectedWorkspaceId;
                    return (
                      <button
                        key={workspace.id}
                        onClick={() => setSelectedWorkspaceId(workspace.id)}
                        className={clsx(
                          'w-full rounded border px-3 py-3 text-left transition-colors',
                          active
                            ? 'border-reaper-accent/40 bg-reaper-accent/10'
                            : 'border-reaper-border bg-black/20 hover:border-reaper-accent/20',
                        )}
                        type="button"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="truncate text-sm font-mono text-white">{workspace.name}</div>
                          {active ? <span className="text-[10px] font-mono text-reaper-accent">ACTIVE</span> : null}
                        </div>
                        <div className="mt-2 line-clamp-2 text-xs font-mono text-reaper-muted">
                          {workspace.description || 'No description yet.'}
                        </div>
                      </button>
                    );
                  })
                ) : (
                  <div className="rounded border border-dashed border-reaper-border px-3 py-6 text-center text-xs font-mono text-reaper-muted">
                    Create the first workspace to start organizing scraped pages.
                  </div>
                )}
              </div>
            </div>
          </AnimateIn>

          <AnimateIn delay={0.15}>
            <form onSubmit={handleStartWorkspaceCrawl} className={clsx(panelCls, 'p-4')}>
              <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-reaper-muted">
                <Globe className="h-3.5 w-3.5 text-reaper-accent" />
                Crawl Into Workspace
              </div>
              <label className="mt-3 block text-xs font-mono text-reaper-muted">
                Target URL
                <input
                  value={crawlForm.url}
                  onChange={(event) => setCrawlForm((current) => ({ ...current, url: event.target.value }))}
                  className={inputCls}
                  placeholder="https://example.com"
                  disabled={!selectedWorkspaceId}
                  required
                />
              </label>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <label className="block text-xs font-mono text-reaper-muted">
                  Depth
                  <input
                    type="number"
                    min={1}
                    max={10}
                    value={crawlForm.depth}
                    onChange={(event) => setCrawlForm((current) => ({ ...current, depth: Number(event.target.value) }))}
                    className={inputCls}
                    disabled={!selectedWorkspaceId}
                  />
                </label>
                <label className="block text-xs font-mono text-reaper-muted">
                  Concurrency
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={crawlForm.concurrency}
                    onChange={(event) => setCrawlForm((current) => ({ ...current, concurrency: Number(event.target.value) }))}
                    className={inputCls}
                    disabled={!selectedWorkspaceId}
                  />
                </label>
              </div>
              <label className="mt-3 flex items-center gap-2 text-xs font-mono text-reaper-muted">
                <input
                  type="checkbox"
                  checked={crawlForm.browser_render}
                  onChange={(event) => setCrawlForm((current) => ({ ...current, browser_render: event.target.checked }))}
                  disabled={!selectedWorkspaceId}
                />
                Browser-render fallback
              </label>
              <button
                type="submit"
                disabled={!selectedWorkspaceId || startingCrawl}
                className={clsx(buttonCls, 'mt-4 border-reaper-warning/30 bg-reaper-warning/10 text-reaper-warning disabled:opacity-50')}
              >
                <ExternalLink className="h-3.5 w-3.5" />
                {startingCrawl ? 'Starting...' : 'Start Workspace Crawl'}
              </button>
            </form>
          </AnimateIn>
        </div>

        <div className="space-y-4">
          <AnimateIn delay={0.1}>
            <div className={clsx(panelCls, 'p-4')}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-mono text-white">
                    {summary?.workspace.name || 'Workspace overview'}
                  </div>
                  <div className="mt-1 text-xs font-mono text-reaper-muted">
                    Filing density, domain spread, and content shape for the selected workspace.
                  </div>
                </div>
                {selectedWorkspaceId ? (
                  <button
                    type="button"
                    onClick={() => void loadWorkspaceLibrary(selectedWorkspaceId)}
                    className={clsx(buttonCls, 'border-reaper-border text-reaper-muted hover:text-white')}
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    Reload
                  </button>
                ) : null}
              </div>

              {loadingLibrary && !summary ? (
                <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-4">
                  {Array.from({ length: 4 }).map((_, index) => <SkeletonCard key={index} />)}
                </div>
              ) : summary ? (
                <>
                  <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-4">
                    <StatCard label="Pages" value={String(summary.summary.total_pages)} hint="Scraped into this workspace" />
                    <StatCard label="Filed" value={String(summary.summary.filed_pages)} hint="Pages with manual or auto filing" />
                    <StatCard label="Starred" value={String(summary.summary.starred_pages)} hint="High-signal saved pages" />
                    <StatCard label="Domains" value={String(summary.summary.domains)} hint={`Avg words ${summary.summary.avg_word_count}`} />
                  </div>
                  <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
                    <div className="rounded border border-reaper-border bg-black/20 p-3">
                      <div className="text-[10px] font-mono uppercase tracking-widest text-reaper-muted">Top Categories</div>
                      <div className="mt-3 space-y-2">
                        {summary.summary.by_category.slice(0, 5).map((entry) => (
                          <div key={entry.category} className="flex items-center justify-between gap-3 text-xs font-mono">
                            <span className="text-white">{entry.category}</span>
                            <span className="text-reaper-muted">{entry.count}</span>
                          </div>
                        ))}
                        {summary.summary.by_category.length === 0 ? (
                          <div className="text-xs font-mono text-reaper-muted">No pages filed yet.</div>
                        ) : null}
                      </div>
                    </div>
                    <div className="rounded border border-reaper-border bg-black/20 p-3">
                      <div className="text-[10px] font-mono uppercase tracking-widest text-reaper-muted">Recent Pages</div>
                      <div className="mt-3 space-y-2">
                        {summary.recent_items.slice(0, 5).map((item) => (
                          <button
                            key={item.page_id}
                            onClick={() => setSelectedItemId(item.page_id)}
                            className="block w-full text-left"
                            type="button"
                          >
                            <div className="truncate text-xs font-mono text-white">{item.title || item.url}</div>
                            <div className="mt-1 truncate text-[11px] font-mono text-reaper-muted">{item.folder}</div>
                          </button>
                        ))}
                        {summary.recent_items.length === 0 ? (
                          <div className="text-xs font-mono text-reaper-muted">This workspace has no pages yet.</div>
                        ) : null}
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <div className="mt-4 rounded border border-dashed border-reaper-border px-4 py-8 text-center text-xs font-mono text-reaper-muted">
                  Select a workspace to see its library.
                </div>
              )}
            </div>
          </AnimateIn>

          <AnimateIn delay={0.15}>
            <div className={clsx(panelCls, 'p-4')}>
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  if (!selectedWorkspaceId) return;
                  void loadWorkspaceLibrary(selectedWorkspaceId, filters);
                }}
                className="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1.6fr)_220px_220px_auto]"
              >
                <label className="block text-xs font-mono text-reaper-muted">
                  Search
                  <div className="relative mt-1">
                    <Search className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-reaper-muted" />
                    <input
                      value={filters.search}
                      onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
                      className={clsx(inputCls, 'pl-9')}
                      placeholder="title, h1, or URL"
                    />
                  </div>
                </label>
                <label className="block text-xs font-mono text-reaper-muted">
                  Category
                  <input
                    list="workspace-library-categories"
                    value={filters.category}
                    onChange={(event) => setFilters((current) => ({ ...current, category: event.target.value }))}
                    className={inputCls}
                    placeholder="documentation"
                  />
                </label>
                <label className="block text-xs font-mono text-reaper-muted">
                  Domain
                  <input
                    value={filters.domain}
                    onChange={(event) => setFilters((current) => ({ ...current, domain: event.target.value }))}
                    className={inputCls}
                    placeholder="example.com"
                  />
                </label>
                <div className="flex flex-wrap items-end gap-3">
                  <label className="flex items-center gap-2 text-xs font-mono text-reaper-muted">
                    <input
                      type="checkbox"
                      checked={filters.starredOnly}
                      onChange={(event) => setFilters((current) => ({ ...current, starredOnly: event.target.checked }))}
                    />
                    Starred only
                  </label>
                  <button
                    type="submit"
                    disabled={!selectedWorkspaceId}
                    className={clsx(buttonCls, 'border-reaper-border text-reaper-muted hover:text-white disabled:opacity-50')}
                  >
                    Apply
                  </button>
                </div>
              </form>
              <datalist id="workspace-library-categories">
                {CATEGORY_OPTIONS.map((category) => <option key={category} value={category} />)}
              </datalist>
            </div>
          </AnimateIn>

          <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1fr)_360px]">
            <AnimateIn delay={0.2}>
              <div className={clsx(panelCls, 'overflow-hidden')}>
                <div className="border-b border-reaper-border px-4 py-3 text-xs font-mono uppercase tracking-widest text-reaper-muted">
                  Library Items
                </div>
                <div className="overflow-x-auto">
                  {loadingLibrary ? (
                    <div className="p-4">
                      <SkeletonTable rows={8} />
                    </div>
                  ) : (
                    <table className="w-full text-left text-xs font-mono">
                      <thead className="border-b border-reaper-border text-reaper-muted">
                        <tr>
                          <th className="px-3 py-2 font-normal">Page</th>
                          <th className="px-3 py-2 font-normal">Category</th>
                          <th className="px-3 py-2 font-normal">Folder</th>
                          <th className="px-3 py-2 font-normal">Status</th>
                          <th className="px-3 py-2 font-normal">Words</th>
                        </tr>
                      </thead>
                      <tbody>
                        {library?.items.map((item) => (
                          <tr
                            key={item.page_id}
                            onClick={() => setSelectedItemId(item.page_id)}
                            className={clsx(
                              'cursor-pointer border-b border-reaper-border/50 transition-colors hover:bg-reaper-border/20',
                              item.page_id === selectedItemId && 'bg-reaper-accent/10',
                            )}
                          >
                            <td className="px-3 py-3 align-top">
                              <div className="flex items-start gap-2">
                                <Star className={clsx('mt-0.5 h-3.5 w-3.5', item.starred ? 'fill-current text-reaper-warning' : 'text-reaper-muted')} />
                                <div className="min-w-0">
                                  <div className="truncate text-white">{item.title || item.url}</div>
                                  <div className="mt-1 truncate text-[11px] text-reaper-muted">{item.url}</div>
                                  <div className="mt-1 flex flex-wrap gap-1">
                                    {item.labels.slice(0, 3).map((label) => (
                                      <span key={label} className="rounded bg-black/30 px-1.5 py-0.5 text-[10px] text-reaper-muted">
                                        {label}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                              </div>
                            </td>
                            <td className="px-3 py-3 align-top">
                              <div className="text-white">{item.category}</div>
                              <div className="mt-1 text-[11px] text-reaper-muted">{item.category_source}</div>
                            </td>
                            <td className="px-3 py-3 align-top">
                              <div className="max-w-[240px] truncate text-white">{item.folder}</div>
                              <div className="mt-1 text-[11px] text-reaper-muted">{item.domain}</div>
                            </td>
                            <td className="px-3 py-3 align-top text-white">
                              {item.status_code || '—'}
                            </td>
                            <td className="px-3 py-3 align-top text-white">
                              {item.word_count.toLocaleString()}
                            </td>
                          </tr>
                        ))}
                        {!library || library.items.length === 0 ? (
                          <tr>
                            <td colSpan={5} className="px-4 py-10 text-center text-xs font-mono text-reaper-muted">
                              No library items yet. Start a crawl into this workspace, then auto-file the results.
                            </td>
                          </tr>
                        ) : null}
                      </tbody>
                    </table>
                  )}
                </div>
              </div>
            </AnimateIn>

            <AnimateIn delay={0.25}>
              <div className={clsx(panelCls, 'p-4')}>
                <div className="flex items-center justify-between gap-2">
                  <div className="text-xs font-mono uppercase tracking-widest text-reaper-muted">Selected Page</div>
                  {selectedItem ? (
                    <button
                      type="button"
                      onClick={() => window.open(selectedItem.url, '_blank', 'noopener,noreferrer')}
                      className={clsx(buttonCls, 'border-reaper-border text-reaper-muted hover:text-white')}
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                      Open
                    </button>
                  ) : null}
                </div>

                {selectedItem ? (
                  <form onSubmit={handleSaveSelectedItem} className="mt-4 space-y-3">
                    <div>
                      <div className="text-sm font-mono text-white">{selectedItem.title || selectedItem.url}</div>
                      <div className="mt-1 break-all text-[11px] font-mono text-reaper-muted">{selectedItem.url}</div>
                    </div>

                    <label className="block text-xs font-mono text-reaper-muted">
                      Category
                      <input
                        list="workspace-library-categories"
                        value={editor.category}
                        onChange={(event) => setEditor((current) => ({ ...current, category: event.target.value }))}
                        className={inputCls}
                      />
                    </label>

                    <label className="block text-xs font-mono text-reaper-muted">
                      Folder
                      <input
                        value={editor.folder}
                        onChange={(event) => setEditor((current) => ({ ...current, folder: event.target.value }))}
                        className={inputCls}
                      />
                    </label>

                    <label className="block text-xs font-mono text-reaper-muted">
                      Labels
                      <input
                        value={editor.labels}
                        onChange={(event) => setEditor((current) => ({ ...current, labels: event.target.value }))}
                        className={inputCls}
                        placeholder="priority:high, owner:sales"
                      />
                    </label>

                    <label className="block text-xs font-mono text-reaper-muted">
                      Notes
                      <textarea
                        value={editor.notes}
                        onChange={(event) => setEditor((current) => ({ ...current, notes: event.target.value }))}
                        className={clsx(inputCls, 'min-h-28 resize-y')}
                        placeholder="Why this page matters."
                      />
                    </label>

                    <label className="flex items-center gap-2 text-xs font-mono text-reaper-muted">
                      <input
                        type="checkbox"
                        checked={editor.starred}
                        onChange={(event) => setEditor((current) => ({ ...current, starred: event.target.checked }))}
                      />
                      Star this page
                    </label>

                    <div className="rounded border border-reaper-border bg-black/20 p-3 text-[11px] font-mono text-reaper-muted">
                      Suggested: {selectedItem.suggested_category} in {selectedItem.suggested_folder}
                    </div>

                    <button
                      type="submit"
                      disabled={savingItem}
                      className={clsx(buttonCls, 'border-reaper-accent/30 bg-reaper-accent/10 text-reaper-accent disabled:opacity-50')}
                    >
                      <Save className="h-3.5 w-3.5" />
                      {savingItem ? 'Saving...' : 'Save Filing'}
                    </button>
                  </form>
                ) : (
                  <div className="mt-4 rounded border border-dashed border-reaper-border px-4 py-10 text-center text-xs font-mono text-reaper-muted">
                    Pick a page to edit its filing metadata.
                  </div>
                )}
              </div>
            </AnimateIn>
          </div>
        </div>
      </div>
    </div>
  );
}
