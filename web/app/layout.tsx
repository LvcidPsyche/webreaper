'use client';

import { useState, useCallback } from 'react';
import './globals.css';
import { Sidebar } from '@/components/layout/sidebar';
import { Header } from '@/components/layout/header';
import { StatusBar } from '@/components/layout/status-bar';
import { useSSE } from '@/hooks/use-sse';
import type { MetricsSnapshot } from '@/lib/types';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [metrics, setMetrics] = useState<MetricsSnapshot | null>(null);

  const handleMetrics = useCallback((data: MetricsSnapshot) => {
    setMetrics(data);
  }, []);

  const { connected } = useSSE<MetricsSnapshot>({
    path: '/stream/metrics',
    eventNames: 'metrics',
    onEvent: handleMetrics,
  });

  return (
    <html lang="en" className="dark">
      <body className="bg-ghost-bg text-ghost-text antialiased">
        <div className="flex h-screen overflow-hidden">
          <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
          <div className="flex flex-col flex-1 min-w-0">
            <Header agentConnected={connected} />
            <main className="flex-1 overflow-y-auto p-4">{children}</main>
            <StatusBar
              pagesCrawled={metrics?.pages_crawled ?? 0}
              uptimeSeconds={metrics?.uptime_seconds ?? 0}
              connected={connected}
            />
          </div>
        </div>
      </body>
    </html>
  );
}
