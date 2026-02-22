'use client';

import { clsx } from 'clsx';

interface SkeletonProps {
  className?: string;
  width?: string | number;
  height?: string | number;
  rounded?: boolean;
}

export function Skeleton({ className, width, height, rounded }: SkeletonProps) {
  return (
    <div
      className={clsx(
        'animate-pulse bg-reaper-border skeleton-shimmer',
        rounded ? 'rounded-full' : 'rounded',
        className
      )}
      style={{ width, height }}
    />
  );
}

export function SkeletonCard() {
  return (
    <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4 space-y-3">
      <Skeleton height={16} width="60%" />
      <Skeleton height={32} width="40%" />
      <Skeleton height={12} width="80%" />
    </div>
  );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      <div className="flex gap-4 pb-2 border-b border-reaper-border">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} height={14} className="flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4 py-2">
          {[1, 2, 3, 4].map((j) => (
            <Skeleton key={j} height={12} className="flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}
