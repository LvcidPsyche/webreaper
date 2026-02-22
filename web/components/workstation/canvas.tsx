'use client';

import { useState } from 'react';
import { Pin, X, FileText } from 'lucide-react';
import { clsx } from 'clsx';
import type { IntelligenceBrief } from '@/lib/types';

interface CanvasProps {
  briefs: IntelligenceBrief[];
  onSelect: (brief: IntelligenceBrief) => void;
  onPin?: (id: string) => void;
  onRemove?: (id: string) => void;
}

export function Canvas({ briefs, onSelect, onPin, onRemove }: CanvasProps) {
  const [pinnedIds, setPinnedIds] = useState<Set<string>>(new Set());

  const handlePin = (id: string) => {
    setPinnedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    onPin?.(id);
  };

  const pinned = briefs.filter((b) => pinnedIds.has(b.id));
  const unpinned = briefs.filter((b) => !pinnedIds.has(b.id));
  const sorted = [...pinned, ...unpinned];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
      {sorted.length === 0 && (
        <div className="col-span-full flex items-center justify-center py-12 text-reaper-muted font-mono text-sm">
          No intelligence briefs yet
        </div>
      )}
      {sorted.map((brief) => (
        <div
          key={brief.id}
          onClick={() => onSelect(brief)}
          className={clsx(
            'bg-reaper-surface border rounded-lg p-3 cursor-pointer hover:border-reaper-accent/30 transition-colors duration-150',
            pinnedIds.has(brief.id) ? 'border-reaper-accent/40' : 'border-reaper-border'
          )}
        >
          <div className="flex items-start justify-between mb-2">
            <div className="flex items-center gap-2">
              <FileText className="w-3.5 h-3.5 text-reaper-accent" />
              <span className="text-sm font-mono text-white truncate">{brief.title}</span>
            </div>
            <div className="flex gap-1">
              <button
                onClick={(e) => { e.stopPropagation(); handlePin(brief.id); }}
                className={clsx(
                  'p-1 rounded transition-colors',
                  pinnedIds.has(brief.id) ? 'text-reaper-accent' : 'text-reaper-muted hover:text-white'
                )}
              >
                <Pin className="w-3 h-3" />
              </button>
              {onRemove && (
                <button
                  onClick={(e) => { e.stopPropagation(); onRemove(brief.id); }}
                  className="p-1 text-reaper-muted hover:text-reaper-danger rounded transition-colors"
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>
          </div>
          <p className="text-xs font-mono text-reaper-muted line-clamp-2">{brief.summary}</p>
          <div className="flex gap-1 mt-2 flex-wrap">
            {brief.tags.slice(0, 3).map((tag) => (
              <span key={tag} className="text-[10px] font-mono bg-reaper-border px-1.5 py-0.5 rounded text-reaper-muted">
                {tag}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
