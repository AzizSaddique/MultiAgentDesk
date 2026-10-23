import {
  LeadRecord,
  ResearchRequest,
  ResearchResponse,
  OutreachDraftRequest,
  OutreachDraftResponse,
  SendOutreachRequest,
  SendOutreachResponse,
  ProvidersResponse,
  OutreachHistoryResponse,
  HistoryFilterParams,
} from '../types/agent';

export interface HealthResponse {
  status: string;
  service: string;
  version?: string;
  provider?: string;
  demo_mode?: boolean;
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

/**
 * Execute lead research request via FastAPI backend.
 */
export async function searchLeads(request: ResearchRequest, timeoutMs: number = 15000): Promise<ResearchResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${BACKEND_BASE_URL}/api/research/leads`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(request),
      signal: controller.signal,
    });

    if (!response.ok) {
      let errorDetail = `Backend error (${response.status})`;
      try {
        const errorJson = await response.json();
        if (errorJson.detail) {
          if (typeof errorJson.detail === 'string') {
            errorDetail = errorJson.detail;
          } else if (Array.isArray(errorJson.detail)) {
            errorDetail = errorJson.detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ');
          }
        }
      } catch {
        // Fallback to text status
      }
      throw new Error(errorDetail);
    }

    const data: ResearchResponse = await response.json();
    return data;
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Research request timed out after 15 seconds.');
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Serializes and triggers browser/desktop CSV download for the provided lead records.
 * Uses FastAPI /api/research/export-csv with client-side fallback.
 */
export async function downloadLeadsCsv(leads: LeadRecord[]): Promise<void> {
  if (!leads || leads.length === 0) {
    throw new Error('No lead records to export.');
  }

  let csvContent = '';

  try {
    const response = await fetch(`${BACKEND_BASE_URL}/api/research/export-csv`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ leads }),
    });

    if (response.ok) {
      csvContent = await response.text();
    } else {
      throw new Error(`Export API returned status ${response.status}`);
    }
  } catch {
    // Client-side RFC 4180 CSV generation fallback
    const headers = [
      'ID',
      'Company Name',
      'Contact Name',
      'Contact Role',
      'Email',
      'Website',
      'Industry',
      'Location',
      'Source URL',
      'Description',
      'Verified Fields',
      'Source Note',
      'Created At',
    ];
    const escapeCsv = (val: string) => `"${(val || '').replace(/"/g, '""')}"`;
    const rows = leads.map((lead) =>
      [
        escapeCsv(lead.id),
        escapeCsv(lead.company_name),
        escapeCsv(lead.contact_name),
        escapeCsv(lead.contact_role),
        escapeCsv(lead.email),
        escapeCsv(lead.website),
        escapeCsv(lead.industry),
        escapeCsv(lead.location),
        escapeCsv(lead.source_url || ''),
        escapeCsv(lead.description || ''),
        escapeCsv(lead.verified_fields ? lead.verified_fields.join(', ') : ''),
        escapeCsv(lead.source_note),
        escapeCsv(lead.created_at),
      ].join(',')
    );
    csvContent = [headers.join(','), ...rows].join('\r\n');
  }

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `agentdesk_leads_${Date.now()}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Fetch available AI drafting providers and configuration options.
 */
export async function fetchAIProviders(): Promise<ProvidersResponse> {
  try {
    const response = await fetch(`${BACKEND_BASE_URL}/api/outreach/providers`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });
    if (!response.ok) {
      throw new Error(`Failed to fetch AI providers (${response.status})`);
    }
    return await response.json();
  } catch (err) {
    // Fallback to built-in provider if offline
    return {
      providers: [
        {
          id: 'template',
          name: 'Built-in Grounded Drafter',
          description: 'Deterministic, zero-leakage drafter using strictly verified public metadata. Fast & offline-ready.',
          requires_key: false,
          is_available: true,
        },
      ],
      dispatch: {
        mode: 'simulation',
        is_live: false,
        display_name: 'Simulation Mode (Safe Offline)',
        from_email: 'simulation@agentdesk.local',
        is_configured: true,
        notice: 'Simulation mode: No real emails are delivered.',
      },
    };
  }
}

/**
 * Request AI-powered personalized outreach drafting for selected leads.
 */
export async function draftOutreach(
  request: OutreachDraftRequest,
  timeoutMs: number = 30000
): Promise<OutreachDraftResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${BACKEND_BASE_URL}/api/outreach/draft`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(request),
      signal: controller.signal,
    });

    if (!response.ok) {
      let errorDetail = `Outreach drafting error (${response.status})`;
      try {
        const errorJson = await response.json();
        if (errorJson.detail) {
          errorDetail = typeof errorJson.detail === 'string'
            ? errorJson.detail
            : JSON.stringify(errorJson.detail);
        }
      } catch {
        // Fallback to status text
      }
      throw new Error(errorDetail);
    }

    return await response.json();
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('Outreach drafting request timed out after 30 seconds.');
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Dispatches outreach email through the human approval safety gate.
 * Requires approved === true and a genuine verified recipient email.
 */
