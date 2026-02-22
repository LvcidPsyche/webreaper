'use client';

import { clsx } from 'clsx';
import { User, Bot } from 'lucide-react';
import type { ChatMessage } from '@/lib/types';

interface MessageProps {
  message: ChatMessage;
}

export function Message({ message }: MessageProps) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  if (isSystem) {
    return (
      <div className="flex justify-center my-2">
        <span className="text-xs font-mono text-reaper-muted bg-reaper-border/50 px-3 py-1 rounded-full">
          {message.content}
        </span>
      </div>
    );
  }

  return (
    <div
      className={clsx('flex gap-2 mb-3', isUser ? 'flex-row-reverse' : 'flex-row')}
    >
      <div
        className={clsx(
          'w-7 h-7 rounded flex items-center justify-center shrink-0',
          isUser ? 'bg-reaper-accent/20' : 'bg-reaper-surface'
        )}
      >
        {isUser ? (
          <User className="w-3.5 h-3.5 text-reaper-accent" />
        ) : (
          <Bot className="w-3.5 h-3.5 text-reaper-success" />
        )}
      </div>
      <div
        className={clsx(
          'max-w-[75%] rounded-lg px-3 py-2 text-sm font-mono',
          isUser
            ? 'bg-reaper-accent/10 text-white border border-reaper-accent/20'
            : 'bg-reaper-surface text-gray-300 border border-reaper-border'
        )}
      >
        <div className="whitespace-pre-wrap break-words">{message.content}</div>
        <div className="text-[10px] text-reaper-muted mt-1">
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}
