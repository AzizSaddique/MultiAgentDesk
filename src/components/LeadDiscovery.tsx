import React, { useState, useEffect, useCallback } from 'react';
import {
  DiscoveryPlan,
  DiscoveryJob,
  DiscoveredLeadRecord,
  SearchProviderInfo,
} from '../types/agent';
import {
  generateDiscoveryPlan,
  fetchSearchProviders,
  createDiscoveryJob,
  fetchDiscoveryJob,
  cancelDiscoveryJob,
  fetchDiscoveredLeads,
  downloadDiscoveredLeadsCsv,
  transferLeadsToOutreach,
} from '../services/api';
import { BackendStatus } from '../hooks/useBackendStatus';
import {
  CompassIcon,
  SearchIcon,
  CheckCircleIcon,
  AlertTriangleIcon,
  DownloadIcon,
  RefreshCwIcon,
  ExternalLinkIcon,
  MapPinIcon,
  PhoneIcon,
  CheckIcon,
  XIcon,
  EyeIcon,
  StopCircleIcon,
  SendIcon,
  SparklesIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from './icons';

interface LeadDiscoveryProps {
  backendStatus?: BackendStatus;
  onNavigateToOutreach?: () => void;
}

const EXAMPLE_PROMPTS = [
  "Find 100 solar installation companies in Lahore that serve commercial customers.",
  "Find software houses in Pakistan that might need IoT development services.",
  "Discover manufacturing companies in Saudi Arabia and collect their official websites and publicly listed business contact emails.",
  "Find robotics and automation companies in Germany that could be potential clients.",
];

const DEFAULT_SEARCH_PROVIDERS: SearchProviderInfo[] = [
  {
    id: 'auto',
    name: 'Auto-Select Best Available',
    description: 'Automatically routes to highest priority configured provider.',
    is_configured: true,
    requires_key: false,
    notice: 'Active route: Automatic Provider Selection',
  },
  {
    id: 'tavily',
    name: 'Tavily Search API',
    description: 'Official Tavily AI Search API optimized for agent discovery, clean web extracts, and factual company sources.',
    is_configured: false,
    requires_key: true,
    notice: 'Requires TAVILY_API_KEY in root .env.',
  },
  {
    id: 'google',
    name: 'Google Custom Search API',
    description: 'Official Google Custom Search JSON API for high-precision company website discovery.',
    is_configured: false,
    requires_key: true,
    notice: 'Requires GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID in root .env.',
  },
  {
    id: 'bing',
    name: 'Bing Web Search API',
    description: 'Official Azure Cognitive Services Bing Web Search v7.0 API for web business discovery.',
    is_configured: false,
    requires_key: true,
    notice: 'Requires BING_SEARCH_API_KEY in root .env.',
  },
  {
    id: 'directory',
    name: 'Public Business Directory',
    description: 'Built-in public trade registries, verified corporate databases, and offline testing directory.',
    is_configured: true,
    requires_key: false,
    notice: 'Built-in directory. Zero API keys required.',
  },
];

export const LeadDiscovery: React.FC<LeadDiscoveryProps> = ({
  backendStatus,
  onNavigateToOutreach,
}) => {
  // Natural-Language Input State
  const [prompt, setPrompt] = useState<string>(EXAMPLE_PROMPTS[0]);
  const [isInterpreting, setIsInterpreting] = useState<boolean>(false);
  const [plan, setPlan] = useState<DiscoveryPlan | null>(null);

  // Search Provider State
  const [providers, setProviders] = useState<SearchProviderInfo[]>(DEFAULT_SEARCH_PROVIDERS);
  const [selectedProvider, setSelectedProvider] = useState<string>('auto');

  // Active Job & Telemetry State
  const [activeJob, setActiveJob] = useState<DiscoveryJob | null>(null);
  const [isStartingJob, setIsStartingJob] = useState<boolean>(false);
  const [isCancelling, setIsCancelling] = useState<boolean>(false);

  // Discovered Leads Table State
  const [leads, setLeads] = useState<DiscoveredLeadRecord[]>([]);
  const [totalLeads, setTotalLeads] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [pageSize] = useState<number>(15);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [verificationCounts, setVerificationCounts] = useState<Record<string, number>>({});
  const [isLoadingLeads, setIsLoadingLeads] = useState<boolean>(false);

  // Table Filters
  const [searchFilter, setSearchFilter] = useState<string>('');
  const [emailStatusFilter, setEmailStatusFilter] = useState<string>('');
  const [selectedLeadIds, setSelectedLeadIds] = useState<Set<string>>(new Set());

  // Evidence Detail Modal
  const [evidenceLead, setEvidenceLead] = useState<DiscoveredLeadRecord | null>(null);

  // General Notification / Error
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isTransferring, setIsTransferring] = useState<boolean>(false);

  // Load search providers on mount
  useEffect(() => {
    let isMounted = true;
    fetchSearchProviders()
      .then((res) => {
        if (isMounted && res.providers && res.providers.length > 0) {
          setProviders(res.providers);
        }
      })
      .catch(() => {
        if (isMounted) {
          setProviders(DEFAULT_SEARCH_PROVIDERS);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  // Poll active job status if job is pending or running
  useEffect(() => {
    if (!activeJob || (activeJob.status !== 'pending' && activeJob.status !== 'running')) {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const res = await fetchDiscoveryJob(activeJob.id);
        setActiveJob(res.job);

        // Also refresh the leads table
        loadLeads(activeJob.id, page, searchFilter, emailStatusFilter);

        if (res.job.status === 'completed') {
          setSuccessMessage(
            `Discovery Job completed! Found ${res.job.discovered_count} leads (${res.job.verified_email_count} with verified public emails).`
          );
        } else if (res.job.status === 'failed') {
          setErrorMessage(res.job.error_message || 'Discovery job failed.');
        }
      } catch {
        // backend poll error
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [activeJob?.id, activeJob?.status, page, searchFilter, emailStatusFilter]);

  // Load discovered leads with pagination and filters
  const loadLeads = useCallback(
    async (jobId: string, pageNum: number, search: string, emailStatus: string) => {
      setIsLoadingLeads(true);
      try {
        const res = await fetchDiscoveredLeads(jobId, {
          page: pageNum,
          pageSize,
          search: search || undefined,
          emailStatus: emailStatus || undefined,
        });
        setLeads(res.leads);
        setTotalLeads(res.total);
        setTotalPages(res.total_pages);
        setVerificationCounts(res.verification_counts);
      } catch (err: unknown) {
        // ignore background poll errors
      } finally {
        setIsLoadingLeads(false);
      }
    },
    [pageSize]
  );

  // Trigger natural language plan interpretation
  const handleInterpretPrompt = async () => {
    if (!prompt.trim()) return;
    setIsInterpreting(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const generatedPlan = await generateDiscoveryPlan(prompt.trim());
      setPlan(generatedPlan);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to interpret prompt.');
    } finally {
      setIsInterpreting(false);
    }
  };

  // Launch discovery job
  const handleStartDiscovery = async () => {
    if (!plan) return;
    setIsStartingJob(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    setSelectedLeadIds(new Set());
    setPage(1);
    try {
      const job = await createDiscoveryJob(plan, selectedProvider);
      setActiveJob(job);
      setSuccessMessage(`Discovery job started with provider [${selectedProvider}]. Pipeline active.`);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to start discovery job.');
    } finally {
      setIsStartingJob(false);
    }
  };

  // Cancel running job
  const handleCancelJob = async () => {
    if (!activeJob) return;
    setIsCancelling(true);
    try {
      const updated = await cancelDiscoveryJob(activeJob.id);
      setActiveJob(updated);
      setSuccessMessage('Job cancellation requested. Stopping external requests.');
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to cancel discovery job.');
    } finally {
      setIsCancelling(false);
    }
  };

  // Export CSV
  const handleExportCsv = async () => {
    if (!activeJob) return;
    try {
      await downloadDiscoveredLeadsCsv(activeJob.id, searchFilter, emailStatusFilter);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to export CSV.');
    }
  };

  // Transfer selected leads to Outreach
  const handleTransferToOutreach = async () => {
    if (!activeJob || selectedLeadIds.size === 0) return;
    setIsTransferring(true);
    setErrorMessage(null);
    try {
      const res = await transferLeadsToOutreach(activeJob.id, Array.from(selectedLeadIds));
      setSuccessMessage(
        `Successfully transferred ${res.total} leads to Outreach (${res.verified_email_count} verified emails). Opening Outreach Console...`
      );
      if (onNavigateToOutreach) {
        setTimeout(() => onNavigateToOutreach(), 1200);
      }
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to transfer leads.');
    } finally {
      setIsTransferring(false);
    }
  };

  // Toggle select lead checkbox
  const toggleSelectLead = (leadId: string) => {
    setSelectedLeadIds((prev) => {
      const next = new Set(prev);
      if (next.has(leadId)) next.delete(leadId);
      else next.add(leadId);
      return next;
    });
  };

  const toggleSelectAllVisible = () => {
    if (selectedLeadIds.size === leads.length && leads.length > 0) {
      setSelectedLeadIds(new Set());
    } else {
      setSelectedLeadIds(new Set(leads.map((l) => l.id)));
    }
  };

  const getVerificationBadge = (status: string) => {
    switch (status) {
      case 'verified_public':
        return (
          <span className="badge badge-active" title="Genuine verified public business email">
            <CheckCircleIcon size={12} /> Verified Public
          </span>
        );
      case 'found_unverified':
        return (
          <span className="badge" style={{ background: 'rgba(234, 179, 8, 0.15)', color: '#eab308', border: '1px solid rgba(234, 179, 8, 0.3)' }}>
            Unverified
          </span>
        );
      case 'invalid':
        return (
          <span className="badge badge-offline" title="Syntax invalid or placeholder address">
            <XIcon size={12} /> Invalid
          </span>
        );
      case 'not_found':
      default:
        return (
          <span className="badge" style={{ background: 'rgba(148, 163, 184, 0.1)', color: 'var(--text-muted)' }}>
            None Listed
          </span>
        );
    }
  };

  return (
    <div className="lead-discovery-container" style={{ padding: '1.5rem', maxWidth: '1440px', margin: '0 auto' }}>
      {/* Top Banner & Header */}
      <div style={{ marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <div style={{ background: 'linear-gradient(135deg, rgba(6,182,212,0.2), rgba(59,130,246,0.2))', padding: '0.5rem', borderRadius: '8px', border: '1px solid rgba(6,182,212,0.3)' }}>
              <CompassIcon size={24} color="var(--accent-cyan)" />
            </div>
            <div>
              <h2 style={{ fontSize: '1.4rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                Automated Lead Discovery Agent
              </h2>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: '0.2rem 0 0' }}>
                Natural-language business discovery across authorized search engines and verified public registries.
              </p>
            </div>
          </div>
        </div>

        {/* Global Notifications */}
        {backendStatus && !backendStatus.isOnline && (
          <div className="alert alert-warning" style={{ maxWidth: '480px', margin: 0, padding: '0.6rem 0.9rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertTriangleIcon size={16} />
            <span>FastAPI Backend is offline. Start the backend service to perform discovery.</span>
          </div>
        )}
        {errorMessage && (
          <div className="alert alert-danger" style={{ maxWidth: '480px', margin: 0, padding: '0.6rem 0.9rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertTriangleIcon size={16} />
            <span style={{ flex: 1 }}>{errorMessage}</span>
            <button onClick={() => setErrorMessage(null)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'inherit' }}>
              <XIcon size={14} />
            </button>
          </div>
        )}
        {successMessage && (
          <div className="alert alert-success" style={{ maxWidth: '480px', margin: 0, padding: '0.6rem 0.9rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <CheckCircleIcon size={16} />
            <span style={{ flex: 1 }}>{successMessage}</span>
            <button onClick={() => setSuccessMessage(null)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'inherit' }}>
              <XIcon size={14} />
            </button>
          </div>
        )}
      </div>

      {/* 1. Natural Language Prompt Panel */}
      <div className="card" style={{ marginBottom: '1.5rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
          <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
            <SparklesIcon size={16} color="var(--accent-cyan)" />
            Describe the businesses you want to discover
          </label>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            No target URLs required. Searches official websites & business registries.
          </span>
        </div>

        <textarea
          className="form-control"
          rows={3}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="e.g. Find 100 solar installation companies in Lahore that serve commercial customers..."
          style={{
            width: '100%',
            background: 'var(--bg-tertiary)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '8px',
            padding: '0.75rem',
            fontSize: '0.9rem',
            lineHeight: 1.5,
            resize: 'vertical',
            fontFamily: 'inherit',
          }}
        />

        {/* Example Prompt Chips */}
        <div style={{ marginTop: '0.65rem', display: 'flex', flexWrap: 'wrap', gap: '0.45rem', alignItems: 'center' }}>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Examples:</span>
          {EXAMPLE_PROMPTS.map((ex, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setPrompt(ex)}
              style={{
                background: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid var(--border-subtle)',
                color: 'var(--text-secondary)',
                borderRadius: '16px',
                padding: '0.2rem 0.6rem',
                fontSize: '0.7rem',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--accent-cyan)')}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border-subtle)')}
            >
              {ex.slice(0, 48)}...
            </button>
          ))}
        </div>

        <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
          <button
            className="btn btn-primary"
            onClick={handleInterpretPrompt}
            disabled={isInterpreting || !prompt.trim()}
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.55rem 1.1rem' }}
          >
            {isInterpreting ? (
              <>
                <RefreshCwIcon size={15} className="spin" /> Interpreting Request...
              </>
            ) : (
              <>
                <SparklesIcon size={15} /> Interpret & Create Plan
              </>
            )}
          </button>
        </div>
      </div>

      {/* 2. Interpreted Plan & Provider Configuration */}
      {plan && (
        <div className="card" style={{ marginBottom: '1.5rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0, display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
              <CompassIcon size={16} color="var(--accent-cyan)" /> Structured Search Plan
            </h3>
            <span className="badge badge-cyan" style={{ fontSize: '0.72rem' }}>
              Review & Customize
            </span>
          </div>

          {/* Ambiguity Alert */}
          {plan.is_ambiguous && (
            <div className="alert alert-warning" style={{ marginBottom: '1rem', padding: '0.75rem 1rem', fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <AlertTriangleIcon size={18} color="#eab308" />
              <div>
                <strong>Ambiguous Criteria: </strong>
                {plan.clarification_question || 'Please provide more details on target industry or location.'}
              </div>
            </div>
          )}

          {/* Plan Form Fields Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
            <div>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.3rem' }}>
                Industry / Category
              </label>
              <input
                type="text"
                className="form-control"
                value={plan.industry}
                onChange={(e) => setPlan({ ...plan, industry: e.target.value })}
                style={{ width: '100%', padding: '0.45rem 0.65rem', fontSize: '0.85rem' }}
              />
            </div>

            <div>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.3rem' }}>
                City
              </label>
              <input
                type="text"
                className="form-control"
                value={plan.location_city || ''}
                placeholder="e.g. Lahore, Berlin, Riyadh"
                onChange={(e) => setPlan({ ...plan, location_city: e.target.value })}
                style={{ width: '100%', padding: '0.45rem 0.65rem', fontSize: '0.85rem' }}
              />
            </div>

            <div>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.3rem' }}>
                Country
              </label>
              <input
                type="text"
                className="form-control"
                value={plan.location_country || ''}
                placeholder="e.g. Pakistan, Germany"
                onChange={(e) => setPlan({ ...plan, location_country: e.target.value })}
                style={{ width: '100%', padding: '0.45rem 0.65rem', fontSize: '0.85rem' }}
              />
            </div>

            <div>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.3rem' }}>
                Target Lead Count
              </label>
              <input
                type="number"
                min={1}
                max={100}
                className="form-control"
                value={plan.target_lead_count}
                onChange={(e) => setPlan({ ...plan, target_lead_count: parseInt(e.target.value) || 25 })}
                style={{ width: '100%', padding: '0.45rem 0.65rem', fontSize: '0.85rem' }}
              />
            </div>
          </div>

          {/* Search Source Selector */}
          <div style={{ marginTop: '1.2rem', paddingTop: '1rem', borderTop: '1px solid var(--border-subtle)' }}>
            <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)', display: 'block', marginBottom: '0.5rem' }}>
              Search Source & Provider:
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '0.75rem' }}>
              {providers.map((p) => {
                const isSelected = selectedProvider === p.id;
                return (
                  <div
                    key={p.id}
                    onClick={() => setSelectedProvider(p.id)}
                    style={{
                      padding: '0.75rem',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      background: isSelected ? 'rgba(6,182,212,0.12)' : 'var(--bg-tertiary)',
                      border: isSelected ? '1px solid var(--accent-cyan)' : '1px solid var(--border-subtle)',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                      <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)' }}>{p.name}</span>
                      {p.is_configured ? (
                        <span className="badge badge-active" style={{ fontSize: '0.62rem' }}>Ready</span>
                      ) : (
                        <span className="badge badge-offline" style={{ fontSize: '0.62rem' }}>Needs Setup</span>
                      )}
                    </div>
                    <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', margin: '0 0 0.35rem' }}>{p.description}</p>
                    <span style={{ fontSize: '0.68rem', color: p.is_configured ? 'var(--accent-cyan)' : '#f87171' }}>
                      {p.notice}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Start Button */}
          <div style={{ marginTop: '1.25rem', display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button
              className="btn btn-primary"
              onClick={handleStartDiscovery}
              disabled={Boolean(isStartingJob || (activeJob && (activeJob.status === 'pending' || activeJob.status === 'running')))}
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.6rem 1.4rem', fontWeight: 600 }}
            >
              {isStartingJob ? (
                <>
                  <RefreshCwIcon size={16} className="spin" /> Initializing Discovery...
                </>
              ) : (
                <>
                  <CompassIcon size={16} /> Start Automated Discovery
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* 3. Live Telemetry & Progress Card */}
      {activeJob && (
        <div className="card" style={{ marginBottom: '1.5rem', background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Job ID: {activeJob.id} • Source: {activeJob.provider_used}
              </span>
              <div style={{ fontSize: '0.92rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.2rem' }}>
                {activeJob.current_stage || 'Discovery in progress'}
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span
                className={`badge ${
                  activeJob.status === 'completed'
                    ? 'badge-active'
                    : activeJob.status === 'failed' || activeJob.status === 'cancelled'
                    ? 'badge-offline'
                    : 'badge-cyan'
                }`}
                style={{ fontSize: '0.75rem' }}
              >
                {activeJob.status.toUpperCase()}
              </span>

              {(activeJob.status === 'running' || activeJob.status === 'pending') && (
                <button
                  className="btn btn-secondary"
                  onClick={handleCancelJob}
                  disabled={isCancelling}
                  style={{ color: '#f87171', borderColor: 'rgba(248,113,113,0.3)', padding: '0.4rem 0.8rem', fontSize: '0.78rem' }}
                >
                  <StopCircleIcon size={14} color="#f87171" />
                  {isCancelling ? 'Cancelling...' : 'Cancel Job'}
                </button>
              )}
            </div>
          </div>

          {/* Progress Bar */}
          <div style={{ width: '100%', height: '8px', background: 'var(--bg-tertiary)', borderRadius: '4px', overflow: 'hidden', marginBottom: '1rem' }}>
            <div
              style={{
                width: `${activeJob.progress_percent}%`,
                height: '100%',
                background: 'linear-gradient(90deg, var(--accent-cyan), #3b82f6)',
                transition: 'width 0.3s ease',
              }}
            />
          </div>

          {/* KPI Counters */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem' }}>
            <div style={{ background: 'var(--bg-tertiary)', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Discovered Leads</span>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                {activeJob.discovered_count} / {activeJob.total_target}
              </div>
            </div>

            <div style={{ background: 'var(--bg-tertiary)', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Verified Public Emails</span>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                {activeJob.verified_email_count}
              </div>
            </div>

            <div style={{ background: 'var(--bg-tertiary)', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Duplicates Skipped</span>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-secondary)' }}>
                {activeJob.duplicate_count}
              </div>
            </div>

            <div style={{ background: 'var(--bg-tertiary)', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Skipped / Restricted</span>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#eab308' }}>
                {activeJob.skipped_count}
              </div>
            </div>

            <div style={{ background: 'var(--bg-tertiary)', padding: '0.65rem 0.85rem', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Inaccessible / Failed</span>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f87171' }}>
                {activeJob.failed_count}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 4. Discovered Leads Table & Actions */}
      <div className="card" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '1.25rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flex: 1, minWidth: '280px' }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <input
                type="text"
                className="form-control"
                placeholder="Search discovered companies, emails, or domains..."
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                style={{ paddingLeft: '2rem', width: '100%', fontSize: '0.85rem' }}
              />
              <div style={{ position: 'absolute', left: '0.65rem', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}>
                <SearchIcon size={14} color="var(--text-muted)" />
              </div>
            </div>

            <select
              className="form-control"
              value={emailStatusFilter}
              onChange={(e) => setEmailStatusFilter(e.target.value)}
              style={{ width: '170px', fontSize: '0.82rem' }}
            >
              <option value="">All Verification States</option>
              <option value="verified_public">Verified Public ({verificationCounts.verified_public || 0})</option>
              <option value="found_unverified">Unverified ({verificationCounts.found_unverified || 0})</option>
              <option value="not_found">No Email Listed ({verificationCounts.not_found || 0})</option>
              <option value="invalid">Invalid ({verificationCounts.invalid || 0})</option>
            </select>

            {verificationCounts.verified_public ? (
              <span className="badge badge-active" style={{ fontSize: '0.72rem', whiteSpace: 'nowrap' }}>
                <CheckCircleIcon size={11} /> {verificationCounts.verified_public} Verified Public
              </span>
            ) : null}
          </div>

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              className="btn btn-secondary"
              onClick={handleExportCsv}
              disabled={!activeJob || leads.length === 0}
              style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.8rem' }}
            >
              <DownloadIcon size={14} /> Export CSV
            </button>

            <button
              className="btn btn-primary"
              onClick={handleTransferToOutreach}
              disabled={isTransferring || selectedLeadIds.size === 0}
              style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.8rem' }}
            >
              <SendIcon size={14} />
              {isTransferring ? 'Drafting...' : `Transfer to Outreach (${selectedLeadIds.size})`}
            </button>
          </div>
        </div>

        {/* Table */}
        <div style={{ overflowX: 'auto' }}>
          <table className="table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)', textAlign: 'left' }}>
                <th style={{ padding: '0.6rem 0.5rem', width: '36px' }}>
                  <input
                    type="checkbox"
                    checked={selectedLeadIds.size === leads.length && leads.length > 0}
                    onChange={toggleSelectAllVisible}
                  />
                </th>
                <th style={{ padding: '0.6rem 0.75rem' }}>Company & Official Website</th>
                <th style={{ padding: '0.6rem 0.75rem' }}>Location</th>
                <th style={{ padding: '0.6rem 0.75rem' }}>Public Business Email</th>
                <th style={{ padding: '0.6rem 0.75rem' }}>Public Phone</th>
                <th style={{ padding: '0.6rem 0.75rem' }}>Relevance</th>
                <th style={{ padding: '0.6rem 0.75rem', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {leads.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-muted)' }}>
                    {isLoadingLeads ? (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
                        <RefreshCwIcon size={20} className="spin" />
                        <span>Searching web sources and verifying records...</span>
                      </div>
                    ) : (
                      <div>
                        <CompassIcon size={32} color="var(--border-subtle)" style={{ marginBottom: '0.5rem' }} />
                        <p style={{ margin: 0 }}>No leads discovered yet. Enter a request above and start discovery.</p>
                      </div>
                    )}
                  </td>
                </tr>
              ) : (
                leads.map((lead) => {
                  const isChecked = selectedLeadIds.has(lead.id);
                  return (
                    <tr
                      key={lead.id}
                      style={{
                        borderBottom: '1px solid rgba(255,255,255,0.04)',
                        background: isChecked ? 'rgba(6,182,212,0.06)' : undefined,
                      }}
                    >
                      <td style={{ padding: '0.65rem 0.5rem' }}>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleSelectLead(lead.id)}
                        />
                      </td>

                      <td style={{ padding: '0.65rem 0.75rem' }}>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{lead.company_name}</div>
                        <a
                          href={lead.website}
                          target="_blank"
                          rel="noreferrer"
                          style={{
                            fontSize: '0.72rem',
                            color: 'var(--accent-cyan)',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.25rem',
                            textDecoration: 'none',
                          }}
                        >
                          {lead.website.replace(/^https?:\/\//, '')} <ExternalLinkIcon size={11} />
                        </a>
                      </td>

                      <td style={{ padding: '0.65rem 0.75rem', color: 'var(--text-secondary)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          <MapPinIcon size={13} color="var(--text-muted)" />
                          {[lead.city, lead.country].filter(Boolean).join(', ') || 'Global / Web'}
                        </div>
                      </td>

                      <td style={{ padding: '0.65rem 0.75rem' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem', color: lead.email ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                            {lead.email || '(None listed)'}
                          </span>
                          <div>{getVerificationBadge(lead.email_verification_status)}</div>
                        </div>
                      </td>

                      <td style={{ padding: '0.65rem 0.75rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                        {lead.phone ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                            <PhoneIcon size={12} color="var(--accent-cyan)" /> {lead.phone}
                          </div>
                        ) : (
                          <span style={{ color: 'var(--text-muted)' }}>—</span>
                        )}
                      </td>

                      <td style={{ padding: '0.65rem 0.75rem' }}>
                        <span className="badge badge-cyan" style={{ fontSize: '0.7rem' }}>
                          {Math.round(lead.relevance_score * 100)}%
                        </span>
                      </td>

                      <td style={{ padding: '0.65rem 0.75rem', textAlign: 'right' }}>
                        <button
                          className="btn btn-secondary"
                          onClick={() => setEvidenceLead(lead)}
                          style={{ padding: '0.3rem 0.6rem', fontSize: '0.72rem', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
                        >
                          <EyeIcon size={12} /> Evidence
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        {totalPages > 1 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Showing {leads.length} of {totalLeads} discovered leads
            </span>
            <div style={{ display: 'flex', gap: '0.4rem' }}>
              <button
                className="btn btn-secondary"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                style={{ padding: '0.3rem 0.6rem' }}
              >
                <ChevronLeftIcon size={14} />
              </button>
              <span style={{ fontSize: '0.8rem', padding: '0.3rem 0.6rem', color: 'var(--text-secondary)' }}>
                Page {page} of {totalPages}
              </span>
              <button
                className="btn btn-secondary"
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
                style={{ padding: '0.3rem 0.6rem' }}
              >
                <ChevronRightIcon size={14} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 5. Lead Evidence Modal */}
      {evidenceLead && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: '1rem',
          }}
          onClick={() => setEvidenceLead(null)}
        >
          <div
            className="card"
            style={{
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '12px',
              maxWidth: '680px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              padding: '1.5rem',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
              <div>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                  {evidenceLead.company_name}
                </h3>
                <a
                  href={evidenceLead.website}
                  target="_blank"
                  rel="noreferrer"
                  style={{ fontSize: '0.8rem', color: 'var(--accent-cyan)', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}
                >
                  {evidenceLead.website} <ExternalLinkIcon size={12} />
                </a>
              </div>
              <button
                onClick={() => setEvidenceLead(null)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <XIcon size={18} />
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '1rem' }}>
              <div style={{ background: 'var(--bg-tertiary)', padding: '0.65rem 0.85rem', borderRadius: '8px' }}>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Discovery Source</span>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {evidenceLead.discovery_source}
                </div>
              </div>

              <div style={{ background: 'var(--bg-tertiary)', padding: '0.65rem 0.85rem', borderRadius: '8px' }}>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Email Verification Status</span>
                <div style={{ marginTop: '0.2rem' }}>{getVerificationBadge(evidenceLead.email_verification_status)}</div>
              </div>
            </div>

            <div style={{ marginBottom: '1rem' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '0.3rem' }}>
                Relevance Explanation:
              </label>
              <div style={{ background: 'var(--bg-tertiary)', padding: '0.65rem 0.85rem', borderRadius: '8px', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                {evidenceLead.relevance_explanation}
              </div>
            </div>

            <div style={{ marginBottom: '1rem' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '0.3rem' }}>
                Business Description:
              </label>
              <div style={{ background: 'var(--bg-tertiary)', padding: '0.65rem 0.85rem', borderRadius: '8px', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                {evidenceLead.services_description || 'No public business description found.'}
              </div>
            </div>

            <div style={{ marginBottom: '1rem' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '0.3rem' }}>
                Source URLs (Direct Evidence):
              </label>
              <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.78rem', color: 'var(--accent-cyan)' }}>
                {evidenceLead.source_urls.map((u, i) => (
                  <li key={i} style={{ marginBottom: '0.25rem' }}>
                    <a href={u} target="_blank" rel="noreferrer" style={{ color: 'inherit', textDecoration: 'none' }}>
                      {u}
                    </a>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '0.3rem' }}>
                Confirmed Verified Fields:
              </label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                {evidenceLead.verified_fields.map((f, i) => (
                  <span key={i} className="badge badge-active" style={{ fontSize: '0.68rem' }}>
                    <CheckIcon size={10} /> {f}
                  </span>
                ))}
              </div>
            </div>

            <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary" onClick={() => setEvidenceLead(null)}>
                Close Evidence
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
