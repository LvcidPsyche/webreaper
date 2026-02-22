'use client';

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { AnimateIn } from '@/components/shared/animate-in';
import { STATUS_COLORS } from '@/lib/constants';

interface StatusDonutProps {
  statusCodes: Record<string, number>;
}

export function StatusDonut({ statusCodes }: StatusDonutProps) {
  const data = Object.entries(statusCodes).map(([key, value]) => ({
    name: key,
    value,
    color: STATUS_COLORS[key] || '#666680',
  }));

  const total = data.reduce((sum, d) => sum + d.value, 0);

  return (
    <AnimateIn delay={0.15}>
      <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
        <h3 className="text-xs font-mono text-reaper-muted uppercase tracking-wider mb-4">
          Status Distribution
        </h3>
        <div className="flex items-center gap-4">
          <div className="h-36 w-36">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data}
                  innerRadius={35}
                  outerRadius={55}
                  paddingAngle={2}
                  dataKey="value"
                >
                  {data.map((entry, i) => (
                    <Cell key={i} fill={entry.color} stroke="transparent" />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#12121a',
                    border: '1px solid #1e1e2e',
                    borderRadius: 6,
                    fontFamily: 'monospace',
                    fontSize: 12,
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-col gap-2">
            {data.map((entry) => (
              <div key={entry.name} className="flex items-center gap-2 text-xs font-mono">
                <div
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: entry.color }}
                />
                <span className="text-reaper-muted">{entry.name}</span>
                <span className="text-white">
                  {entry.value} ({total > 0 ? ((entry.value / total) * 100).toFixed(0) : 0}%)
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AnimateIn>
  );
}
