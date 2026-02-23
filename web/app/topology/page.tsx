'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import { Network, RefreshCw, Maximize2, Minimize2, ChevronDown } from 'lucide-react';
import { ForceGraph } from '@/components/topology/force-graph';
import { AnimateIn } from '@/components/shared/animate-in';
import { Skeleton } from '@/components/shared/skeleton';
import { useApi } from '@/hooks/use-api';
import type { Page, TopologyData } from '@/lib/types';

interface Crawl { id: string; start_url: string; pages_crawled: number; started_at: string }

export default function TopologyPage() {
  const { data: crawls } = useApi<Crawl[]>('/api/data/crawls');
  const [selectedCrawl, setSelectedCrawl] = useState<string>('');

  // Auto-select the most recent crawl
  useEffect(() => {
    if (crawls && crawls.length > 0 && !selectedCrawl) {
      setSelectedCrawl(crawls[0].id);
    }
  }, [crawls, selectedCrawl]);

  const endpoint = selectedCrawl
    ? `/api/results/pages?crawl_id=${selectedCrawl}&limit=200`
    : null;

  const { data: pages, loading, refetch } = useApi<Page[]>(endpoint ?? '');
  const [fullscreen, setFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 });

  useEffect(() => {
    const measure = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setDimensions({
          width: Math.floor(rect.width) - 2,
          height: fullscreen ? window.innerHeight - 120 : Math.min(500, window.innerHeight - 280),
        });
      }
    };
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [fullscreen]);

  const topology: TopologyData = useMemo(() => {
    if (!pages || pages.length === 0) return { nodes: [], links: [] };

    const domainMap = new Map<string, { pages: number; status: number }>();
    const linkMap = new Map<string, number>();

    for (const page of pages) {
      try {
        const domain = new URL(page.url).hostname;
        const existing = domainMap.get(domain);
        if (existing) {
          existing.pages++;
        } else {
          domainMap.set(domain, { pages: 1, status: page.status_code });
        }
      } catch { /* skip invalid URLs */ }
    }

    const domains = Array.from(domainMap.keys());
    for (let i = 0; i < domains.length && i < 80; i++) {
      for (let j = i + 1; j < domains.length && j < 80; j++) {
        const parts1 = domains[i].split('.');
        const parts2 = domains[j].split('.');
        if (parts1.slice(-2).join('.') === parts2.slice(-2).join('.')) {
          const key = `${domains[i]}-${domains[j]}`;
          linkMap.set(key, (linkMap.get(key) || 0) + 1);
        }
      }
    }

    const nodes = Array.from(domainMap.entries()).slice(0, 80).map(([domain, data]) => ({
      id: domain, domain, pages: data.pages, status: data.status,
    }));
    const nodeIds = new Set(nodes.map((n) => n.id));
    const links = Array.from(linkMap.entries())
      .filter(([key]) => { const [s, t] = key.split('-'); return nodeIds.has(s) && nodeIds.has(t); })
      .map(([key, weight]) => { const [source, target] = key.split('-'); return { source, target, weight }; });

    return { nodes, links };
  }, [pages]);

  const selectedCrawlData = crawls?.find((c) => c.id === selectedCrawl);

  return (
    <div className="space-y-4">
      <AnimateIn>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <h1 className="text-sm font-mono text-white flex items-center gap-2">
              <Network className="w-4 h-4 text-reaper-accent" />
              Network Topology
            </h1>
            {/* Crawl selector */}
            <div className="relative">
              <select
                value={selectedCrawl}
                onChange={(e) => setSelectedCrawl(e.target.value)}
                className="appearance-none bg-reaper-bg border border-reaper-border rounded px-3 py-1 text-xs font-mono text-white focus:border-reaper-accent outline-none pr-7 cursor-pointer"
              >
                {!crawls || crawls.length === 0
                  ? <option value="">No crawls yet</option>
                  : crawls.map((c) => {
                      let label = c.start_url || c.id;
                      try { label = new URL(c.start_url).hostname; } catch { /* ok */ }
                      return (
                        <option key={c.id} value={c.id}>
                          {label} ({c.pages_crawled}p)
                        </option>
                      );
                    })
                }
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-reaper-muted pointer-events-none" />
            </div>
            <span className="text-xs text-reaper-muted font-mono">
              {topology.nodes.length} domains · {topology.links.length} edges
            </span>
          </div>
          <div className="flex gap-2">
            <button onClick={() => setFullscreen(!fullscreen)} className="text-reaper-muted hover:text-white transition-colors">
              {fullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
            </button>
            <button onClick={refetch} className="text-reaper-muted hover:text-white transition-colors">
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </AnimateIn>

      <AnimateIn delay={0.1}>
        <div ref={containerRef} className="w-full">
          {!selectedCrawl ? (
            <div className="bg-reaper-surface border border-reaper-border rounded-lg flex items-center justify-center h-[500px] text-reaper-muted font-mono text-sm">
              No crawls yet — run a crawl to see the topology
            </div>
          ) : loading ? (
            <Skeleton className="w-full" height={500} />
          ) : topology.nodes.length === 0 ? (
            <div className="bg-reaper-surface border border-reaper-border rounded-lg flex items-center justify-center h-[500px] text-reaper-muted font-mono text-sm">
              No topology data for this crawl
            </div>
          ) : (
            <ForceGraph data={topology} width={dimensions.width} height={dimensions.height} />
          )}
        </div>
      </AnimateIn>
    </div>
  );
}
