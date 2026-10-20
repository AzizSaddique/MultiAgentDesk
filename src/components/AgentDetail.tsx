import React, { useState } from 'react';
import { AgentModel, LeadRecord, ResearchResponse } from '../types/agent';
import { BackendStatus } from '../hooks/useBackendStatus';
import { searchLeads, downloadLeadsCsv } from '../services/api';
import {
  SearchIcon,
  FileSpreadsheetIcon,
  ShieldAlertIcon,
  CheckCircleIcon,
  TerminalIcon,
  DownloadIcon,
  RefreshCwIcon,
  ExternalLinkIcon,
  BuildingIcon,
  MapPinIcon,
  UserIcon,
  SparklesIcon,
  AlertTriangleIcon,
} from './icons';

interface AgentDetailProps {
  agent: AgentModel;
  backendStatus?: BackendStatus;
}

interface AuditEntry {
  id: string;
  timestamp: string;
  type: 'success' | 'error' | 'info';
  message: string;
}

const PRESET_QUERIES = [
  { topic: 'AI Workflow Automation', industry: 'Software & IT', location: 'Austin, TX' },
  { topic: 'Renewable Storage & Grid', industry: 'CleanTech', location: 'Denver, CO' },
  { topic: 'Digital Therapeutics', industry: 'HealthTech', location: 'Boston, MA' },
  { topic: 'Cross-Border Payments', industry: 'FinTech', location: 'London, UK' },
];

