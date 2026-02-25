'use client';

import { useState, useEffect, useCallback } from 'react';
import { useWebSocket } from './use-websocket';
import { useApi } from './use-api';
import api from '@/lib/api';
import type { AgentProvider, ChatMessage } from '@/lib/types';

interface UseAgentReturn {
  providers: AgentProvider[];
  activeProvider: AgentProvider | null;
  connected: boolean;
  messages: ChatMessage[];
  sendMessage: (content: string) => void;
  approveToolCall: (messageId: string) => void;
  denyToolCall: (messageId: string) => void;
  selectProvider: (id: string) => void;
  loadingProviders: boolean;
  typing: boolean;
}

export function useAgent(): UseAgentReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeProviderId, setActiveProviderId] = useState<string | null>(null);
  const [typing, setTyping] = useState(false);

  const { data: providers, loading: loadingProviders } = useApi<AgentProvider[]>('/api/agents');

  const onMessage = useCallback((data: unknown) => {
    const msg = data as Partial<ChatMessage>;
    if (typeof msg.id === 'string' && typeof msg.role === 'string') {
      if (msg.role === 'agent') {
        setTyping((msg.content ?? '').length === 0);
      } else {
        setTyping(false);
      }
      setMessages((prev) => {
        const idx = prev.findIndex((m) => m.id === msg.id);
        if (idx >= 0) {
          const updated = [...prev];
          updated[idx] = msg as ChatMessage;
          return updated;
        }
        return [...prev, msg as ChatMessage];
      });
    }
  }, []);

  const { connected, send } = useWebSocket({
    path: '/ws/chat',
    onMessage,
    autoConnect: true,
  });

  const activeProvider = providers?.find((p) => p.id === activeProviderId) ?? providers?.[0] ?? null;

  useEffect(() => {
    if (providers?.length && !activeProviderId) {
      setActiveProviderId(providers[0].id);
    }
  }, [providers, activeProviderId]);

  const sendMessage = useCallback((content: string) => {
    const msg: Partial<ChatMessage> = {
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };
    send({ type: 'chat_message', ...msg, provider_id: activeProviderId });
    setTyping(true);
    setMessages((prev) => [
      ...prev,
      { ...msg, id: `local-${Date.now()}` } as ChatMessage,
    ]);
  }, [send, activeProviderId]);

  const approveToolCall = useCallback((messageId: string) => {
    send({ type: 'tool_approve', message_id: messageId });
  }, [send]);

  const denyToolCall = useCallback((messageId: string) => {
    send({ type: 'tool_deny', message_id: messageId });
  }, [send]);

  const selectProvider = useCallback((id: string) => {
    setActiveProviderId(id);
    api.post(`/api/agents/${id}/activate`).catch(() => {
      // Activation errors are non-fatal; gateway may not be running
    });
  }, []);

  return {
    providers: providers ?? [],
    activeProvider,
    connected,
    messages,
    sendMessage,
    approveToolCall,
    denyToolCall,
    selectProvider,
    loadingProviders,
    typing,
  };
}
