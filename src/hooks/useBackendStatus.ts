import { useState, useEffect, useCallback } from 'react';
import { fetchHealth, HealthResponse } from '../services/api';

export interface BackendStatus {
  isOnline: boolean;
  isLoading: boolean;
  data: HealthResponse | null;
  error: string | null;
  checkHealth: () => Promise<void>;
}

export function useBackendStatus(pollIntervalMs: number = 4000): BackendStatus {
  const [isOnline, setIsOnline] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [data, setData] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const checkHealth = useCallback(async () => {
    try {
      const result = await fetchHealth(2000);
      setIsOnline(true);
      setData(result);
      setError(null);
    } catch (err: unknown) {
      setIsOnline(false);
      setData(null);
      setError(err instanceof Error ? err.message : 'Backend offline');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, pollIntervalMs);
    return () => clearInterval(interval);
  }, [checkHealth, pollIntervalMs]);

  return { isOnline, isLoading, data, error, checkHealth };
}
