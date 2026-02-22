'use client';

import { X, ExternalLink, Clock } from 'lucide-react';
import type { IntelligenceBrief } from '@/lib/types';

interface BriefViewerProps {
  brief: IntelligenceBrief | null;
  onClose: () => void;
}

export function BriefViewer({ brief, onClose }: BriefViewerProps) {
  if (!brief) return null;

  return (
    <div className="bg-reaper-surface border border-reaper-border rounded-lg flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-reaper-border">
        <h3 className="text-sm font-mono text-white truncate flex-1">{brief.title}</h3>
        <button
          onClick={onClose}
          className="text-reaper-muted hover:text-white ml-2 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div className="flex items-center gap-2 text-xs font-mono text-reaper-muted">
          <Clock className="w-3 h-3" />
          <span>{new Date(brief.created_at).toLocaleString()}</span>
        </div>

        <div>
          <span className="text-[10px] font-mono text-reaper-muted uppercase tracking-wider">
            Summary
          </span>
          <p className="text-sm font-mono text-gray-300 mt-1">{brief.summary}</p>
        </div>

        <div>
          <span className="text-[10px] font-mono text-reaper-muted uppercase tracking-wider">
            Content
          </span>
          <div className="text-sm font-mono text-gray-300 mt-1 whitespace-pre-wrap">
            {brief.content}
          </div>
        </div>

        {brief.sources.length > 0 && (
          <div>
            <span className="text-[10px] font-mono text-reaper-muted uppercase tracking-wider">
              Sources
            </span>
            <ul className="mt-1 space-y-1">
              {brief.sources.map((src, i) => (
                <li key={i} className="flex items-center gap-1">
                  <ExternalLink className="w-3 h-3 text-reaper-accent shrink-0" />
                  <a
                    href={src}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-mono text-reaper-accent hover:underline truncate"
                  >
                    {src}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex gap-1 flex-wrap">
          {brief.tags.map((tag) => (
            <span
              key={tag}
              className="text-[10px] font-mono bg-reaper-border px-1.5 py-0.5 rounded text-reaper-muted"
            >
              {tag}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
