export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000';
export const SSE_BASE_URL = process.env.NEXT_PUBLIC_SSE_URL ?? 'http://localhost:8000';

export const SEVERITY_COLORS: Record<string, string> = {
  critical: '#ff4444',
  high: '#ff8800',
  medium: '#ffaa00',
  low: '#666680',
  info: '#00d4ff',
};

export const STATUS_COLORS: Record<string, string> = {
  '2xx': '#00ff88',
  '3xx': '#00d4ff',
  '4xx': '#ffaa00',
  '5xx': '#ff4444',
};

export const LOG_LEVEL_COLORS: Record<string, string> = {
  error: '#ff4444',
  warn: '#ffaa00',
  warning: '#ffaa00',
  info: '#00d4ff',
  debug: '#666680',
};
