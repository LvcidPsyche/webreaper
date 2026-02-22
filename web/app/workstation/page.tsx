'use client';

import { useState } from 'react';
import { FlaskConical, RefreshCw } from 'lucide-react';
import { Canvas } from '@/components/workstation/canvas';
import { BriefViewer } from '@/components/workstation/brief-viewer';
import { DataTable } from '@/components/workstation/data-table';
import { AnimateIn } from '@/components/shared/animate-in';
import { SkeletonCard, SkeletonTable } from '@/components/shared/skeleton';
import { useApi } from '@/hooks/use-api';
import type { IntelligenceBrief, Page } from '@/lib/types';

export default function WorkstationPage() {
  const { data: briefs, loading: briefsLoading, refetch: refetchBriefs } =
    useApi<IntelligenceBrief[]>('/api/workstation/briefs');
  const { data: pages, loading: pagesLoading } = useApi<Page[]>('/api/workstation/results');
  const [selectedBrief, setSelectedBrief] = useState<IntelligenceBrief | null>(null);

  const pageColumns = [
    { key: 'url' as const, label: 'URL', sortable: true },
    { key: 'status_code' as const, label: 'Status', sortable: true, width: '80px',
      render: (val: unknown) => {
        const code = val as number;
        const color = code < 300 ? 'text-reaper-success' : code < 400 ? 'text-reaper-accent' : code < 500 ? 'text-reaper-warning' : 'text-reaper-danger';
        return <span className={color}>{code}</span>;
      }
    },
    { key: 'title' as const, label: 'Title', sortable: true },
    { key: 'response_time_ms' as const, label: 'Time (ms)', sortable: true, width: '100px' },
    { key: 'links_found' as const, label: 'Links', sortable: true, width: '80px' },
  ];

  return (
    <div className="space-y-4">
      <AnimateIn>
        <div className="flex items-center justify-between">
          <h1 className="text-sm font-mono text-white flex items-center gap-2">
            <FlaskConical className="w-4 h-4 text-reaper-accent" />
            Research Workstation
          </h1>
          <button
            onClick={refetchBriefs}
            className="text-reaper-muted hover:text-white transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </AnimateIn>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className={selectedBrief ? 'lg:col-span-2' : 'lg:col-span-3'}>
          <AnimateIn delay={0.05}>
            <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
              <h2 className="text-xs font-mono text-reaper-muted uppercase tracking-wider mb-3">
                Intelligence Briefs
              </h2>
              {briefsLoading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
                </div>
              ) : (
                <Canvas
                  briefs={briefs || []}
                  onSelect={setSelectedBrief}
                />
              )}
            </div>
          </AnimateIn>
        </div>

        {selectedBrief && (
          <AnimateIn delay={0.1} direction="left" className="lg:col-span-1 h-[400px]">
            <BriefViewer brief={selectedBrief} onClose={() => setSelectedBrief(null)} />
          </AnimateIn>
        )}
      </div>

      <AnimateIn delay={0.15}>
        <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
          <h2 className="text-xs font-mono text-reaper-muted uppercase tracking-wider mb-3">
            Crawl Results
          </h2>
          {pagesLoading ? (
            <SkeletonTable rows={8} />
          ) : (
            <DataTable
              columns={pageColumns}
              data={(pages || []) as unknown as Record<string, unknown>[]}
              searchable
              searchKeys={['url' as never, 'title' as never]}
            />
          )}
        </div>
      </AnimateIn>
    </div>
  );
}
