import {
  LeadRecord,
  ResearchRequest,
  ResearchResponse,
  OutreachDraftRequest,
  OutreachDraftResponse,
  SendOutreachRequest,
  SendOutreachResponse,
  ProvidersResponse,
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

