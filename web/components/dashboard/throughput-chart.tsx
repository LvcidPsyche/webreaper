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
      <div className="ghost-panel p-4">
        <h3 className="ghost-label mb-4">Throughput — pages/sec</h3>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid stroke="#0e1520" strokeDasharray="2 4" />
              <XAxis
                dataKey="time"
                tick={{ fill: '#3d6080', fontSize: 9, fontFamily: 'Share Tech Mono, monospace' }}
                axisLine={{ stroke: '#141c28' }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: '#3d6080', fontSize: 9, fontFamily: 'Share Tech Mono, monospace' }}
                axisLine={{ stroke: '#141c28' }}
                tickLine={false}
                width={32}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#080b12',
                  border: '1px solid #141c28',
                  borderRadius: 2,
                  fontFamily: 'Share Tech Mono, monospace',
                  fontSize: 11,
                }}
                labelStyle={{ color: '#3d6080' }}
                itemStyle={{ color: '#39ff14' }}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke="#39ff14"
                strokeWidth={1.5}
                isAnimationActive={false}
                dot={false}
                activeDot={{ r: 2, fill: '#39ff14', stroke: 'none' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </AnimateIn>
  );
}
