'use client';

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
    <footer className="h-7 bg-ghost-bg border-t border-ghost-border flex items-center px-4 gap-5 shrink-0">
      <span className="text-[10px] font-mono text-ghost-label uppercase tracking-widest">
        PAGES{' '}
        <Counter value={pagesCrawled} className="text-ghost-text" />
      </span>

      <span className="text-ghost-border select-none">·</span>

      <span className="text-[10px] font-mono text-ghost-label uppercase tracking-widest">
        UP <span className="text-ghost-text">{formatUptime(uptimeSeconds)}</span>
      </span>

      <span className="ml-auto flex items-center gap-1.5">
        <span className={connected ? 'live-dot' : 'w-1.5 h-1.5 rounded-full bg-ghost-red inline-block'} />
        <span className={`text-[10px] font-mono uppercase tracking-widest ${connected ? 'text-ghost-green' : 'text-ghost-red'}`}>
          {connected ? 'connected' : 'offline'}
        </span>
      </span>
    </footer>
  );
}
