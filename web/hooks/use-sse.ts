'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { SSE_BASE_URL } from '@/lib/constants';

interface UseSSEOptions<T> {
  path: string;
  onEvent?: (data: T) => void;
  autoConnect?: boolean;
}

interface UseSSEReturn {
  connected: boolean;
  connect: () => void;
  disconnect: () => void;
}

export function useSSE<T = unknown>({
  path,
  onEvent,
  autoConnect = true,
}: UseSSEOptions<T>): UseSSEReturn {
  const sourceRef = useRef<EventSource | null>(null);
  const [connected, setConnected] = useState(false);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const connect = useCallback(() => {
    if (sourceRef.current) sourceRef.current.close();

    const url = `${SSE_BASE_URL}${path}`;
    const source = new EventSource(url);
    sourceRef.current = source;

    source.onopen = () => setConnected(true);

    source.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as T;
        onEventRef.current?.(data);
      } catch {
        onEventRef.current?.(event.data as T);
      }
    };

    source.onerror = () => {
      setConnected(false);
      source.close();
      setTimeout(() => {
        if (sourceRef.current === source) connect();
      }, 3000);
    };
  }, [path]);

  const disconnect = useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
    setConnected(false);
  }, []);

  useEffect(() => {
    if (autoConnect) connect();
    return () => disconnect();
  }, [autoConnect, connect, disconnect]);

  return { connected, connect, disconnect };
}
