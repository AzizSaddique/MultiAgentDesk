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
  GlobeIcon,
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

const LIVE_SAMPLE_URLS = [
  { label: 'HttpBin HTML Fixture', url: 'https://httpbin.org/html' },
  { label: 'Example Domain', url: 'https://example.com' },
  { label: 'Wikipedia Foundation', url: 'https://www.wikipedia.org' },
];

export const AgentDetail: React.FC<AgentDetailProps> = ({ agent, backendStatus }) => {
  // Mode Selection: 'demo' (mock provider) vs 'live' (Playwright scraper)
  const [researchMode, setResearchMode] = useState<'demo' | 'live'>('demo');

  // Common Search Criteria
  const [topic, setTopic] = useState<string>('AI Workflow Automation');
  const [industry, setIndustry] = useState<string>('Software & IT');
  const [location, setLocation] = useState<string>('Austin, TX');
  const [maxResults, setMaxResults] = useState<number>(5);

  // Live Research Settings
  const [urlsInput, setUrlsInput] = useState<string>('https://httpbin.org/html');
  const [followLinks, setFollowLinks] = useState<boolean>(true);
  const [maxPagesPerDomain, setMaxPagesPerDomain] = useState<number>(2);

  // Execution & Display State
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
      message: 'Agent 1 initialized. Modular providers: MockResearchProvider & PlaywrightResearchProvider ready.',
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
      ...prev.slice(0, 24),
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

    let parsedUrls: string[] = [];
    if (researchMode === 'live') {
      parsedUrls = urlsInput
        .split('\n')
        .flatMap((line) => line.split(','))
        .map((u) => u.trim())
        .filter((u) => u.length > 0);

      if (parsedUrls.length === 0) {
        setFormError('Live research mode requires at least one public website URL (HTTP/HTTPS only).');
        return;
      }

      for (const u of parsedUrls) {
        if (!u.startsWith('http://') && !u.startsWith('https://')) {
          setFormError(`Invalid URL "${u}". All URLs must begin with http:// or https://`);
          return;
        }
      }
    }

    setFormError(null);
    setIsLoading(true);

    try {
      if (researchMode === 'live') {
        addAuditLog(
          'info',
          `Launching Playwright live research for ${parsedUrls.length} target URL(s) (follow links: ${followLinks})...`
        );
      } else {
        addAuditLog('info', `Running demo research simulation for "${cleanTopic}" in ${cleanLocation}...`);
      }

      const response = await searchLeads({
        topic: cleanTopic,
        industry: cleanIndustry,
        location: cleanLocation,
        max_results: maxResults,
        mode: researchMode,
        urls: parsedUrls,
        follow_links: followLinks,
        max_pages_per_domain: maxPagesPerDomain,
      });

      setLeads(response.leads);
      setLastResponse(response);

      if (response.is_demo) {
        addAuditLog(
          'success',
          `Generated ${response.leads.length} demo records via ${response.provider}. (Demo disclaimer attached).`
        );
      } else {
        const pagesCount = response.pages_crawled ?? 0;
        addAuditLog(
          'success',
          `Playwright live research complete: ${response.leads.length} verified records extracted across ${pagesCount} pages.`
        );
      }
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

  const appendLiveUrl = (url: string) => {
    if (!urlsInput.includes(url)) {
      setUrlsInput((prev) => (prev.trim() ? `${prev.trim()}\n${url}` : url));
    }
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
          <div className="card-header" style={{ marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <div style={{
                width: 28,
                height: 28,
                borderRadius: 6,
                background: researchMode === 'live' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(6, 182, 212, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                {researchMode === 'live' ? (
                  <GlobeIcon size={16} color="#34d399" />
                ) : (
                  <SearchIcon size={16} color="var(--accent-cyan)" />
                )}
              </div>
              <div>
                <h3 className="card-title" style={{ fontSize: '1rem' }}>
                  Lead Researcher Console
                </h3>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                  Active Provider:{' '}
                  <strong style={{ color: researchMode === 'live' ? '#34d399' : 'var(--accent-cyan)' }}>
                    {researchMode === 'live' ? 'Playwright Live Web Scraper' : 'Demo / Mock Research Provider'}
                  </strong>
                </span>
              </div>
            </div>

            {/* Provider Mode Switcher */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div className="mode-switch-group">
                <button
                  type="button"
                  className={`mode-switch-btn ${researchMode === 'demo' ? 'active' : ''}`}
                  onClick={() => {
                    setResearchMode('demo');
                    setFormError(null);
                  }}
                >
                  <SparklesIcon size={13} color={researchMode === 'demo' ? 'var(--accent-cyan)' : 'var(--text-muted)'} />
                  Demo Mode (Simulated)
                </button>
                <button
                  type="button"
                  className={`mode-switch-btn ${researchMode === 'live' ? 'active-live' : ''}`}
                  onClick={() => {
                    setResearchMode('live');
                    setFormError(null);
                  }}
                >
                  <GlobeIcon size={13} color={researchMode === 'live' ? '#34d399' : 'var(--text-muted)'} />
                  Live Web (Playwright)
                </button>
              </div>

              {backendStatus && !backendStatus.isOnline && (
                <span className="badge badge-warning" title="FastAPI backend service is currently offline on http://127.0.0.1:8000">
                  <AlertTriangleIcon size={12} color="#fbbf24" />
                  Backend Offline
                </span>
              )}
            </div>
          </div>

          {/* Mode-Specific Guidelines / Presets */}
          {researchMode === 'demo' ? (
            <div style={{ marginBottom: '1.2rem', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600 }}>Demo Presets:</span>
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
          ) : (
            <div style={{ marginBottom: '1.2rem', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600 }}>Sample Public URLs:</span>
              {LIVE_SAMPLE_URLS.map((sample, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="preset-chip"
                  onClick={() => appendLiveUrl(sample.url)}
                  disabled={isLoading}
                >
                  <GlobeIcon size={11} color="var(--accent-cyan)" />
                  <span>{sample.label}</span>
                </button>
              ))}
            </div>
          )}

          {/* Research Input Form */}
          <form onSubmit={handleRunResearch}>
            {researchMode === 'live' && (
              <div style={{ marginBottom: '1rem' }}>
                <div className="form-group">
                  <label className="form-label" htmlFor="live-urls-input">
                    <GlobeIcon size={13} color="#34d399" />
                    Target Public Website URLs (HTTP / HTTPS Only)
                  </label>
                  <textarea
                    id="live-urls-input"
                    className="form-input"
                    rows={3}
                    placeholder="Enter public URLs to scrape, separated by newlines or commas (e.g. https://httpbin.org/html, https://example.com)"
                    value={urlsInput}
                    onChange={(e) => setUrlsInput(e.target.value)}
                    disabled={isLoading}
                    style={{ resize: 'vertical', fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                    <span>Playwright will check robots.txt, extract visible company identity, and look for contact info.</span>
                    <span style={{ color: '#34d399' }}>Never fabricates missing details</span>
                  </div>
                </div>
              </div>
            )}

            <div className="grid-cols-3" style={{ gap: '1rem', marginBottom: '1rem' }}>
              <div className="form-group">
                <label className="form-label" htmlFor="topic-input">
                  <SearchIcon size={13} color="var(--accent-cyan)" />
                  Search Topic / Research Focus
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
                  Industry Sector
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
                  placeholder="e.g. Austin, TX, Berlin, London"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  disabled={isLoading}
                />
              </div>
            </div>

            {/* Live Mode Scraper Options */}
            {researchMode === 'live' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', marginBottom: '1rem', padding: '0.6rem 0.85rem', background: 'rgba(15, 23, 42, 0.45)', borderRadius: '8px', border: '1px solid var(--border-subtle)', flexWrap: 'wrap' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={followLinks}
                    onChange={(e) => setFollowLinks(e.target.checked)}
                    disabled={isLoading}
                    style={{ accentColor: 'var(--accent-cyan)' }}
                  />
                  <span>Follow on-domain subpages (e.g. /about, /contact)</span>
                </label>

                {followLinks && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <label htmlFor="max-pages-select" style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      Max Subpages per Domain:
                    </label>
                    <select
                      id="max-pages-select"
                      className="form-select"
                      value={maxPagesPerDomain}
                      onChange={(e) => setMaxPagesPerDomain(Number(e.target.value))}
                      disabled={isLoading}
                      style={{ padding: '0.25rem 0.5rem', fontSize: '0.72rem' }}
                    >
                      <option value={1}>1 Subpage</option>
                      <option value={2}>2 Subpages</option>
                      <option value={3}>3 Subpages</option>
                    </select>
                  </div>
                )}
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>
                  Strict robots.txt & polite 0.4s rate limiting enforced
                </span>
              </div>
            )}

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border-subtle)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <label htmlFor="max-results" style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    Record Limit:
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
                  {researchMode === 'live'
                    ? 'Playwright crawls target sites in headless Chromium'
                    : 'Simulated sample set generated by modular mock provider'}
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
                      {researchMode === 'live' ? 'Visiting Web Pages...' : 'Simulating Research...'}
                    </>
                  ) : (
                    <>
                      {researchMode === 'live' ? <GlobeIcon size={14} color="white" /> : <SearchIcon size={14} color="white" />}
                      {researchMode === 'live' ? 'Run Live Web Research' : 'Run Demo Pipeline'}
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
            {/* Mode-Specific Status Banner */}
            {lastResponse && (
              lastResponse.is_demo ? (
                /* Demo Notice Banner */
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
              ) : (
                /* Live Research Banner */
                <div className="live-banner" style={{ marginBottom: '1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <div style={{ width: 30, height: 30, borderRadius: 6, background: 'rgba(16, 185, 129, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <GlobeIcon size={16} color="#34d399" />
                    </div>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#34d399' }}>
                          LIVE PUBLIC WEB EXTRACTION (PLAYWRIGHT)
                        </span>
                        <span className="badge badge-active" style={{ fontSize: '0.65rem' }}>
                          Provider: {lastResponse.provider}
                        </span>
                        {lastResponse.pages_crawled !== undefined && (
                          <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                            {lastResponse.pages_crawled} pages visited
                          </span>
                        )}
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
                      <DownloadIcon size={13} color="#34d399" />
                      {isExporting ? 'Exporting...' : 'Export CSV'}
                    </button>
                  </div>
                </div>
              )
            )}

            {/* Loading State */}
            {isLoading ? (
              <div style={{
                background: 'rgba(10, 14, 23, 0.5)',
                border: '1px solid var(--border-active)',
                borderRadius: '8px',
                padding: '2.5rem 1.5rem',
                textAlign: 'center',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '0.75rem'
              }}>
                <div className="spinner" style={{ width: 24, height: 24, borderWidth: 3 }} />
                <div>
                  <p style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '0.9rem' }}>
                    {researchMode === 'live'
                      ? 'Executing Playwright Headless Web Scraper...'
                      : 'Executing Lead Research Pipeline...'}
                  </p>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                    {researchMode === 'live'
                      ? 'Checking robots.txt &bull; Navigating publicly accessible pages &bull; Extracting visible metadata'
                      : `Querying modular mock provider for "${topic.trim()}" • Synthesizing verified demo schemas`}
                  </p>
                </div>
              </div>
            ) : lastResponse && leads.length === 0 ? (
              /* Empty Results State */
              <div style={{
                background: 'rgba(245, 158, 11, 0.05)',
                border: '1px dashed rgba(245, 158, 11, 0.3)',
                borderRadius: '8px',
                padding: '2.25rem 1.5rem',
                textAlign: 'center',
                color: 'var(--text-secondary)'
              }}>
                <div style={{ width: 44, height: 44, borderRadius: 10, background: 'rgba(245, 158, 11, 0.15)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: '0.5rem' }}>
                  <AlertTriangleIcon size={22} color="#fbbf24" />
                </div>
                <h4 style={{ fontWeight: 700, color: '#fbbf24', fontSize: '0.92rem', marginBottom: '0.35rem' }}>
                  Zero Leads Found
                </h4>
                <p style={{ fontSize: '0.78rem', maxWidth: '480px', margin: '0 auto', color: 'var(--text-secondary)' }}>
                  No lead records could be extracted for topic <strong>&ldquo;{lastResponse.topic}&rdquo;</strong>.
                </p>
                <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>
                  {researchMode === 'live'
                    ? 'Check if the target URLs are publicly reachable, permissive in robots.txt, and contain visible company content.'
                    : 'Tip: Try broadening your search or click any of the Demo Presets above.'}
                </p>
              </div>
            ) : leads.length > 0 ? (
              /* Success / Results Table View */
              <div className="lead-table-container">
                <table className="lead-table">
                  <thead>
                    <tr>
                      <th style={{ width: '22%' }}>Company & Domain</th>
                      <th style={{ width: '20%' }}>Decision Maker & Email</th>
                      <th style={{ width: '24%' }}>Public Business Summary</th>
                      <th style={{ width: '18%' }}>Source Page URL</th>
                      <th style={{ width: '16%' }}>Extraction Verification</th>
                    </tr>
                  </thead>
                  <tbody>
                    {leads.map((lead) => (
                      <tr key={lead.id}>
                        <td>
                          <div className="lead-company">
                            <BuildingIcon size={14} color={lead.is_live ? '#34d399' : 'var(--accent-cyan)'} />
                            {lead.company_name}
                          </div>
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.3rem', marginTop: '0.15rem' }}>
                            <a
                              href={lead.website}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="lead-link"
                              onClick={(e) => {
                                if (lead.website.includes('.test') || lead.website.includes('.example.com')) {
                                  e.preventDefault();
                                }
                              }}
                            >
                              <span>{lead.website.replace(/^https?:\/\/(www\.)?/, '')}</span>
                              <ExternalLinkIcon size={10} color="var(--accent-cyan)" />
                            </a>
                          </div>
                        </td>
                        <td>
                          <div className="lead-contact">
                            <UserIcon size={12} color="var(--text-secondary)" style={{ display: 'inline', marginRight: 4, verticalAlign: 'middle' }} />
                            {lead.contact_name}
                          </div>
                          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: lead.email.includes('@') ? '#38bdf8' : 'var(--text-muted)', marginTop: '0.15rem' }}>
                            {lead.email}
                          </div>
                        </td>
                        <td>
                          <div style={{ fontSize: '0.73rem', color: 'var(--text-secondary)', lineHeight: 1.35, maxHeight: '3.6em', overflow: 'hidden' }}>
                            {lead.description || lead.source_note}
                          </div>
                        </td>
                        <td>
                          {lead.source_url && lead.source_url.startsWith('http') ? (
                            <a
                              href={lead.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="lead-link"
                              style={{ fontSize: '0.72rem', fontFamily: 'var(--font-mono)' }}
                              onClick={(e) => {
                                if (lead.source_url?.includes('.test')) e.preventDefault();
                              }}
                            >
                              <span>{lead.source_url.replace(/^https?:\/\//, '').slice(0, 24)}...</span>
                              <ExternalLinkIcon size={11} color="var(--accent-cyan)" />
                            </a>
                          ) : (
                            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                              {lead.source_url || 'simulated://mock'}
                            </span>
                          )}
                        </td>
                        <td>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                            <span className={lead.is_live ? 'badge badge-active' : 'badge badge-cyan'} style={{ fontSize: '0.62rem', alignSelf: 'flex-start' }}>
                              {lead.is_live ? 'Live Public Web' : 'Simulated Sample'}
                            </span>
                            {lead.verified_fields && lead.verified_fields.length > 0 && (
                              <div style={{ display: 'flex', gap: '0.2rem', flexWrap: 'wrap' }}>
                                {lead.verified_fields.slice(0, 3).map((vf, idx) => (
                                  <span key={idx} className="tag-verified">
                                    {vf}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              /* Initial Welcome / Ready View */
              <div style={{
                background: 'rgba(10, 14, 23, 0.4)',
                border: '1px dashed var(--border-subtle)',
                borderRadius: '8px',
                padding: '2.5rem 1.5rem',
                textAlign: 'center',
                color: 'var(--text-muted)'
              }}>
                {researchMode === 'live' ? (
                  <GlobeIcon size={32} color="var(--border-subtle)" />
                ) : (
                  <SearchIcon size={32} color="var(--border-subtle)" />
                )}
                <p style={{ marginTop: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                  {researchMode === 'live' ? 'Ready for Live Public-Web Research' : 'No lead records generated yet'}
                </p>
                <p style={{ fontSize: '0.75rem', maxWidth: '440px', margin: '0.35rem auto 0 auto' }}>
                  {researchMode === 'live'
                    ? 'Enter target public URLs above or click a Sample Public URL to launch the Playwright headless web scraper.'
                    : 'Enter your search criteria above and click Run Demo Pipeline to simulate lead extraction.'}
                </p>
              </div>
            )}

            {/* Crawl Diagnostics & Skipped Pages Panel */}
            {lastResponse && lastResponse.diagnostics && lastResponse.diagnostics.length > 0 && (
              <div className="diagnostics-box">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <AlertTriangleIcon size={13} color="#fbbf24" />
                    Crawl Diagnostics & Page Audit ({lastResponse.diagnostics.length})
                  </span>
                  <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    Robots.txt & Error Trace
                  </span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', fontSize: '0.72rem' }}>
                  {lastResponse.diagnostics.map((diag, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '0.35rem 0.6rem',
                        background: 'rgba(10, 14, 23, 0.5)',
                        borderRadius: '4px',
                        border: '1px solid rgba(148, 163, 184, 0.08)'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflow: 'hidden' }}>
                        <span className={diag.status === 'success' ? 'badge badge-active' : 'badge badge-warning'} style={{ fontSize: '0.62rem' }}>
                          {diag.status}
                        </span>
                        <span style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', maxWidth: '280px' }}>
                          {diag.url}
                        </span>
                      </div>
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>
                        {diag.reason}
                      </span>
                    </div>
                  ))}
                </div>
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
              <span className="badge badge-active">Playwright Active</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.78rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0.65rem', background: 'rgba(15, 23, 42, 0.5)', borderRadius: '6px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Live Web Engine:</span>
                <span style={{ color: '#34d399', fontFamily: 'var(--font-mono)' }}>Playwright (Chromium Headless)</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0.65rem', background: 'rgba(15, 23, 42, 0.5)', borderRadius: '6px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Demo Provider:</span>
                <span style={{ color: '#38bdf8', fontFamily: 'var(--font-mono)' }}>MockResearchProvider (Simulated)</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0.65rem', background: 'rgba(15, 23, 42, 0.5)', borderRadius: '6px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Robots.txt & Ethics:</span>
                <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>Strict robotparser Enforcement</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0.65rem', background: 'rgba(15, 23, 42, 0.5)', borderRadius: '6px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Export Engine:</span>
                <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>RFC 4180 CSV + Source URLs</span>
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
