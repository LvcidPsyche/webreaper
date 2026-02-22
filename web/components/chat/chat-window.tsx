'use client';

import { useRef, useEffect, useState } from 'react';
import { Send } from 'lucide-react';
import { Message } from './message';
import { ToolCard } from './tool-card';
import type { ChatMessage } from '@/lib/types';

interface ChatWindowProps {
  messages: ChatMessage[];
  onSend: (content: string) => void;
  onApproveToolCall?: (id: string) => void;
  onDenyToolCall?: (id: string) => void;
  connected: boolean;
  typing?: boolean;
}

export function ChatWindow({
  messages,
  onSend,
  onApproveToolCall,
  onDenyToolCall,
  connected,
  typing = false,
}: ChatWindowProps) {
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, typing]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    onSend(text);
    setInput('');
  };

  return (
    <div className="flex flex-col h-full">
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-1">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-reaper-muted font-mono text-sm">
            Start a conversation with the agent
          </div>
        )}
        {messages.map((msg) =>
          msg.role === 'tool' ? (
            <ToolCard
              key={msg.id}
              message={msg}
              onApprove={onApproveToolCall}
              onDeny={onDenyToolCall}
            />
          ) : (
            <Message key={msg.id} message={msg} />
          )
        )}
        {typing && (
          <div className="flex gap-1 px-3 py-2">
            <div className="w-1.5 h-1.5 bg-reaper-accent rounded-full animate-pulse-soft" />
            <div className="w-1.5 h-1.5 bg-reaper-accent rounded-full animate-pulse-soft" style={{ animationDelay: '0.2s' }} />
            <div className="w-1.5 h-1.5 bg-reaper-accent rounded-full animate-pulse-soft" style={{ animationDelay: '0.4s' }} />
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="border-t border-reaper-border p-3 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={connected ? 'Type a message...' : 'Agent disconnected'}
          disabled={!connected}
          className="flex-1 bg-reaper-bg border border-reaper-border rounded px-3 py-2 text-sm font-mono text-white placeholder:text-reaper-muted focus:border-reaper-accent outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={!connected || !input.trim()}
          className="px-3 py-2 bg-reaper-accent/10 text-reaper-accent border border-reaper-accent/30 rounded hover:bg-reaper-accent/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}
