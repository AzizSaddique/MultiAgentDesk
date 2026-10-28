import React, { useState, useEffect, useCallback, useMemo } from 'react';
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
  ArrowUpDownIcon,
  GlobeIcon,
  BuildingIcon,
  ShieldAlertIcon,
  FilterIcon,
} from './icons';

interface LeadDiscoveryProps {
  backendStatus?: BackendStatus;
  onNavigateToOutreach?: () => void;
}

const EXAMPLE_PROMPTS = [
  "Find 20 IoT companies in Germany that may need embedded software development.",
  "Find 100 solar installation companies in Lahore that serve commercial customers.",
  "Discover manufacturing companies in Saudi Arabia and collect their official websites and publicly listed business contact emails.",
  "Find robotics and automation companies in Germany that could be potential clients.",
  "Discover European B2B SaaS companies specializing in logistics and supply chain optimization.",
];

const DEFAULT_SEARCH_PROVIDERS: SearchProviderInfo[] = [
  {
    id: 'auto',
    name: 'Auto-Select Best Available',
    description: 'Automatically routes to highest priority configured commercial provider, falling back to DuckDuckGo live search.',
    is_configured: true,
    requires_key: false,
    notice: 'Active route: Automatic Provider Selection',
  },
  {
    id: 'duckduckgo',
    name: 'DuckDuckGo Live Search',
    description: 'Real-time web search without external API key requirements. Discovers live company websites directly.',
    is_configured: true,
    requires_key: false,
    notice: 'Live web search available out-of-the-box. Zero API keys required.',
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

const STAGE_STEPS = [
  { id: 1, label: 'Query Formulation', keyword: 'query' },
  { id: 2, label: 'Provider Retrieval', keyword: 'search' },
  { id: 3, label: 'Website Verification', keyword: 'crawling' },
  { id: 4, label: 'Contact Extraction', keyword: 'extracting' },
  { id: 5, label: 'Deduplication & Grounding', keyword: 'grounding' },
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
  const [pageSize, setPageSize] = useState<number>(15);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [verificationCounts, setVerificationCounts] = useState<Record<string, number>>({});
  const [isLoadingLeads, setIsLoadingLeads] = useState<boolean>(false);

  // Table Filters & Sorting
  const [searchFilter, setSearchFilter] = useState<string>('');
  const [emailStatusFilter, setEmailStatusFilter] = useState<string>('');
  const [sortBy, setSortBy] = useState<string>('relevance_score');
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc');
  const [selectedLeadIds, setSelectedLeadIds] = useState<Set<string>>(new Set());

  // Evidence Detail Modal
  const [evidenceLead, setEvidenceLead] = useState<DiscoveredLeadRecord | null>(null);

  // New Keyword input in Plan Editor
  const [newKeywordInput, setNewKeywordInput] = useState<string>('');

  // General Notification / Error
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isTransferring, setIsTransferring] = useState<boolean>(false);
  const [transferringLeadId, setTransferringLeadId] = useState<string | null>(null);

  // Selected Provider Info
  const currentProviderInfo = useMemo(() => {
    return providers.find((p) => p.id === selectedProvider) || providers[0];
  }, [providers, selectedProvider]);

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

  // Load discovered leads with pagination and filters
  const loadLeads = useCallback(
    async (
      jobId: string,
      pageNum: number,
      search: string,
      emailStatus: string,
      sortField: string,
      sortDir: string,
      size: number
    ) => {
      setIsLoadingLeads(true);
      try {
        const res = await fetchDiscoveredLeads(jobId, {
          page: pageNum,
          pageSize: size,
          search: search || undefined,
          emailStatus: emailStatus || undefined,
          sortBy: sortField,
          sortOrder: sortDir,
        });
        setLeads(res.leads);
        setTotalLeads(res.total);
        setTotalPages(res.total_pages);
        setVerificationCounts(res.verification_counts || {});
      } catch (err: unknown) {
        // ignore background poll errors
      } finally {
        setIsLoadingLeads(false);
      }
    },
    []
  );

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
        loadLeads(activeJob.id, page, searchFilter, emailStatusFilter, sortBy, sortOrder, pageSize);

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
  }, [activeJob?.id, activeJob?.status, page, searchFilter, emailStatusFilter, sortBy, sortOrder, pageSize, loadLeads]);

  // When filters or sorting change, reload leads
  useEffect(() => {
    if (activeJob?.id) {
      loadLeads(activeJob.id, page, searchFilter, emailStatusFilter, sortBy, sortOrder, pageSize);
    }
  }, [activeJob?.id, page, searchFilter, emailStatusFilter, sortBy, sortOrder, pageSize, loadLeads]);

  // Trigger natural language plan interpretation
  const handleInterpretPrompt = async () => {
    const trimmed = prompt.trim();
    if (!trimmed) return;
    setIsInterpreting(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const generatedPlan = await generateDiscoveryPlan(trimmed);
      setPlan(generatedPlan);
      setSuccessMessage('Search plan generated. Review parameters below and start discovery.');
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
      setSuccessMessage(`Discovery pipeline initiated with provider [${selectedProvider}]. Live telemetry running.`);
      // Initial lead load
      loadLeads(job.id, 1, '', '', sortBy, sortOrder, pageSize);
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
      setSuccessMessage('Job cancellation requested. Search engine requests safely halted.');
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

  // Transfer leads to personalized Outreach Drafts (supports single and bulk)
  const handleTransferLeads = async (leadIds: string[], companyLabel?: string) => {
    if (!activeJob || leadIds.length === 0) return;
    setIsTransferring(true);
    if (leadIds.length === 1) {
      setTransferringLeadId(leadIds[0]);
    }
    setErrorMessage(null);
    try {
      const res = await transferLeadsToOutreach(activeJob.id, leadIds, {
        serviceOffering: "Custom software development, IoT systems, and cloud architecture",
        tone: "professional",
        preventDuplicates: true,
      });

      const counts = [];
      if (res.created_count > 0) counts.push(`${res.created_count} created`);
      if (res.skipped_count > 0) counts.push(`${res.skipped_count} skipped (duplicate)`);
      if (res.failed_count > 0) counts.push(`${res.failed_count} failed`);

      const countSummary = counts.length > 0 ? counts.join(', ') : `${res.total} processed`;
      const msg = companyLabel
        ? `Outreach Draft for "${companyLabel}": ${countSummary} (${res.verified_email_count} verified emails).`
        : `Transfer complete: ${countSummary} (${res.verified_email_count} verified emails).`;

      setSuccessMessage(msg);

      // Deselect transferred leads
      setSelectedLeadIds((prev) => {
        const next = new Set(prev);
        leadIds.forEach((id) => next.delete(id));
        return next;
      });
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to transfer lead(s) to outreach.');
    } finally {
      setIsTransferring(false);
      setTransferringLeadId(null);
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

  // Plan Keyword management
  const handleAddKeyword = () => {
    const kw = newKeywordInput.trim();
    if (!kw || !plan) return;
    if (!plan.keywords.includes(kw)) {
      setPlan({ ...plan, keywords: [...plan.keywords, kw] });
    }
    setNewKeywordInput('');
  };

  const handleRemoveKeyword = (index: number) => {
    if (!plan) return;
    const next = [...plan.keywords];
    next.splice(index, 1);
    setPlan({ ...plan, keywords: next });
  };

  // Status badge helper
  const getVerificationBadge = (status: string) => {
    switch (status) {
      case 'verified_public':
      case 'publicly_listed':
        return (
          <span className="badge badge-active" title="Authentic public business email listed on official website or registry; mailbox unverified">
            <CheckCircleIcon size={12} /> Publicly Listed
          </span>
        );
      case 'verified_by_provider':
        return (
          <span className="badge badge-cyan" title="Operational inbox status verified by email verification provider">
            <CheckCircleIcon size={12} /> Provider Verified
          </span>
        );
      case 'syntax_valid':
      case 'domain_valid':
      case 'mailbox_unverified':
        return (
          <span className="badge badge-cyan" title="Email syntax and domain format are valid; mailbox delivery unverified">
            <CheckCircleIcon size={12} /> Syntax Valid
          </span>
        );
      case 'needs_review':
        return (
          <span className="badge badge-warning" title="Field data requires manual operator review">
            <AlertTriangleIcon size={12} /> Needs Review
          </span>
        );
      case 'found_unverified':
        return (
          <span className="badge badge-warning" title="Email address found in text but syntax or domain verification pending">
            <AlertTriangleIcon size={12} /> Unverified
          </span>
        );
      case 'invalid':
        return (
          <span className="badge badge-offline" title="Syntax invalid or placeholder address - rejected by safety gate">
            <XIcon size={12} /> Invalid Format
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

  // Source attribution badge helper
  const getSourceBadge = (source: string, isLive?: boolean) => {
    const sLower = (source || '').toLowerCase();
    if (!isLive || sLower.includes('seed') || sLower.includes('predefined') || sLower.includes('audit')) {
      return (
        <span
          className="badge"
          style={{
            background: 'rgba(148, 163, 184, 0.15)',
            color: 'var(--text-secondary)',
            border: '1px solid rgba(148, 163, 184, 0.3)',
          }}
          title="Predefined seed record from verified offline audit roster. Not retrieved from live search."
        >
          <BuildingIcon size={11} /> Predefined Seed Data
        </span>
      );
    }
    if (sLower.includes('directory')) {
      return (
        <span
          className="badge"
          style={{
            background: 'rgba(148, 163, 184, 0.12)',
            color: 'var(--text-secondary)',
            border: '1px solid rgba(148, 163, 184, 0.25)',
          }}
          title="Extracted from public trade registry"
        >
          <BuildingIcon size={11} /> Public Directory
        </span>
      );
    }
    return (
      <span
        className="badge badge-cyan"
        title={`Live web discovery verified via ${source || 'Live Search'}`}
      >
        <GlobeIcon size={11} /> {source || 'Live Search'}
      </span>
    );
  };

  // Determine active stage index for Stepper
  const activeStageIndex = useMemo(() => {
    if (!activeJob) return -1;
    if (activeJob.status === 'completed') return 5;
    if (activeJob.status === 'failed' || activeJob.status === 'cancelled') return -1;
    const stageStr = (activeJob.current_stage || '').toLowerCase();
    if (stageStr.includes('formulat') || stageStr.includes('query')) return 0;
    if (stageStr.includes('search') || stageStr.includes('retriev') || stageStr.includes('provider')) return 1;
    if (stageStr.includes('crawl') || stageStr.includes('website') || stageStr.includes('verif')) return 2;
    if (stageStr.includes('extract') || stageStr.includes('email') || stageStr.includes('contact')) return 3;
    if (stageStr.includes('ground') || stageStr.includes('dedup')) return 4;
    return 1;
  }, [activeJob]);

  return (
    <div className="discovery-dashboard">
      {/* Top Header & Breadcrumbs */}
      <div className="discovery-header-row">
        <div className="discovery-title-group">
          <div className="discovery-icon-orb">
            <CompassIcon size={24} color="var(--accent-cyan)" />
          </div>
          <div className="discovery-title-text">
            <h2>
              Automated Lead Discovery
              <span className="badge badge-cyan" style={{ fontSize: '0.65rem', verticalAlign: 'middle' }}>
                AI Discovery Engine
              </span>
            </h2>
            <p>
              Natural-language market discovery across live authorized search engines and verified public business directories.
            </p>
          </div>
        </div>

        {/* Global Notifications */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxWidth: '480px', width: '100%' }}>
          {backendStatus && !backendStatus.isOnline && (
            <div className="alert alert-warning" style={{ margin: 0, padding: '0.6rem 0.9rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <AlertTriangleIcon size={16} />
              <span>FastAPI Backend is offline. Run backend service to execute discovery.</span>
            </div>
          )}
          {errorMessage && (
            <div className="alert alert-danger" style={{ margin: 0, padding: '0.65rem 0.95rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <AlertTriangleIcon size={16} />
              <span style={{ flex: 1 }}>{errorMessage}</span>
              <button
                onClick={() => setErrorMessage(null)}
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'inherit' }}
                aria-label="Dismiss error"
              >
                <XIcon size={14} />
              </button>
            </div>
          )}
          {successMessage && (
            <div className="alert alert-success" style={{ margin: 0, padding: '0.65rem 0.95rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
              <CheckCircleIcon size={16} />
              <span style={{ flex: 1, minWidth: '180px' }}>{successMessage}</span>
              {onNavigateToOutreach && (
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={onNavigateToOutreach}
                  style={{
                    fontSize: '0.74rem',
                    padding: '0.25rem 0.65rem',
                    whiteSpace: 'nowrap',
                    background: 'rgba(52, 211, 153, 0.15)',
                    borderColor: 'rgba(52, 211, 153, 0.35)',
                    color: '#34d399',
                    cursor: 'pointer',
                  }}
                >
                  Open Outreach Console &rarr;
                </button>
              )}
              <button
                onClick={() => setSuccessMessage(null)}
                style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'inherit' }}
                aria-label="Dismiss message"
              >
                <XIcon size={14} />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 1. Natural Language Search & Prompt Card */}
      <div className="discovery-hero-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
          <label style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <SparklesIcon size={17} color="var(--accent-cyan)" />
            Describe the businesses you want to discover
          </label>
          <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
            No target URLs required. Searches official websites & public directories.
          </span>
        </div>

        <div className="discovery-input-box">
          <textarea
            className="discovery-textarea"
            rows={2}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                handleInterpretPrompt();
              }
            }}
            placeholder="Find 20 IoT companies in Germany that may need embedded software development."
          />

          <div className="discovery-prompt-footer">
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem', alignItems: 'center', flex: 1 }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600 }}>Quick Prompts:</span>
              {EXAMPLE_PROMPTS.map((ex, i) => (
                <button
                  key={i}
                  type="button"
                  className="discovery-chip"
                  onClick={() => setPrompt(ex)}
                  title={ex}
                >
                  <SparklesIcon size={12} color="var(--accent-cyan)" />
                  {ex.length > 50 ? `${ex.slice(0, 48)}...` : ex}
                </button>
              ))}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setPrompt('')}
                disabled={!prompt.trim() || isInterpreting}
                style={{ fontSize: '0.78rem', padding: '0.45rem 0.75rem' }}
              >
                Clear
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleInterpretPrompt}
                disabled={isInterpreting || !prompt.trim()}
                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.55rem 1.25rem', fontWeight: 600 }}
              >
                {isInterpreting ? (
                  <>
                    <RefreshCwIcon size={15} className="spin" /> Interpreting Prompt...
                  </>
                ) : (
                  <>
                    <SparklesIcon size={15} /> Interpret & Create Plan
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* 2. Provider Selector (Always visible) */}
        <div className="provider-select-section">
          <div className="provider-section-label">
            <span>Select Discovery Search Provider</span>
            <span style={{ fontSize: '0.7rem', textTransform: 'none', color: 'var(--text-muted)' }}>
              Live availability from microservice
            </span>
          </div>

          <div className="provider-grid">
            {providers.map((p) => {
              const isSelected = selectedProvider === p.id;
              const isDir = p.id === 'directory';
              const isAuto = p.id === 'auto';

              return (
                <div
                  key={p.id}
                  className={`provider-card ${isSelected ? 'selected' : ''}`}
                  onClick={() => setSelectedProvider(p.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      setSelectedProvider(p.id);
                    }
                  }}
                >
                  <div>
                    <div className="provider-card-header">
                      <span className="provider-card-title">{p.name}</span>
                      {isAuto ? (
                        <span className="badge badge-cyan" style={{ fontSize: '0.62rem' }}>
                          Auto
                        </span>
                      ) : isDir ? (
                        <span className="badge" style={{ background: 'rgba(148, 163, 184, 0.15)', color: 'var(--text-primary)', fontSize: '0.62rem' }}>
                          Offline Safe
                        </span>
                      ) : p.is_configured ? (
                        <span className="badge badge-active" style={{ fontSize: '0.62rem' }}>
                          <span className="badge-dot" /> Ready
                        </span>
                      ) : (
                        <span className="badge badge-offline" style={{ fontSize: '0.62rem' }}>
                          Needs Key
                        </span>
                      )}
                    </div>
                    <p className="provider-card-desc">{p.description}</p>
                  </div>

                  <div className="provider-card-notice">
                    {p.is_configured ? (
                      <span style={{ color: isAuto ? 'var(--accent-cyan)' : '#34d399' }}>
                        ✓ {p.notice}
                      </span>
                    ) : (
                      <span style={{ color: '#f87171' }}>
                        ⚠ {p.notice}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Provider Not Configured Alert State */}
          {!currentProviderInfo.is_configured && (
            <div className="provider-alert-card">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <AlertTriangleIcon size={20} color="#f87171" />
                <div>
                  <strong style={{ color: '#f87171', fontSize: '0.85rem' }}>
                    {currentProviderInfo.name} is not configured
                  </strong>
                  <p style={{ margin: '0.15rem 0 0', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                    {currentProviderInfo.notice} Switch to Public Business Directory for offline discovery or Auto-Select to route automatically.
                  </p>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', flexShrink: 0 }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setSelectedProvider('directory')}
                  style={{ fontSize: '0.76rem', padding: '0.35rem 0.75rem' }}
                >
                  Use Public Directory
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setSelectedProvider('auto')}
                  style={{ fontSize: '0.76rem', padding: '0.35rem 0.75rem', borderColor: 'var(--accent-cyan)', color: 'var(--accent-cyan)' }}
                >
                  Use Auto-Select
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 3. Structured Search-Plan Preview & Customizer */}
      {plan && (
        <div className="search-plan-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <CompassIcon size={18} color="var(--accent-cyan)" />
                Structured Search Plan Preview
              </h3>
              <p style={{ margin: '0.2rem 0 0', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                Review and customize search parameters extracted from your request before discovery begins.
              </p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="badge badge-cyan" style={{ fontSize: '0.72rem' }}>
                Route: {currentProviderInfo.name}
              </span>
            </div>
          </div>

          {/* Ambiguity Alert Banner */}
          {plan.is_ambiguous && (
            <div className="alert alert-warning" style={{ marginBottom: '1rem', padding: '0.75rem 1rem', fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <AlertTriangleIcon size={18} color="#fbbf24" />
              <div>
                <strong>Ambiguity Detected: </strong>
                {plan.clarification_question || 'Target criteria could be broader or narrower. Adjust the fields below as needed.'}
              </div>
            </div>
          )}

          {/* Plan Form Fields Grid */}
          <div className="plan-grid">
            <div className="form-group">
              <label className="form-label">
                <BuildingIcon size={13} color="var(--accent-cyan)" /> Target Industry / Category
              </label>
              <input
                type="text"
                className="form-input"
                value={plan.industry}
                onChange={(e) => setPlan({ ...plan, industry: e.target.value })}
                placeholder="e.g. IoT, Embedded Software, Solar"
              />
            </div>

            <div className="form-group">
              <label className="form-label">
                <MapPinIcon size={13} color="var(--accent-cyan)" /> City / Metro
              </label>
              <input
                type="text"
                className="form-input"
                value={plan.location_city || ''}
                placeholder="e.g. Berlin, Munich, Lahore, Riyadh"
                onChange={(e) => setPlan({ ...plan, location_city: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label className="form-label">
                <GlobeIcon size={13} color="var(--accent-cyan)" /> Country / Region
              </label>
              <input
                type="text"
                className="form-input"
                value={plan.location_country || ''}
                placeholder="e.g. Germany, Pakistan, Saudi Arabia"
                onChange={(e) => setPlan({ ...plan, location_country: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label className="form-label">
                <SearchIcon size={13} color="var(--accent-cyan)" /> Target Lead Count
              </label>
              <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                <input
                  type="number"
                  min={1}
                  max={100}
                  className="form-input"
                  style={{ width: '90px' }}
                  value={plan.target_lead_count}
                  onChange={(e) => setPlan({ ...plan, target_lead_count: Math.min(100, Math.max(1, parseInt(e.target.value) || 20)) })}
                />
                <div style={{ display: 'flex', gap: '0.25rem' }}>
                  {[10, 20, 50].map((n) => (
                    <button
                      key={n}
                      type="button"
                      className="preset-chip"
                      style={{ padding: '0.2rem 0.45rem', fontSize: '0.7rem' }}
                      onClick={() => setPlan({ ...plan, target_lead_count: n })}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Keywords Tag Editor */}
          <div style={{ marginBottom: '1.25rem' }}>
            <label className="form-label" style={{ marginBottom: '0.45rem' }}>
              Extracted Search Keywords:
            </label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', alignItems: 'center', marginBottom: '0.6rem' }}>
              {plan.keywords.map((kw, i) => (
                <span key={i} className="plan-keyword-tag">
                  {kw}
                  <button
                    type="button"
                    onClick={() => handleRemoveKeyword(i)}
                    style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', padding: 0, display: 'inline-flex' }}
                    title="Remove keyword"
                  >
                    <XIcon size={12} />
                  </button>
                </span>
              ))}

              <div style={{ display: 'inline-flex', gap: '0.3rem', alignItems: 'center' }}>
                <input
                  type="text"
                  placeholder="+ Add keyword..."
                  value={newKeywordInput}
                  onChange={(e) => setNewKeywordInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleAddKeyword();
                    }
                  }}
                  style={{
                    background: 'rgba(15, 23, 42, 0.6)',
                    border: '1px dashed var(--border-subtle)',
                    borderRadius: '16px',
                    padding: '0.2rem 0.65rem',
                    fontSize: '0.72rem',
                    color: 'var(--text-primary)',
                    outline: 'none',
                    width: '120px',
                  }}
                />
                {newKeywordInput.trim() && (
                  <button
                    type="button"
                    onClick={handleAddKeyword}
                    className="btn btn-secondary"
                    style={{ padding: '0.15rem 0.45rem', fontSize: '0.7rem', borderRadius: '12px' }}
                  >
                    Add
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Action Row */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-subtle)', paddingTop: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              <ShieldAlertIcon size={14} color="#34d399" />
              <span>Strict public domain verification & SSRF protection enforced.</span>
            </div>

            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleStartDiscovery}
                disabled={Boolean(isStartingJob || (activeJob && (activeJob.status === 'pending' || activeJob.status === 'running')))}
                style={{ display: 'flex', alignItems: 'center', gap: '0.55rem', padding: '0.65rem 1.6rem', fontSize: '0.9rem', fontWeight: 700 }}
              >
                {isStartingJob ? (
                  <>
                    <RefreshCwIcon size={17} className="spin" /> Starting Discovery Pipeline...
                  </>
                ) : (
                  <>
                    <CompassIcon size={17} /> Discover Leads
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 4. Live Telemetry & Discovery Stages Panel */}
      {activeJob && (
        <div className="telemetry-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  JOB: {activeJob.id}
                </span>
                {getSourceBadge(activeJob.provider_used, true)}
                <span
                  className={`badge ${
                    activeJob.status === 'completed'
                      ? 'badge-active'
                      : activeJob.status === 'failed' || activeJob.status === 'cancelled'
                      ? 'badge-offline'
                      : 'badge-cyan'
                  }`}
                  style={{ fontSize: '0.7rem' }}
                >
                  {activeJob.status.toUpperCase()}
                </span>
              </div>
              <div style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '0.25rem' }}>
                {activeJob.current_stage || 'Pipeline in progress...'}
              </div>
            </div>

            {(activeJob.status === 'running' || activeJob.status === 'pending') && (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleCancelJob}
                disabled={isCancelling}
                style={{
                  color: '#f87171',
                  borderColor: 'rgba(248,113,113,0.3)',
                  padding: '0.45rem 0.95rem',
                  fontSize: '0.8rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.45rem',
                }}
              >
                <StopCircleIcon size={15} color="#f87171" />
                {isCancelling ? 'Cancelling Discovery...' : 'Cancel Discovery'}
              </button>
            )}
          </div>

          {/* Discovery Stage Stepper */}
          <div className="stage-stepper">
            {STAGE_STEPS.map((step, idx) => {
              const isDone = activeJob.status === 'completed' || idx < activeStageIndex;
              const isActive = activeJob.status === 'running' && idx === activeStageIndex;
              return (
                <div
                  key={step.id}
                  className={`stepper-item ${isDone ? 'completed' : ''} ${isActive ? 'active' : ''}`}
                >
                  <div className="stepper-circle">
                    {isDone ? <CheckIcon size={12} /> : step.id}
                  </div>
                  <div style={{ fontSize: '0.76rem', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {step.label}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Progress Bar */}
          <div style={{ width: '100%', height: '8px', background: 'var(--bg-tertiary)', borderRadius: '4px', overflow: 'hidden', margin: '0.75rem 0' }}>
            <div
              style={{
                width: `${activeJob.progress_percent}%`,
                height: '100%',
                background: 'linear-gradient(90deg, var(--accent-cyan), #3b82f6)',
                transition: 'width 0.3s ease',
              }}
            />
          </div>

          {/* Summary KPI Metrics Grid */}
          <div className="metrics-row">
            <div className="metric-card">
              <span className="metric-card-label">
                <BuildingIcon size={13} color="var(--accent-cyan)" /> Discovered Leads
              </span>
              <div className="metric-card-val">
                {activeJob.discovered_count}{' '}
                <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 500 }}>
                  / {activeJob.total_target}
                </span>
              </div>
            </div>

            <div className="metric-card">
              <span className="metric-card-label">
                <CheckCircleIcon size={13} color="#10b981" /> Verified Public Emails
              </span>
              <div className="metric-card-val" style={{ color: '#34d399' }}>
                {activeJob.verified_email_count}
              </div>
            </div>

            <div className="metric-card">
              <span className="metric-card-label">
                <FilterIcon size={13} color="var(--accent-cyan)" /> Duplicates Filtered
              </span>
              <div className="metric-card-val">
                {activeJob.duplicate_count}
              </div>
            </div>

            <div className="metric-card">
              <span className="metric-card-label">
                <AlertTriangleIcon size={13} color="#f87171" /> Failed / Skipped
              </span>
              <div className="metric-card-val" style={{ color: activeJob.failed_count + activeJob.skipped_count > 0 ? '#f87171' : 'var(--text-secondary)' }}>
                {activeJob.failed_count + activeJob.skipped_count}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 5. Discovered Leads Table & Management Suite */}
      <div className="leads-table-card">
        <div className="leads-toolbar">
          <div className="leads-toolbar-left">
            {/* Search Filter */}
            <div style={{ position: 'relative', flex: 1, minWidth: '220px' }}>
              <input
                type="text"
                className="form-input"
                placeholder="Search discovered companies, emails, or domains..."
                value={searchFilter}
                onChange={(e) => {
                  setSearchFilter(e.target.value);
                  setPage(1);
                }}
                style={{ paddingLeft: '2.1rem', width: '100%', fontSize: '0.82rem' }}
              />
              <div style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}>
                <SearchIcon size={14} color="var(--text-muted)" />
              </div>
            </div>

            {/* Email Verification Filter */}
            <select
              className="form-select"
              value={emailStatusFilter}
              onChange={(e) => {
                setEmailStatusFilter(e.target.value);
                setPage(1);
              }}
              style={{ width: '180px', fontSize: '0.8rem' }}
            >
              <option value="">All Verification States</option>
              <option value="verified_public">Verified / Public ({verificationCounts.verified_public || 0})</option>
              <option value="publicly_listed">Publicly Listed ({verificationCounts.publicly_listed || 0})</option>
              <option value="verified_by_provider">Provider Verified ({verificationCounts.verified_by_provider || 0})</option>
              <option value="needs_review">Needs Review ({verificationCounts.needs_review || 0})</option>
              <option value="found_unverified">Unverified ({verificationCounts.found_unverified || 0})</option>
              <option value="not_found">No Email Listed ({verificationCounts.not_found || 0})</option>
              <option value="invalid">Invalid ({verificationCounts.invalid || 0})</option>
            </select>

            {/* Sorting Dropdown */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <select
                className="form-select"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                style={{ width: '150px', fontSize: '0.8rem' }}
              >
                <option value="relevance_score">Sort: Relevance</option>
                <option value="discovered_at">Sort: Discovered Date</option>
                <option value="company_name">Sort: Company Name</option>
                <option value="email_verification_status">Sort: Email Status</option>
              </select>

              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setSortOrder((prev) => (prev === 'desc' ? 'asc' : 'desc'))}
                title={`Sort ${sortOrder === 'desc' ? 'Descending' : 'Ascending'}`}
                style={{ padding: '0.45rem 0.6rem' }}
              >
                <ArrowUpDownIcon size={14} />
              </button>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="leads-toolbar-right">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleExportCsv}
              disabled={!activeJob || leads.length === 0}
              style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.8rem' }}
              title="Download RFC 4180 CSV export"
            >
              <DownloadIcon size={14} /> Export CSV
            </button>

            <button
              type="button"
              className="btn btn-primary"
              onClick={() => handleTransferLeads(Array.from(selectedLeadIds))}
              disabled={isTransferring || selectedLeadIds.size === 0}
              style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.8rem', fontWeight: 600 }}
              title="Generate personalized software development outreach drafts for selected leads"
            >
              <SendIcon size={14} />
              {isTransferring && !transferringLeadId
                ? 'Creating Drafts...'
                : `Create Drafts for Selected Leads (${selectedLeadIds.size})`}
            </button>
          </div>
        </div>

        {/* Leads Table */}
        <div className="table-responsive-container">
          <table className="modern-leads-table">
            <thead>
              <tr>
                <th style={{ width: '36px', textAlign: 'center' }}>
                  <input
                    type="checkbox"
                    checked={selectedLeadIds.size === leads.length && leads.length > 0}
                    onChange={toggleSelectAllVisible}
                    aria-label="Select all leads"
                  />
                </th>
                <th>Company & Official Website</th>
                <th>Location</th>
                <th>Public Business Email</th>
                <th>Public Phone</th>
                <th>Source Evidence</th>
                <th style={{ textAlign: 'center' }}>Relevance</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {leads.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: '3.5rem 1rem' }}>
                    {isLoadingLeads ? (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.65rem' }}>
                        <RefreshCwIcon size={24} className="spin" color="var(--accent-cyan)" />
                        <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                          Querying search engine and verifying official sources...
                        </span>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
                        <CompassIcon size={36} color="var(--border-subtle)" />
                        <p style={{ margin: 0, fontWeight: 600, color: 'var(--text-secondary)' }}>
                          No leads discovered yet
                        </p>
                        <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                          Enter your research request above and click &quot;Discover Leads&quot; to begin.
                        </span>
                      </div>
                    )}
                  </td>
                </tr>
              ) : (
                leads.map((lead) => {
                  const isChecked = selectedLeadIds.has(lead.id);
                  const relevancePct = Math.round((lead.relevance_score || 0) * 100);

                  return (
                    <tr key={lead.id} className={isChecked ? 'selected' : ''}>
                      <td style={{ textAlign: 'center' }}>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleSelectLead(lead.id)}
                          aria-label={`Select ${lead.company_name}`}
                        />
                      </td>

                      <td>
                        <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '0.88rem' }}>
                          {lead.company_name}
                        </div>
                        {lead.website ? (
                          <a
                            href={lead.website}
                            target="_blank"
                            rel="noreferrer"
                            className="lead-link"
                            style={{ fontSize: '0.72rem', marginTop: '0.15rem' }}
                          >
                            {lead.website.replace(/^https?:\/\/(www\.)?/, '')} <ExternalLinkIcon size={11} />
                          </a>
                        ) : (
                          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>No website</span>
                        )}
                        {lead.verified_fields?.some((f) => f.startsWith('commercial_fit (evidence:')) && (
                          <div style={{ marginTop: '0.25rem' }}>
                            <span className="badge badge-active" style={{ fontSize: '0.64rem', padding: '0.08rem 0.35rem' }} title="Verified Commercial & Industrial Solar Work">
                              <CheckIcon size={10} /> C&I Solar Evidenced
                            </span>
                          </div>
                        )}
                      </td>

                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.78rem' }}>
                          <MapPinIcon size={13} color="var(--text-muted)" />
                          {[lead.city, lead.country].filter(Boolean).join(', ') || 'Global / Web'}
                        </div>
                      </td>

                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                          <span
                            style={{
                              fontFamily: 'var(--font-mono)',
                              fontSize: '0.78rem',
                              color: lead.email ? 'var(--text-primary)' : 'var(--text-muted)',
                            }}
                          >
                            {lead.email || '(None listed)'}
                          </span>
                          <div>{getVerificationBadge(lead.email_verification_status)}</div>
                        </div>
                      </td>

                      <td>
                        {lead.phone ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                            <PhoneIcon size={12} color={lead.phone_verification_status === 'needs_review' ? 'var(--accent-amber)' : 'var(--accent-cyan)'} />
                            <span>{lead.phone}</span>
                            {lead.phone_verification_status === 'needs_review' && (
                              <span className="badge badge-warning" style={{ fontSize: '0.62rem', padding: '0.05rem 0.3rem' }} title="Phone number flagged for operator review">
                                Needs Review
                              </span>
                            )}
                          </div>
                        ) : (
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>—</span>
                        )}
                      </td>

                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem', alignItems: 'flex-start' }}>
                          {getSourceBadge(lead.discovery_source, lead.is_live)}
                          {lead.source_urls && lead.source_urls.length > 0 && (
                            <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                              {lead.source_urls.length} verified URL{lead.source_urls.length > 1 ? 's' : ''}
                            </span>
                          )}
                        </div>
                      </td>

                      <td style={{ textAlign: 'center' }}>
                        <span
                          className={`badge ${
                            relevancePct >= 80 ? 'badge-active' : relevancePct >= 60 ? 'badge-cyan' : 'badge-warning'
                          }`}
                          style={{ fontSize: '0.72rem', fontWeight: 700 }}
                        >
                          {relevancePct}%
                        </span>
                      </td>

                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'flex-end', gap: '0.4rem' }}>
                          <button
                            type="button"
                            className="btn btn-primary"
                            onClick={() => handleTransferLeads([lead.id], lead.company_name)}
                            disabled={isTransferring && transferringLeadId === lead.id}
                            style={{
                              padding: '0.3rem 0.65rem',
                              fontSize: '0.74rem',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.35rem',
                              fontWeight: 600,
                            }}
                            title="Generate personalized software development outreach draft for this lead"
                          >
                            {isTransferring && transferringLeadId === lead.id ? (
                              <>
                                <RefreshCwIcon size={11} className="spin" /> Drafting...
                              </>
                            ) : (
                              <>
                                <SendIcon size={11} /> Create Draft
                              </>
                            )}
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={() => setEvidenceLead(lead)}
                            style={{ padding: '0.3rem 0.65rem', fontSize: '0.74rem', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}
                            title="View verified source evidence and facts"
                          >
                            <EyeIcon size={12} /> Evidence
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        {totalLeads > 0 && (
          <div className="pagination-bar">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              <span>
                Showing {leads.length} of {totalLeads} discovered leads
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <span>Page size:</span>
                <select
                  className="form-select"
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(parseInt(e.target.value) || 15);
                    setPage(1);
                  }}
                  style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', width: '65px' }}
                >
                  <option value={10}>10</option>
                  <option value={15}>15</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                </select>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                style={{ padding: '0.35rem 0.65rem' }}
                aria-label="Previous page"
              >
                <ChevronLeftIcon size={14} />
              </button>
              <span style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem', color: 'var(--text-secondary)' }}>
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
                style={{ padding: '0.35rem 0.65rem' }}
                aria-label="Next page"
              >
                <ChevronRightIcon size={14} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 6. Lead Evidence Modal */}
      {evidenceLead && (
        <div
          className="modal-overlay"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(6px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: '1rem',
          }}
          onClick={() => setEvidenceLead(null)}
        >
          <div
            className="modal-container"
            style={{
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '14px',
              maxWidth: '720px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              padding: '1.75rem',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.25rem' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                    {evidenceLead.company_name}
                  </h3>
                  {getSourceBadge(evidenceLead.discovery_source, evidenceLead.is_live)}
                </div>
                {evidenceLead.website ? (
                  <a
                    href={evidenceLead.website}
                    target="_blank"
                    rel="noreferrer"
                    style={{ fontSize: '0.82rem', color: 'var(--accent-cyan)', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.3rem', marginTop: '0.2rem' }}
                  >
                    {evidenceLead.website} <ExternalLinkIcon size={12} />
                  </a>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => setEvidenceLead(null)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '0.2rem' }}
                aria-label="Close evidence"
              >
                <XIcon size={20} />
              </button>
            </div>

            {/* Quick Metadata Grid: Discovery Method, Query, Email, Phone */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem', marginBottom: '1.25rem' }}>
              <div style={{ background: 'var(--bg-tertiary)', padding: '0.75rem 0.95rem', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Discovery Method</span>
                <div style={{ marginTop: '0.25rem' }}>
                  {getSourceBadge(evidenceLead.discovery_source, evidenceLead.is_live)}
                </div>
              </div>

              <div style={{ background: 'var(--bg-tertiary)', padding: '0.75rem 0.95rem', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Discovery Query</span>
                <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.2rem', fontFamily: 'var(--font-mono)' }}>
                  &quot;{evidenceLead.discovery_query || 'N/A'}&quot;
                </div>
              </div>

              <div style={{ background: 'var(--bg-tertiary)', padding: '0.75rem 0.95rem', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Public Email</span>
                <div style={{ fontSize: '0.78rem', fontFamily: 'var(--font-mono)', marginTop: '0.15rem' }}>
                  {evidenceLead.email || '(None listed)'}
                </div>
                <div style={{ marginTop: '0.25rem' }}>{getVerificationBadge(evidenceLead.email_verification_status)}</div>
              </div>

              <div style={{ background: 'var(--bg-tertiary)', padding: '0.75rem 0.95rem', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Public Phone</span>
                <div style={{ fontSize: '0.78rem', fontFamily: 'var(--font-mono)', marginTop: '0.15rem' }}>
                  {evidenceLead.phone || '(None listed)'}
                </div>
                <div style={{ marginTop: '0.25rem' }}>
                  {evidenceLead.phone_verification_status === 'needs_review' ? (
                    <span className="badge badge-warning" style={{ fontSize: '0.65rem' }}>Needs Review</span>
                  ) : evidenceLead.phone ? (
                    <span className="badge badge-active" style={{ fontSize: '0.65rem' }}>Publicly Listed</span>
                  ) : (
                    <span className="badge" style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>None Listed</span>
                  )}
                </div>
              </div>
            </div>

            {/* Commercial-Fit and Lahore Presence Evidence */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '1.25rem' }}>
              <div style={{ background: 'var(--bg-tertiary)', padding: '0.75rem 0.95rem', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '0.7rem', color: 'var(--accent-cyan)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Commercial & Industrial Fit Evidence
                </span>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.35rem', lineHeight: 1.4 }}>
                  {evidenceLead.verified_fields?.find((f) => f.startsWith('commercial_fit')) ||
                    'General commercial solar EPC services (refer to business description)'}
                </div>
              </div>

              <div style={{ background: 'var(--bg-tertiary)', padding: '0.75rem 0.95rem', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                <span style={{ fontSize: '0.7rem', color: 'var(--accent-emerald)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Lahore Office & Service Coverage
                </span>
                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.35rem', lineHeight: 1.4 }}>
                  {evidenceLead.verified_fields?.find((f) => f.startsWith('lahore_presence') || f.toLowerCase().includes('lahore')) ||
                    `Location: ${[evidenceLead.city, evidenceLead.country].filter(Boolean).join(', ') || 'Lahore, Pakistan'}`}
                </div>
              </div>
            </div>

            {/* Relevance Explanation */}
            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ fontSize: '0.76rem', fontWeight: 700, color: 'var(--text-muted)', display: 'block', marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                AI Relevance Explanation:
              </label>
              <div style={{ background: 'var(--bg-tertiary)', padding: '0.75rem 1rem', borderRadius: '8px', fontSize: '0.84rem', color: 'var(--text-primary)', lineHeight: 1.5, border: '1px solid var(--border-subtle)' }}>
                {evidenceLead.relevance_explanation}
              </div>
            </div>

            {/* Business Services Description */}
            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ fontSize: '0.76rem', fontWeight: 700, color: 'var(--text-muted)', display: 'block', marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Public Business & Services Description:
              </label>
              <div style={{ background: 'var(--bg-tertiary)', padding: '0.75rem 1rem', borderRadius: '8px', fontSize: '0.84rem', color: 'var(--text-secondary)', lineHeight: 1.5, border: '1px solid var(--border-subtle)' }}>
                {evidenceLead.services_description || 'No public business description extracted.'}
              </div>
            </div>

            {/* Source URLs */}
            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ fontSize: '0.76rem', fontWeight: 700, color: 'var(--text-muted)', display: 'block', marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Direct Source Evidence URLs:
              </label>
              <div style={{ background: 'var(--bg-tertiary)', padding: '0.75rem 1rem', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                {evidenceLead.source_urls && evidenceLead.source_urls.length > 0 ? (
                  <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.8rem', color: 'var(--accent-cyan)' }}>
                    {evidenceLead.source_urls.map((u, i) => (
                      <li key={i} style={{ marginBottom: '0.35rem', wordBreak: 'break-all' }}>
                        <a href={u} target="_blank" rel="noreferrer" style={{ color: 'inherit', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                          {u} <ExternalLinkIcon size={11} />
                        </a>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>No external source URLs recorded.</span>
                )}
              </div>
            </div>

            {/* Confirmed Verified Fields */}
            <div>
              <label style={{ fontSize: '0.76rem', fontWeight: 700, color: 'var(--text-muted)', display: 'block', marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Confirmed Verified Fields on Official Pages:
              </label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                {evidenceLead.verified_fields && evidenceLead.verified_fields.length > 0 ? (
                  evidenceLead.verified_fields.map((f, i) => (
                    <span key={i} className="badge badge-active" style={{ fontSize: '0.72rem' }}>
                      <CheckIcon size={11} /> {f}
                    </span>
                  ))
                ) : (
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>None recorded</span>
                )}
              </div>
            </div>

            <div style={{ marginTop: '1.75rem', display: 'flex', justifyContent: 'flex-end', gap: '0.65rem', alignItems: 'center' }}>
              <button type="button" className="btn btn-secondary" onClick={() => setEvidenceLead(null)}>
                Close Evidence
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  handleTransferLeads([evidenceLead.id], evidenceLead.company_name);
                }}
                disabled={isTransferring}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.45rem', fontWeight: 600 }}
              >
                <SendIcon size={14} />
                {isTransferring && transferringLeadId === evidenceLead.id ? 'Drafting...' : 'Create Outreach Draft'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LeadDiscovery;
