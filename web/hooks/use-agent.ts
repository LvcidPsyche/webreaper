'use client';

import { useState, useEffect, useCallback } from 'react';
import { useWebSocket } from './use-websocket';
import { useApi } from './use-api';
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
}

export function useAgent(): UseAgentReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeProviderId, setActiveProviderId] = useState<string | null>(null);

  const { data: providers, loading: loadingProviders } = useApi<AgentProvider[]>('/api/agents');

  const onMessage = useCallback((data: unknown) => {
    const msg = data as ChatMessage;
    if (msg.id && msg.role) {
      setMessages((prev) => {
        const idx = prev.findIndex((m) => m.id === msg.id);
        if (idx >= 0) {
          const updated = [...prev];
          updated[idx] = msg;
          return updated;
        }
        return [...prev, msg];
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
  };
}
