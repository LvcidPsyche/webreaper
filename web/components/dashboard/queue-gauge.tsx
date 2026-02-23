'use client';

import { AnimateIn } from '@/components/shared/animate-in';
import { Counter } from '@/components/shared/counter';

interface QueueGaugeProps {
  depth: number;
  max?: number;
}

export function QueueGauge({ depth, max = 1000 }: QueueGaugeProps) {
  const pct = Math.min((depth / max) * 100, 100);
  const color = pct > 80 ? '#ff2a2a' : pct > 50 ? '#ff8800' : '#39ff14';

  return (
    <AnimateIn delay={0.2}>
      <div className="ghost-panel p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="ghost-label">Queue Depth</h3>
          <span className="text-[10px] font-mono" style={{ color }}>{pct.toFixed(0)}%</span>
        </div>
        <div className="flex items-end gap-3 mb-3">
          <Counter value={depth} className="text-2xl font-mono font-bold text-white tabular-nums" />
          <span className="text-[10px] font-mono text-ghost-dim mb-1">/ {max}</span>
        </div>
        <div className="h-1 bg-ghost-border overflow-hidden">
          <div
            className="h-full transition-all duration-500 ease-out"
            style={{ width: `${pct}%`, backgroundColor: color }}
          />
        </div>
      </div>
    </AnimateIn>
  );
}
