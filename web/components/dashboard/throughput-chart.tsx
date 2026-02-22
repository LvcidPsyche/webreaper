'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { AnimateIn } from '@/components/shared/animate-in';
import type { ThroughputPoint } from '@/lib/types';

interface ThroughputChartProps {
  data: ThroughputPoint[];
}

function formatTime(timestamp: string): string {
  const d = new Date(timestamp);
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
}

export function ThroughputChart({ data }: ThroughputChartProps) {
  const chartData = data.map((p) => ({
    time: formatTime(p.timestamp),
    value: p.pages_per_second,
  }));

  return (
    <AnimateIn delay={0.1}>
      <div className="bg-reaper-surface border border-reaper-border rounded-lg p-4">
        <h3 className="text-xs font-mono text-reaper-muted uppercase tracking-wider mb-4">
          Throughput (pages/sec)
        </h3>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid stroke="#1e1e2e" strokeDasharray="3 3" />
              <XAxis
                dataKey="time"
                tick={{ fill: '#666680', fontSize: 10, fontFamily: 'monospace' }}
                axisLine={{ stroke: '#1e1e2e' }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: '#666680', fontSize: 10, fontFamily: 'monospace' }}
                axisLine={{ stroke: '#1e1e2e' }}
                tickLine={false}
                width={40}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#12121a',
                  border: '1px solid #1e1e2e',
                  borderRadius: 6,
                  fontFamily: 'monospace',
                  fontSize: 12,
                }}
                labelStyle={{ color: '#666680' }}
                itemStyle={{ color: '#00d4ff' }}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#00d4ff"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3, fill: '#00d4ff' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </AnimateIn>
  );
}
