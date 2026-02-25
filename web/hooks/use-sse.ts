'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import { SSE_BASE_URL } from '@/lib/constants';

export type SSEConnectionStatus = 'idle' | 'connecting' | 'connected' | 'reconnecting';

interface UseSSEOptions<T> {
  path: string;
  onEvent?: (data: T) => void;
  autoConnect?: boolean;
  eventNames?: string | string[];
  reconnectDelayMs?: number;
  maxReconnectDelayMs?: number;
  onStatusChange?: (status: SSEConnectionStatus) => void;
}

interface UseSSEReturn {
  connected: boolean;
  status: SSEConnectionStatus;
  reconnectAttempts: number;
  connect: () => void;
  disconnect: () => void;
}

type SSEEnvelope<T> = {
  type?: string;
  ts?: string;
  payload?: T;
};

function inferEventNames(path: string): string[] {
  if (path.startsWith('/stream/metrics')) return ['metrics'];
  if (path.startsWith('/stream/logs')) return ['log'];
  if (path.startsWith('/stream/job/')) return ['progress', 'error'];
  return [];
}

function parseEventData<T>(raw: string): T {
  const parsed = JSON.parse(raw) as T | SSEEnvelope<T>;
  if (
    parsed &&
    typeof parsed === 'object' &&
    'payload' in parsed &&
    (('type' in parsed) || ('ts' in parsed))
  ) {
    return (parsed as SSEEnvelope<T>).payload as T;
  }
  return parsed as T;
}

export function useSSE<T = unknown>({
  path,
  onEvent,
  autoConnect = true,
  eventNames,
  reconnectDelayMs = 3000,
  maxReconnectDelayMs = 15000,
  onStatusChange,
}: UseSSEOptions<T>): UseSSEReturn {
  const sourceRef = useRef<EventSource | null>(null);
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState<SSEConnectionStatus>('idle');
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const onEventRef = useRef(onEvent);
  const onStatusChangeRef = useRef(onStatusChange);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const manualDisconnectRef = useRef(false);
  onEventRef.current = onEvent;
  onStatusChangeRef.current = onStatusChange;

  const setConnectionStatus = useCallback((next: SSEConnectionStatus) => {
    setStatus(next);
    onStatusChangeRef.current?.(next);
  }, []);

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    manualDisconnectRef.current = false;
    clearReconnectTimer();
    if (sourceRef.current) sourceRef.current.close();

    const url = `${SSE_BASE_URL}${path}`;
    const source = new EventSource(url);
    sourceRef.current = source;
    setConnectionStatus(reconnectAttemptsRef.current > 0 ? 'reconnecting' : 'connecting');

    const handleParsedEvent = (event: MessageEvent<string>) => {
      try {
        const data = parseEventData<T>(event.data);
        onEventRef.current?.(data);
      } catch {
        onEventRef.current?.(event.data as T);
      }
    };

    source.onopen = () => {
      reconnectAttemptsRef.current = 0;
      setReconnectAttempts(0);
      setConnected(true);
      setConnectionStatus('connected');
    };

    source.onmessage = handleParsedEvent;

    const normalizedEventNames = Array.isArray(eventNames)
      ? eventNames
      : eventNames
        ? [eventNames]
        : inferEventNames(path);

    normalizedEventNames.forEach((name) => {
      source.addEventListener(name, (event) => {
        handleParsedEvent(event as MessageEvent<string>);
      });
    });

    source.onerror = () => {
      setConnected(false);
      if (manualDisconnectRef.current) {
        setConnectionStatus('idle');
        return;
      }
      reconnectAttemptsRef.current += 1;
      setReconnectAttempts(reconnectAttemptsRef.current);
      setConnectionStatus('reconnecting');
      source.close();
      const delay = Math.min(
        reconnectDelayMs * Math.max(1, reconnectAttemptsRef.current),
        maxReconnectDelayMs,
      );
      reconnectTimerRef.current = setTimeout(() => {
        if (sourceRef.current === source) connect();
      }, delay);
    };
  }, [clearReconnectTimer, eventNames, maxReconnectDelayMs, path, reconnectDelayMs, setConnectionStatus]);

  const disconnect = useCallback(() => {
    manualDisconnectRef.current = true;
    clearReconnectTimer();
    sourceRef.current?.close();
    sourceRef.current = null;
    setConnected(false);
    reconnectAttemptsRef.current = 0;
    setReconnectAttempts(0);
    setConnectionStatus('idle');
  }, [clearReconnectTimer, setConnectionStatus]);

  useEffect(() => {
    if (autoConnect) connect();
    return () => disconnect();
  }, [autoConnect, connect, disconnect]);

  return { connected, status, reconnectAttempts, connect, disconnect };
}
