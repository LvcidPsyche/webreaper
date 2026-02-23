'use client';

import { clsx } from 'clsx';

interface HeaderProps {
  agentConnected: boolean;
}

export function Header({ agentConnected }: HeaderProps) {
  return (
    <header className="h-10 bg-ghost-surface border-b border-ghost-border flex items-center justify-between px-4 shrink-0">
      {/* Terminal prompt */}
      <div className="flex items-center gap-1 text-xs font-mono">
        <span className="text-ghost-green">▸</span>
        <span className="text-ghost-dim">webreaper</span>
        <span className="text-ghost-label">@</span>
        <span className="text-ghost-dim">sigint</span>
        <span className="text-ghost-label">:~$</span>
        <span className="text-ghost-text ml-1 cursor-blink">_</span>
      </div>

      {/* Connection status */}
      <div className="flex items-center gap-2">
        {agentConnected ? (
          <>
            <span className="live-dot" />
            <span className="text-[10px] font-mono uppercase tracking-widest text-ghost-green">Live</span>
          </>
        ) : (
          <>
            <span className="w-1.5 h-1.5 rounded-full bg-ghost-red" />
            <span className="text-[10px] font-mono uppercase tracking-widest text-ghost-red">Offline</span>
          </>
        )}
      </div>
    </header>
  );
}
