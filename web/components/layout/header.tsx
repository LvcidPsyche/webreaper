'use client';

import { Activity } from 'lucide-react';
import { clsx } from 'clsx';

interface HeaderProps {
  agentConnected: boolean;
}

export function Header({ agentConnected }: HeaderProps) {
  return (
    <header className="h-12 bg-reaper-surface border-b border-reaper-border flex items-center justify-between px-4">
      <div className="flex items-center gap-2">
        <Activity className="w-4 h-4 text-reaper-accent" />
        <span className="font-mono text-sm text-white">WebReaper v2.0</span>
      </div>

      <div className="flex items-center gap-2">
        <div
          className={clsx(
            'w-2 h-2 rounded-full',
            agentConnected ? 'bg-reaper-success animate-pulse-soft' : 'bg-reaper-danger'
          )}
        />
        <span className="font-mono text-xs text-reaper-muted">
          {agentConnected ? 'Agent Connected' : 'Disconnected'}
        </span>
      </div>
    </header>
  );
}
