import { LeadRecord, ResearchRequest, ResearchResponse } from '../types/agent';

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
