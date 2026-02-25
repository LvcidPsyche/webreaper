export interface ProxyTxLike {
  id: string;
  method?: string | null;
  host?: string | null;
  intercept_state?: string | null;
}

export interface ProxyFilterState {
  methodFilter?: string;
  hostFilter?: string;
  queuedOnly?: boolean;
}

export function filterProxyHistory<T extends ProxyTxLike>(items: T[], filters: ProxyFilterState): T[] {
  const method = (filters.methodFilter || '').trim().toUpperCase();
  const host = (filters.hostFilter || '').trim().toLowerCase();
  return (items || []).filter((tx) => {
    if (filters.queuedOnly && (tx.intercept_state || '') !== 'queued') return false;
    if (method && (tx.method || '').toUpperCase() !== method) return false;
    if (host && !String(tx.host || '').toLowerCase().includes(host)) return false;
    return true;
  });
}

export function mergeInterceptQueueUpdate<T extends ProxyTxLike>(items: T[], updated: T): T[] {
  const next = [...(items || [])];
  const idx = next.findIndex((x) => x.id === updated.id);
  if (idx >= 0) next[idx] = { ...next[idx], ...updated };
  else next.unshift(updated);
  return next;
}
