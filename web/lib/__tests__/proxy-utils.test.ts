import { describe, expect, it } from 'vitest';
import { filterProxyHistory, mergeInterceptQueueUpdate } from '../proxy-utils';

describe('proxy-utils', () => {
  const rows = [
    { id: '1', method: 'GET', host: 'example.com', intercept_state: 'queued' },
    { id: '2', method: 'POST', host: 'api.example.com', intercept_state: 'forwarded' },
    { id: '3', method: 'POST', host: 'test.com', intercept_state: 'queued' },
  ];

  it('filters by method/host/queued state', () => {
    expect(filterProxyHistory(rows, { methodFilter: 'POST' })).toHaveLength(2);
    expect(filterProxyHistory(rows, { hostFilter: 'example.com' })).toHaveLength(2);
    expect(filterProxyHistory(rows, { queuedOnly: true })).toHaveLength(2);
    expect(filterProxyHistory(rows, { methodFilter: 'POST', queuedOnly: true })).toEqual([rows[2]]);
  });

  it('merges queue updates for live handling', () => {
    const merged = mergeInterceptQueueUpdate(rows, { id: '2', intercept_state: 'queued', method: 'POST', host: 'api.example.com' });
    expect(merged.find((r) => r.id === '2')?.intercept_state).toBe('queued');
    const inserted = mergeInterceptQueueUpdate(rows, { id: '9', method: 'GET', host: 'new.example', intercept_state: 'queued' });
    expect(inserted[0].id).toBe('9');
  });
});
