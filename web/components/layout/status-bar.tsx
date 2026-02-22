'use client';

import { Wifi, WifiOff, Clock, FileText } from 'lucide-react';
import { Counter } from '@/components/shared/counter';

interface StatusBarProps {
  pagesCrawled: number;
  uptimeSeconds: number;
  connected: boolean;
}

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

export function StatusBar({ pagesCrawled, uptimeSeconds, connected }: StatusBarProps) {
  return (
    <footer className="h-8 bg-reaper-surface border-t border-reaper-border flex items-center px-4 gap-6 text-xs font-mono">
      <div className="flex items-center gap-1.5 text-reaper-muted">
        <FileText className="w-3 h-3" />
        <span>Pages: </span>
        <Counter value={pagesCrawled} className="text-white" />
      </div>

      <div className="flex items-center gap-1.5 text-reaper-muted">
        <Clock className="w-3 h-3" />
        <span>Uptime: </span>
        <span className="text-white">{formatUptime(uptimeSeconds)}</span>
      </div>

      <div className="flex items-center gap-1.5 ml-auto">
        {connected ? (
          <>
            <Wifi className="w-3 h-3 text-reaper-success" />
            <span className="text-reaper-success">Connected</span>
          </>
        ) : (
          <>
            <WifiOff className="w-3 h-3 text-reaper-danger" />
            <span className="text-reaper-danger">Disconnected</span>
          </>
        )}
      </div>
    </footer>
  );
}
