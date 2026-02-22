'use client';

import { AnimateIn } from '@/components/shared/animate-in';
import { Counter } from '@/components/shared/counter';

interface QueueGaugeProps {
  depth: number;
  max?: number;
}

export function QueueGauge({ depth, max = 1000 }: QueueGaugeProps) {
  const pct = Math.min((depth / max) * 100, 100);
  const color = pct > 80 ? '#ff4444' : pct > 50 ? '#ffaa00' : '#00d4ff';

  return (
    <AnimateIn delay={0.2}>
      <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
        <h3 className="text-xs font-mono text-reaper-muted uppercase tracking-wider mb-3">
          Queue Depth
        </h3>
        <div className="flex items-end gap-3 mb-3">
          <Counter value={depth} className="text-2xl font-mono font-bold text-white" />
          <span className="text-xs font-mono text-reaper-muted mb-1">/ {max}</span>
        </div>
        <div className="h-2 bg-reaper-border rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500 ease-out"
            style={{ width: `${pct}%`, backgroundColor: color }}
          />
        </div>
        <div className="mt-1 text-right">
          <span className="text-xs font-mono" style={{ color }}>
            {pct.toFixed(0)}%
          </span>
        </div>
      </div>
    </AnimateIn>
  );
}
