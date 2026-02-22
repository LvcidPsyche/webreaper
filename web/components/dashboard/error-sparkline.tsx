'use client';

import { LineChart, Line, ResponsiveContainer } from 'recharts';

interface ErrorSparklineProps {
  data: number[];
  color?: string;
  height?: number;
}

export function ErrorSparkline({
  data,
  color = '#ff4444',
  height = 24,
}: ErrorSparklineProps) {
  const chartData = data.map((value, index) => ({ index, value }));

  return (
    <div style={{ height, width: 80 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={1.5}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
