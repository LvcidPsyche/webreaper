'use client';

import { useState } from 'react';
import { Plug, Settings } from 'lucide-react';
import { ChatWindow } from '@/components/chat/chat-window';
import { AgentPicker } from '@/components/chat/agent-picker';
import { ConnectModal } from '@/components/chat/connect-modal';
import { AnimateIn } from '@/components/shared/animate-in';
import { useAgent } from '@/hooks/use-agent';
import api from '@/lib/api';

export default function ChatPage() {
  const {
    providers,
    activeProvider,
    connected,
    messages,
    sendMessage,
    approveToolCall,
    denyToolCall,
    selectProvider,
    typing,
  } = useAgent();

  const [showConnect, setShowConnect] = useState(false);

  const handleConnect = async (config: {
    name: string;
    type: string;
    base_url: string;
    api_key: string;
    model: string;
  }) => {
    try {
      const provider = await api.post<{ id: string }>('/api/agents', config);
      if (provider?.id) {
        selectProvider(provider.id);
      }
    } catch {
      // errors surface via the agent status indicator
    }
  };

  return (
    <AnimateIn className="h-[calc(100vh-8rem)] flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <AgentPicker
            providers={providers}
            active={activeProvider}
            onSelect={selectProvider}
          />
          <div className="flex items-center gap-1.5 text-xs font-mono">
            <div
              className={`w-1.5 h-1.5 rounded-full ${
                connected ? 'bg-reaper-success animate-pulse-soft' : 'bg-reaper-danger'
              }`}
            />
            <span className="text-reaper-muted">
              {connected ? 'Live' : 'Disconnected'}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowConnect(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-reaper-surface border border-reaper-border rounded text-xs font-mono text-reaper-muted hover:text-white hover:border-reaper-accent/30 transition-colors"
          >
            <Plug className="w-3 h-3" />
            Connect
          </button>
        </div>
      </div>

      <div className="flex-1 bg-reaper-surface border border-reaper-border rounded-lg overflow-hidden">
        <ChatWindow
          messages={messages}
          onSend={sendMessage}
          onApproveToolCall={approveToolCall}
          onDenyToolCall={denyToolCall}
          connected={connected}
          typing={typing}
        />
      </div>

      <ConnectModal
        open={showConnect}
        onClose={() => setShowConnect(false)}
        onConnect={handleConnect}
      />
    </AnimateIn>
  );
}
