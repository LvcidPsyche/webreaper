'use client';

import { useState, useCallback } from 'react';
import { FileText, Shield, Play, Layers, Zap, AlertTriangle } from 'lucide-react';
import { MetricCard } from '@/components/dashboard/metric-card';
import { ThroughputChart } from '@/components/dashboard/throughput-chart';
import { StatusDonut } from '@/components/dashboard/status-donut';
import { QueueGauge } from '@/components/dashboard/queue-gauge';
import { ErrorSparkline } from '@/components/dashboard/error-sparkline';
import { SkeletonCard } from '@/components/shared/skeleton';
import { AnimateIn } from '@/components/shared/animate-in';
import { useSSE } from '@/hooks/use-sse';
import type { MetricsSnapshot } from '@/lib/types';

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<MetricsSnapshot | null>(null);
  const [errorHistory, setErrorHistory] = useState<number[]>([]);

  const handleMetrics = useCallback((data: MetricsSnapshot) => {
    setMetrics(data);
    setErrorHistory((prev) => [...prev.slice(-19), data.error_rate]);
  }, []);

  useSSE<MetricsSnapshot>({
    path: '/stream/metrics',
    onEvent: handleMetrics,
  });

  if (!metrics) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <MetricCard icon={FileText} label="Pages Crawled" value={metrics.pages_crawled} delay={0} />
        <MetricCard icon={Shield} label="Findings" value={metrics.security_findings} color="#ff4444" delay={0.03} />
        <MetricCard icon={Play} label="Active Jobs" value={metrics.active_jobs} color="#00ff88" delay={0.06} />
        <MetricCard icon={Layers} label="Queue Depth" value={metrics.queue_depth} color="#ffaa00" delay={0.09} />
        <MetricCard icon={Zap} label="Req/s" value={metrics.requests_per_second} decimals={1} delay={0.12} />
        <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-reaper-danger" />
            <span className="text-xs font-mono text-reaper-muted uppercase tracking-wider">Error Rate</span>
          </div>
          <div className="flex items-end gap-2">
            <span className="text-2xl font-mono font-bold text-white">
              {metrics.error_rate.toFixed(1)}%
            </span>
            <ErrorSparkline data={errorHistory} />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="lg:col-span-2">
          <ThroughputChart data={metrics.throughput_history} />
        </div>
        <StatusDonut statusCodes={metrics.status_codes} />
      </div>

      <AnimateIn delay={0.25}>
        <QueueGauge depth={metrics.queue_depth} />
      </AnimateIn>
    </div>
  );
}
