'use client';

import { type LucideIcon } from 'lucide-react';
import { Counter } from '@/components/shared/counter';
import { AnimateIn } from '@/components/shared/animate-in';

interface MetricCardProps {
  icon: LucideIcon;
  label: string;
  value: number;
  decimals?: number;
  suffix?: string;
  trend?: number;
  color?: string;
  delay?: number;
}

export function MetricCard({
  icon: Icon,
  label,
  value,
  decimals = 0,
  suffix = '',
  trend,
  color = '#39ff14',
  delay = 0,
}: MetricCardProps) {
  const trendPositive = trend !== undefined && trend >= 0;

  return (
    <AnimateIn delay={delay} className="w-full">
      <div className="ghost-panel relative overflow-hidden">
        {/* Top accent bar */}
        <div className="h-[2px] w-full" style={{ backgroundColor: color }} />
        <div className="p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="ghost-label">{label}</span>
            {trend !== undefined && (
              <span
                className="text-[10px] font-mono"
                style={{ color: trendPositive ? '#39ff14' : '#ff2a2a' }}
              >
                {trendPositive ? '+' : ''}{trend.toFixed(1)}%
              </span>
            )}
          </div>
          <div className="flex items-end gap-1.5">
            <Counter
              value={value}
              decimals={decimals}
              suffix={suffix}
              className="text-2xl font-mono font-bold text-white tabular-nums"
            />
            <Icon className="w-3.5 h-3.5 mb-0.5 shrink-0" style={{ color }} />
          </div>
        </div>
      </div>
    </AnimateIn>
  );
}
