'use client';

import { ChevronDown } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';
import { clsx } from 'clsx';
import type { AgentProvider } from '@/lib/types';

interface AgentPickerProps {
  providers: AgentProvider[];
  active: AgentProvider | null;
  onSelect: (id: string) => void;
}

export function AgentPicker({ providers, active, onSelect }: AgentPickerProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-1.5 bg-reaper-surface border border-reaper-border rounded text-xs font-mono text-white hover:border-reaper-accent/30 transition-colors"
      >
        <div
          className={clsx(
            'w-1.5 h-1.5 rounded-full',
            active?.status === 'connected' ? 'bg-reaper-success' : 'bg-reaper-danger'
          )}
        />
        <span>{active?.name || 'Select Agent'}</span>
        <ChevronDown className="w-3 h-3 text-reaper-muted" />
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 w-48 bg-reaper-surface border border-reaper-border rounded-lg shadow-xl z-50 py-1">
          {providers.map((p) => (
            <button
              key={p.id}
              onClick={() => { onSelect(p.id); setOpen(false); }}
              className={clsx(
                'w-full flex items-center gap-2 px-3 py-2 text-xs font-mono text-left hover:bg-reaper-border/50 transition-colors',
                p.id === active?.id ? 'text-reaper-accent' : 'text-white'
              )}
            >
              <div
                className={clsx(
                  'w-1.5 h-1.5 rounded-full',
                  p.status === 'connected' ? 'bg-reaper-success' : 'bg-reaper-danger'
                )}
              />
              <span>{p.name}</span>
              <span className="text-reaper-muted ml-auto">{p.model}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
