/**
 * AgentDesk Backend API Client & Health Monitoring
 */

export interface HealthResponse {
  status: string;
  service: string;
  version?: string;
}

export const BACKEND_BASE_URL = 'http://127.0.0.1:8000';

export async function fetchHealth(timeoutMs: number = 2500): Promise<HealthResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${BACKEND_BASE_URL}/health`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Health check returned status ${response.status}`);
    }

    const data: HealthResponse = await response.json();
    return data;
  } finally {
    clearTimeout(timeoutId);
  }
}