export const AgentDetail: React.FC<AgentDetailProps> = ({ agent, backendStatus }) => {
  // Research Form State
  const [topic, setTopic] = useState<string>('AI Workflow Automation');
  const [industry, setIndustry] = useState<string>('Software & IT');
  const [location, setLocation] = useState<string>('Austin, TX');
  const [maxResults, setMaxResults] = useState<number>(5);

  // Workflow Execution State
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [leads, setLeads] = useState<LeadRecord[]>([]);
  const [lastResponse, setLastResponse] = useState<ResearchResponse | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditEntry[]>([
    {
      id: 'init-1',
      timestamp: new Date().toLocaleTimeString(),
      type: 'info',
      message: 'Agent 1 initialized with Mock / Demo Research Provider.',
    },
  ]);

  const addAuditLog = (type: 'success' | 'error' | 'info', message: string) => {
    setAuditLogs((prev) => [
      {
        id: `audit-${Date.now()}-${Math.random()}`,
        timestamp: new Date().toLocaleTimeString(),
        type,
        message,
      },
      ...prev.slice(0, 19), // Keep latest 20
    ]);
  };

  const handleRunResearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();

    const cleanTopic = topic.trim();
    const cleanIndustry = industry.trim();
    const cleanLocation = location.trim();

    if (cleanTopic.length < 2) {
      setFormError('Search topic must be at least 2 characters.');
      return;
    }
    if (cleanIndustry.length < 2) {
      setFormError('Industry sector must be at least 2 characters.');
      return;
    }
    if (cleanLocation.length < 2) {
      setFormError('Location must be at least 2 characters.');
      return;
    }

    setFormError(null);
    setIsLoading(true);

    try {
      addAuditLog('info', `Starting research run for "${cleanTopic}" in ${cleanLocation} (${cleanIndustry})...`);
      
      const response = await searchLeads({
        topic: cleanTopic,
        industry: cleanIndustry,
        location: cleanLocation,
        max_results: maxResults,
      });

      setLeads(response.leads);
      setLastResponse(response);
      addAuditLog(
        'success',
        `Generated ${response.leads.length} demo records via ${response.provider}. (Demo disclaimer attached).`
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error during research';
      setFormError(msg);
      addAuditLog('error', `Research run failed: ${msg}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExportCsv = async () => {
    if (leads.length === 0) return;
    setIsExporting(true);
    try {
      await downloadLeadsCsv(leads);
      addAuditLog('success', `Exported ${leads.length} records to agentdesk_leads.csv`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to export CSV';
      setFormError(msg);
      addAuditLog('error', `CSV Export failed: ${msg}`);
    } finally {
      setIsExporting(false);
    }
  };

  const applyPreset = (preset: typeof PRESET_QUERIES[0]) => {
    setTopic(preset.topic);
    setIndustry(preset.industry);
    setLocation(preset.location);
    setFormError(null);
  };

  const isAgentOne = agent.id === 'agent-1';

  return (
    <div className="dashboard-viewport">
      {/* Top Banner / Hero */}
      <div className="card" style={{ background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.9), rgba(30, 41, 59, 0.7))', borderColor: 'var(--border-active)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '0.4rem' }}>
              <span className="badge badge-cyan">{agent.category}</span>
              <span className="badge badge-active">
                <span className="badge-dot" />
                {isAgentOne ? 'Workflow Operational' : 'Pipeline Staged'}
              </span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>v{agent.version}</span>
            </div>
            <h2 style={{ fontSize: '1.4rem', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '0.5rem' }}>
              {agent.name}
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', maxWidth: '780px' }}>
              {agent.description}
            </p>
          </div>

          {isAgentOne && (
            <div style={{ display: 'flex', gap: '0.65rem' }}>
              <button
                className={`btn btn-secondary ${leads.length === 0 || isExporting ? 'disabled' : ''}`}
                onClick={handleExportCsv}
                disabled={leads.length === 0 || isExporting}
                title="Export current lead table into standard RFC 4180 CSV"
              >
                <FileSpreadsheetIcon size={14} color="var(--accent-cyan)" />
                {isExporting ? 'Exporting...' : `Export CSV (${leads.length})`}
              </button>
              <button
                className="btn btn-primary"
                onClick={() => handleRunResearch()}
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <div className="spinner" />
                    Running...
                  </>
                ) : (
                  <>
                    <SearchIcon size={14} color="white" />
                    Launch Research Run
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Safety Gate Banner */}
      <div style={{
        background: 'rgba(6, 182, 212, 0.06)',
        border: '1px solid rgba(6, 182, 212, 0.25)',
        borderRadius: '10px',
        padding: '0.9rem 1.25rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '1rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ width: 34, height: 34, borderRadius: 8, background: 'rgba(6, 182, 212, 0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <ShieldAlertIcon size={18} color="var(--accent-cyan)" />
          </div>
          <div>
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Strict Approval Policy: Zero Autonomous Outbound Transmission
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
              Every email draft generated by Agent 1 requires explicit manual approval. No emails will ever send without direct operator confirmation.
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--bg-secondary)', padding: '0.4rem 0.8rem', borderRadius: '8px', border: '1px solid var(--border-subtle)', whiteSpace: 'nowrap' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Pending Drafts:</span>
          <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>0</span>
        </div>
      </div>

      {/* Agent 1 Interactive Research Console */}
      {isAgentOne && (
        <div className="card">
          <div className="card-header" style={{ marginBottom: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <div style={{
                width: 28,
                height: 28,
                borderRadius: 6,
                background: 'rgba(6, 182, 212, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <SearchIcon size={16} color="var(--accent-cyan)" />
              </div>
              <div>
                <h3 className="card-title" style={{ fontSize: '1rem' }}>
                  Lead Researcher Query Console
                </h3>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                  Configured Provider: <strong style={{ color: 'var(--accent-cyan)' }}>Demo / Mock Research Provider</strong> (Modular Playwright scraper slot)
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              {backendStatus && !backendStatus.isOnline && (
                <span className="badge badge-warning" title="FastAPI backend service is currently offline on http://127.0.0.1:8000">
                  <AlertTriangleIcon size={12} color="#fbbf24" />
                  Backend Offline
                </span>
              )}
              <span className="badge badge-cyan">
                <SparklesIcon size={12} color="var(--accent-cyan)" />
                Demo Mode Active
              </span>
            </div>
          </div>

          {/* Quick Presets */}
          <div style={{ marginBottom: '1.2rem', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600 }}>Quick Presets:</span>
            {PRESET_QUERIES.map((preset, idx) => (
              <button
                key={idx}
                type="button"
                className="preset-chip"
                onClick={() => applyPreset(preset)}
                disabled={isLoading}
              >
                <span>{preset.topic}</span>
                <span style={{ color: 'var(--text-muted)' }}>({preset.location})</span>
              </button>
            ))}
          </div>

          {/* Input Form */}
          <form onSubmit={handleRunResearch}>
            <div className="grid-cols-3" style={{ gap: '1rem', marginBottom: '1rem' }}>
              <div className="form-group">
                <label className="form-label" htmlFor="topic-input">
                  <SearchIcon size={13} color="var(--accent-cyan)" />
                  Search Topic / Niche Keyword
                </label>
                <input
                  id="topic-input"
                  type="text"
                  className="form-input"
                  placeholder="e.g. AI Workflow Automation, Medical SaaS"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  disabled={isLoading}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="industry-input">
                  <BuildingIcon size={13} color="var(--accent-indigo)" />
                  Target Industry Sector
                </label>
                <input
                  id="industry-input"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Software & IT, CleanTech, Healthcare"
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                  disabled={isLoading}
                />
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="location-input">
                  <MapPinIcon size={13} color="var(--status-active)" />
                  Geographic Location / Market
                </label>
                <input
                  id="location-input"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Austin, TX, Berlin, Germany, London"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  disabled={isLoading}
                />
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border-subtle)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <label htmlFor="max-results" style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    Sample Limit:
                  </label>
                  <select
                    id="max-results"
                    className="form-select"
                    value={maxResults}
                    onChange={(e) => setMaxResults(Number(e.target.value))}
                    disabled={isLoading}
                    style={{ padding: '0.35rem 0.65rem' }}
                  >
                    <option value={3}>3 Records</option>
                    <option value={5}>5 Records</option>
                    <option value={8}>8 Records</option>
                  </select>
                </div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  (Simulated sample set generated by modular backend provider)
                </span>
              </div>

              <div style={{ display: 'flex', gap: '0.65rem' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    setLeads([]);
                    setLastResponse(null);
                    setFormError(null);
                  }}
                  disabled={isLoading || leads.length === 0}
                >
                  <RefreshCwIcon size={13} color="var(--text-secondary)" />
                  Clear Results
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <>
                      <div className="spinner" />
                      Researching Leads...
                    </>
                  ) : (
                    <>
                      <SearchIcon size={14} color="white" />
                      Run Research Pipeline
                    </>
                  )}
                </button>
              </div>
            </div>

            {formError && (
              <div style={{ marginTop: '1rem', background: 'rgba(239, 68, 68, 0.12)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '8px', padding: '0.65rem 0.9rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.78rem', color: '#fca5a5' }}>
                <AlertTriangleIcon size={16} color="#f87171" />
                <span>{formError}</span>
              </div>
            )}
          </form>

          {/* Research Results Display */}
          <div style={{ marginTop: '1.5rem', paddingTop: '1.25rem', borderTop: '1px solid var(--border-subtle)' }}>
            {/* Demo Notice Banner */}
            {lastResponse && (
              <div className="demo-banner" style={{ marginBottom: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <div style={{ width: 30, height: 30, borderRadius: 6, background: 'rgba(245, 158, 11, 0.18)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <SparklesIcon size={16} color="#fbbf24" />
                  </div>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#fbbf24' }}>
                        DEMO / SIMULATED RECORDS
                      </span>
                      <span className="badge badge-warning" style={{ fontSize: '0.65rem' }}>
                        Provider: {lastResponse.provider}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.73rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
                      {lastResponse.disclaimer}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <button
                    className="btn btn-secondary"
                    onClick={handleExportCsv}
                    disabled={isExporting}
                    style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem' }}
                  >
                    <DownloadIcon size={13} color="var(--accent-cyan)" />
                    {isExporting ? 'Exporting...' : 'Export CSV'}
                  </button>
                </div>
              </div>
            )}

            {/* Results Table or Empty State */}
            {leads.length > 0 ? (
              <div className="lead-table-container">
                <table className="lead-table">
                  <thead>
                    <tr>
                      <th style={{ width: '22%' }}>Company & Sector</th>
                      <th style={{ width: '20%' }}>Decision Maker</th>
                      <th style={{ width: '20%' }}>Contact Email</th>
                      <th style={{ width: '18%' }}>Domain & Website</th>
                      <th style={{ width: '20%' }}>Sample Data Verification</th>
                    </tr>
                  </thead>
                  <tbody>
                    {leads.map((lead) => (
                      <tr key={lead.id}>
                        <td>
                          <div className="lead-company">
                            <BuildingIcon size={14} color="var(--accent-cyan)" />
                            {lead.company_name}
                          </div>
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.3rem', marginTop: '0.15rem' }}>
                            <MapPinIcon size={11} color="var(--text-muted)" />
                            {lead.location} • {lead.industry}
                          </div>
                        </td>
                        <td>
                          <div className="lead-contact">
                            <UserIcon size={13} color="var(--text-secondary)" style={{ display: 'inline', marginRight: 4, verticalAlign: 'middle' }} />
                            {lead.contact_name}
                          </div>
                          <div className="lead-role">{lead.contact_role}</div>
                        </td>
                        <td>
                          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.74rem', color: '#38bdf8' }}>
                            {lead.email}
                          </div>
                        </td>
                        <td>
                          <a
                            href={lead.website}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="lead-link"
                            title="Mock demo website link"
                            onClick={(e) => e.preventDefault()}
                          >
                            <span>{lead.website.replace('https://www.', '')}</span>
                            <ExternalLinkIcon size={12} color="var(--accent-cyan)" />
                          </a>
                        </td>
                        <td>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                            <span className="badge badge-cyan" style={{ fontSize: '0.65rem', alignSelf: 'flex-start' }}>
                              Simulated Lead
                            </span>
                            <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                              {lead.id}
                            </span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{
                background: 'rgba(10, 14, 23, 0.4)',
                border: '1px dashed var(--border-subtle)',
                borderRadius: '8px',
                padding: '2.5rem 1.5rem',
                textAlign: 'center',
                color: 'var(--text-muted)'
              }}>
                <SearchIcon size={32} color="var(--border-subtle)" />
                <p style={{ marginTop: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                  No lead records generated yet
                </p>
                <p style={{ fontSize: '0.75rem', maxWidth: '420px', margin: '0.35rem auto 0 auto' }}>
                  Enter your search criteria above and click <strong>Run Research Pipeline</strong> to simulate lead extraction and test the CSV export.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Workflow Stages & Architecture */}
      <div className="grid-cols-2">
        {/* Responsibilities / Workflow pipeline */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">
              <SearchIcon size={16} color="var(--accent-cyan)" />
              Agent 1 Core Responsibilities & Pipeline
            </h3>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>7 Stages</span>
          </div>

          <div className="stages-list">
            {agent.stages.map((stage) => (
              <div key={stage.id} className="stage-card">
                <div className="stage-num">0{stage.id}</div>
                <div className="stage-body">
                  <div className="stage-title">{stage.title}</div>
                  <div className="stage-detail">{stage.description}</div>
                </div>
                <div style={{ alignSelf: 'center' }}>
                  {stage.id <= 3 ? (
                    <span className="badge badge-active" style={{ fontSize: '0.62rem' }}>Working</span>
                  ) : stage.id <= 5 ? (
                    <span className="badge badge-cyan" style={{ fontSize: '0.62rem' }}>Staged</span>
                  ) : stage.id === 6 ? (
                    <span className="badge badge-warning" style={{ fontSize: '0.62rem' }}>Gate</span>
                  ) : (
                    <span className="badge badge-disabled" style={{ fontSize: '0.62rem' }}>Audit</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Column: Execution Engine & Data Interfaces */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Engine Configuration */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">
                <TerminalIcon size={16} color="var(--accent-indigo)" />
                Target Orchestration Architecture
              </h3>
              <span className="badge badge-cyan">Phase 1 Modular</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.78rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0.65rem', background: 'rgba(15, 23, 42, 0.5)', borderRadius: '6px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Research Provider:</span>
                <span style={{ color: '#38bdf8', fontFamily: 'var(--font-mono)' }}>MockResearchProvider (Demo Mode)</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0.65rem', background: 'rgba(15, 23, 42, 0.5)', borderRadius: '6px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Future Web Engine:</span>
                <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>Playwright (Python Async Worker)</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0.65rem', background: 'rgba(15, 23, 42, 0.5)', borderRadius: '6px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Agent Backend:</span>
                <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>FastAPI Sidecar (http://127.0.0.1:8000)</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0.65rem', background: 'rgba(15, 23, 42, 0.5)', borderRadius: '6px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Export Engine:</span>
                <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>RFC 4180 CSV & XLSX Stream</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0.65rem', background: 'rgba(15, 23, 42, 0.5)', borderRadius: '6px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Outbound Approval:</span>
                <span style={{ color: '#fbbf24', fontFamily: 'var(--font-mono)' }}>Strict Human Review Gate</span>
              </div>
            </div>
          </div>

          {/* Activity Log / Failure Audit Card */}
          <div className="card" style={{ flex: 1 }}>
            <div className="card-header">
              <h3 className="card-title">
                <CheckCircleIcon size={16} color="var(--status-active)" />
                Activity & Failure Audit Log
              </h3>
              <span className="badge badge-active">{auditLogs.length} Events</span>
            </div>

            <div style={{
              background: '#050810',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
              padding: '0.75rem',
              minHeight: '140px',
              maxHeight: '220px',
              overflowY: 'auto',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.72rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.4rem'
            }}>
              {auditLogs.map((log) => (
                <div key={log.id} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
                  <span style={{ color: 'var(--text-muted)' }}>[{log.timestamp}]</span>
                  <span style={{
                    color: log.type === 'success' ? '#34d399' : log.type === 'error' ? '#f87171' : 'var(--accent-cyan)',
                    fontWeight: 600
                  }}>
                    {log.type.toUpperCase()}:
                  </span>
                  <span style={{ color: 'var(--text-secondary)' }}>{log.message}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
