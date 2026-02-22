'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import { Network, RefreshCw, Maximize2, Minimize2 } from 'lucide-react';
import { ForceGraph } from '@/components/topology/force-graph';
import { AnimateIn } from '@/components/shared/animate-in';
import { Skeleton } from '@/components/shared/skeleton';
import { useApi } from '@/hooks/use-api';
import type { Page, TopologyData } from '@/lib/types';

export default function TopologyPage() {
  const { data: pages, loading, refetch } = useApi<Page[]>('/api/results/pages');
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
    if (!pages || pages.length === 0) {
      return { nodes: [], links: [] };
    }

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
      } catch {
        // skip invalid URLs
      }
    }

    const domains = Array.from(domainMap.keys());
    for (let i = 0; i < domains.length && i < 50; i++) {
      for (let j = i + 1; j < domains.length && j < 50; j++) {
        const key = `${domains[i]}-${domains[j]}`;
        const parts1 = domains[i].split('.');
        const parts2 = domains[j].split('.');
        const tld1 = parts1.slice(-2).join('.');
        const tld2 = parts2.slice(-2).join('.');
        if (tld1 === tld2) {
          linkMap.set(key, (linkMap.get(key) || 0) + 1);
        }
      }
    }

    const nodes = Array.from(domainMap.entries()).slice(0, 50).map(([domain, data]) => ({
      id: domain,
      domain,
      pages: data.pages,
      status: data.status,
    }));

    const nodeIds = new Set(nodes.map((n) => n.id));
    const links = Array.from(linkMap.entries())
      .filter(([key]) => {
        const [src, tgt] = key.split('-');
        return nodeIds.has(src) && nodeIds.has(tgt);
      })
      .map(([key, weight]) => {
        const [source, target] = key.split('-');
        return { source, target, weight };
      });

    return { nodes, links };
  }, [pages]);

  return (
    <div className="space-y-4">
      <AnimateIn>
        <div className="flex items-center justify-between">
          <h1 className="text-sm font-mono text-white flex items-center gap-2">
            <Network className="w-4 h-4 text-reaper-accent" />
            Network Topology
            <span className="text-xs text-reaper-muted">
              ({topology.nodes.length} domains, {topology.links.length} connections)
            </span>
          </h1>
          <div className="flex gap-2">
            <button
              onClick={() => setFullscreen(!fullscreen)}
              className="text-reaper-muted hover:text-white transition-colors"
            >
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
          {loading ? (
            <Skeleton className="w-full" height={500} />
          ) : topology.nodes.length === 0 ? (
            <div className="bg-reaper-surface border border-reaper-border rounded-lg flex items-center justify-center h-[500px] text-reaper-muted font-mono text-sm">
              No topology data. Run a crawl to populate the graph.
            </div>
          ) : (
            <ForceGraph
              data={topology}
              width={dimensions.width}
              height={dimensions.height}
            />
          )}
        </div>
      </AnimateIn>
    </div>
  );
}
