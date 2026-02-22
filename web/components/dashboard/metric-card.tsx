'use client';

import { type LucideIcon, TrendingUp, TrendingDown } from 'lucide-react';
import { Counter } from '@/components/shared/counter';
import { AnimateIn } from '@/components/shared/animate-in';
import { clsx } from 'clsx';

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
  color = '#00d4ff',
  delay = 0,
}: MetricCardProps) {
  const trendPositive = trend !== undefined && trend >= 0;

  return (
    <AnimateIn delay={delay} className="w-full">
      <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4 hover:border-reaper-accent/30 transition-colors duration-150">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Icon className="w-4 h-4" style={{ color }} />
            <span className="text-xs font-mono text-reaper-muted uppercase tracking-wider">
              {label}
            </span>
          </div>
          {trend !== undefined && (
            <div
              className={clsx(
                'flex items-center gap-0.5 text-xs font-mono',
                trendPositive ? 'text-reaper-success' : 'text-reaper-danger'
              )}
            >
              {trendPositive ? (
                <TrendingUp className="w-3 h-3" />
              ) : (
                <TrendingDown className="w-3 h-3" />
              )}
              <span>{Math.abs(trend).toFixed(1)}%</span>
            </div>
          )}
        </div>
        <Counter
          value={value}
          decimals={decimals}
          suffix={suffix}
          className="text-2xl font-mono font-bold text-white"
        />
      </div>
    </AnimateIn>
  );
}
