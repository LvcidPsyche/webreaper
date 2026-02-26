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
      <div className="ghost-panel p-4">
        <h3 className="ghost-label mb-4">HTTP Status</h3>
        <div className="flex items-center gap-4">
          <div className="h-32 w-32 shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data}
                  innerRadius={30}
                  outerRadius={50}
                  paddingAngle={2}
                  dataKey="value"
                  strokeWidth={0}
                  isAnimationActive={false}
                >
                  {data.map((entry, i) => (
                    <Cell key={i} fill={entry.color} stroke="transparent" />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#080b12',
                    border: '1px solid #141c28',
                    borderRadius: 2,
                    fontFamily: 'Share Tech Mono, monospace',
                    fontSize: 11,
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-col gap-1.5 min-w-0">
            {data.map((entry) => (
              <div key={entry.name} className="flex items-center gap-2 text-[10px] font-mono">
                <div className="w-1.5 h-1.5 shrink-0" style={{ backgroundColor: entry.color }} />
                <span className="text-ghost-dim">{entry.name}</span>
                <span className="text-ghost-text ml-auto pl-2">
                  {total > 0 ? ((entry.value / total) * 100).toFixed(0) : 0}%
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AnimateIn>
  );
}
