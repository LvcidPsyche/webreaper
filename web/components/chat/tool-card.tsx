'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, Check, X, Wrench } from 'lucide-react';
import { clsx } from 'clsx';
import type { ChatMessage } from '@/lib/types';

interface ToolCardProps {
  message: ChatMessage;
  onApprove?: (id: string) => void;
  onDeny?: (id: string) => void;
}

export function ToolCard({ message, onApprove, onDeny }: ToolCardProps) {
  const [expanded, setExpanded] = useState(false);
  const isPending = message.tool_status === 'pending';

  const statusColor = {
    pending: 'text-reaper-warning',
    approved: 'text-reaper-success',
    denied: 'text-reaper-danger',
    completed: 'text-reaper-accent',
    error: 'text-reaper-danger',
  }[message.tool_status || 'pending'];

  return (
    <div className="bg-reaper-surface border border-reaper-border rounded-lg mb-2 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-reaper-border/30 transition-colors duration-150"
      >
        {expanded ? (
          <ChevronDown className="w-3 h-3 text-reaper-muted" />
        ) : (
          <ChevronRight className="w-3 h-3 text-reaper-muted" />
        )}
        <Wrench className="w-3 h-3 text-reaper-accent" />
        <span className="text-xs font-mono text-white flex-1">
          {message.tool_name}
        </span>
        <span className={clsx('text-[10px] font-mono uppercase', statusColor)}>
          {message.tool_status}
        </span>
      </button>

      {expanded && (
        <div className="px-3 pb-3 border-t border-reaper-border">
          {message.tool_params && (
            <div className="mt-2">
              <span className="text-[10px] font-mono text-reaper-muted uppercase">Params</span>
              <pre className="text-xs font-mono text-gray-400 mt-1 bg-reaper-bg p-2 rounded overflow-x-auto">
                {JSON.stringify(message.tool_params, null, 2)}
              </pre>
            </div>
          )}
          {message.tool_result && (
            <div className="mt-2">
              <span className="text-[10px] font-mono text-reaper-muted uppercase">Result</span>
              <pre className="text-xs font-mono text-gray-400 mt-1 bg-reaper-bg p-2 rounded overflow-x-auto max-h-32 overflow-y-auto">
                {message.tool_result}
              </pre>
            </div>
          )}
        </div>
      )}

      {isPending && (
        <div className="flex gap-2 px-3 pb-2">
          <button
            onClick={() => onApprove?.(message.id)}
            className="flex items-center gap-1 px-2 py-1 bg-reaper-success/10 text-reaper-success rounded text-xs font-mono hover:bg-reaper-success/20 transition-colors"
          >
            <Check className="w-3 h-3" /> Approve
          </button>
          <button
            onClick={() => onDeny?.(message.id)}
            className="flex items-center gap-1 px-2 py-1 bg-reaper-danger/10 text-reaper-danger rounded text-xs font-mono hover:bg-reaper-danger/20 transition-colors"
          >
            <X className="w-3 h-3" /> Deny
          </button>
        </div>
      )}
    </div>
  );
}
