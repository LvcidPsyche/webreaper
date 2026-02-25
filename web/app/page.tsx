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
    eventNames: 'metrics',
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
        <MetricCard icon={FileText} label="Pages Crawled" value={metrics.pages_crawled} color="#39ff14" delay={0} />
        <MetricCard icon={Shield} label="Findings" value={metrics.security_findings} color="#ff2a2a" delay={0.03} />
        <MetricCard icon={Play} label="Active Jobs" value={metrics.active_jobs} color="#39ff14" delay={0.06} />
        <MetricCard icon={Layers} label="Queue Depth" value={metrics.queue_depth} color="#ff8800" delay={0.09} />
        <MetricCard icon={Zap} label="Req/s" value={metrics.requests_per_second} decimals={1} color="#4d9fd4" delay={0.12} />
        <div className="ghost-panel relative overflow-hidden">
          <div className="h-[2px] w-full bg-ghost-red" />
          <div className="p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="ghost-label">Error Rate</span>
              <AlertTriangle className="w-3.5 h-3.5 text-ghost-red" />
            </div>
            <div className="flex items-end gap-2">
              <span className="text-2xl font-mono font-bold text-white tabular-nums">
                {metrics.error_rate.toFixed(1)}%
              </span>
              <ErrorSparkline data={errorHistory} />
            </div>
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
