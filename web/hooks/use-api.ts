'use client';

import { useState, useEffect, useCallback } from 'react';
import api from '@/lib/api';

interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

interface UseApiReturn<T> extends UseApiState<T> {
  refetch: () => Promise<void>;
  mutate: (data: T) => void;
}

export function useApi<T>(path: string, autoFetch = true): UseApiReturn<T> {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: autoFetch,
    error: null,
  });

  const fetch = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const data = await api.get<T>(path);
      setState({ data, loading: false, error: null });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Request failed';
      setState((prev) => ({ ...prev, loading: false, error: message }));
    }
  }, [path]);

  const mutate = useCallback((data: T) => {
    setState({ data, loading: false, error: null });
  }, []);

  useEffect(() => {
    if (autoFetch) fetch();
  }, [autoFetch, fetch]);

  return { ...state, refetch: fetch, mutate };
}

export function useApiPost<TReq, TRes>() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const post = useCallback(async (path: string, data: TReq): Promise<TRes | null> => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.post<TRes>(path, data);
      setLoading(false);
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Request failed';
      setError(message);
      setLoading(false);
      return null;
    }
  }, []);

  return { post, loading, error };
}
