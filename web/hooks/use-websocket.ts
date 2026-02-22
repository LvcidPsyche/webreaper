'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { WebSocketClient } from '@/lib/ws';

interface UseWebSocketOptions {
  path: string;
  onMessage?: (data: unknown) => void;
  autoConnect?: boolean;
}

interface UseWebSocketReturn {
  connected: boolean;
  send: (data: unknown) => void;
  connect: () => void;
  disconnect: () => void;
}

export function useWebSocket({
  path,
  onMessage,
  autoConnect = true,
}: UseWebSocketOptions): UseWebSocketReturn {
  const clientRef = useRef<WebSocketClient | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const client = new WebSocketClient(path);
    clientRef.current = client;

    client.on('_connected', () => setConnected(true));
    client.on('_disconnected', () => setConnected(false));

    if (onMessage) {
      client.on('_message', onMessage);
    }

    if (autoConnect) client.connect();

    return () => {
      client.disconnect();
      clientRef.current = null;
    };
  }, [path, autoConnect]);

  useEffect(() => {
    if (!clientRef.current || !onMessage) return;
    return clientRef.current.on('_message', onMessage);
  }, [onMessage]);

  const send = useCallback((data: unknown) => {
    clientRef.current?.send(data);
  }, []);

  const connect = useCallback(() => {
    clientRef.current?.connect();
  }, []);

  const disconnect = useCallback(() => {
    clientRef.current?.disconnect();
  }, []);

  return { connected, send, connect, disconnect };
}