export async function sendOutreach(request: SendOutreachRequest): Promise<SendOutreachResponse> {
  const response = await fetch(`${BACKEND_BASE_URL}/api/outreach/send`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    let errorDetail = `Outreach dispatch failed (${response.status})`;
    try {
      const errorJson = await response.json();
      if (errorJson.detail) {
        errorDetail = typeof errorJson.detail === 'string'
          ? errorJson.detail
          : JSON.stringify(errorJson.detail);
      }
    } catch {
      // Fallback
    }
    throw new Error(errorDetail);
  }

  return await response.json();
}

/**
 * Fetches outreach history with filtering, searching, and pagination.
 */
export async function fetchOutreachHistory(
  params: HistoryFilterParams = {},
  timeoutMs: number = 10000
): Promise<OutreachHistoryResponse> {
  const queryParts: string[] = [];
  if (params.status) queryParts.push(`status=${encodeURIComponent(params.status)}`);
  if (params.query) queryParts.push(`query=${encodeURIComponent(params.query)}`);
  if (params.start_date) queryParts.push(`start_date=${encodeURIComponent(params.start_date)}`);
  if (params.end_date) queryParts.push(`end_date=${encodeURIComponent(params.end_date)}`);
  if (params.page !== undefined) queryParts.push(`page=${params.page}`);
  if (params.page_size !== undefined) queryParts.push(`page_size=${params.page_size}`);

  const queryString = queryParts.length > 0 ? `?${queryParts.join('&')}` : '';
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${BACKEND_BASE_URL}/api/outreach/history${queryString}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
      signal: controller.signal,
    });

    if (!response.ok) {
      let detail = `Failed to fetch outreach history (${response.status})`;
      try {
        const errorJson = await response.json();
        if (errorJson.detail) detail = String(errorJson.detail);
      } catch {
        // use fallback
      }
      throw new Error(detail);
    }

    return await response.json();
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('History request timed out after 10 seconds.');
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Downloads outreach history as CSV, passing any active search/filter parameters.
 */
export async function downloadHistoryCsv(params: HistoryFilterParams = {}): Promise<void> {
  const queryParts: string[] = [];
  if (params.status) queryParts.push(`status=${encodeURIComponent(params.status)}`);
  if (params.query) queryParts.push(`query=${encodeURIComponent(params.query)}`);
  if (params.start_date) queryParts.push(`start_date=${encodeURIComponent(params.start_date)}`);
  if (params.end_date) queryParts.push(`end_date=${encodeURIComponent(params.end_date)}`);

  const queryString = queryParts.length > 0 ? `?${queryParts.join('&')}` : '';

  const response = await fetch(`${BACKEND_BASE_URL}/api/outreach/history/export-csv${queryString}`, {
    method: 'GET',
    headers: {
      'Accept': 'text/csv',
    },
  });

  if (!response.ok) {
    let detail = `Failed to export history CSV (${response.status})`;
    try {
      const err = await response.json();
      if (err.detail) detail = String(err.detail);
    } catch {
      // fallback
    }
    throw new Error(detail);
  }

  const csvContent = await response.text();
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `outreach_history_${Date.now()}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
