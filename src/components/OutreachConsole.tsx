import React, { useState, useEffect, useCallback } from 'react';
import {
  LeadRecord,
  OutreachDraft,
  AIProviderConfig,
  AIProviderInfo,
  DispatchStatusInfo,
} from '../types/agent';
import { BackendStatus } from '../hooks/useBackendStatus';
import {
  fetchAIProviders,
  draftOutreach,
  sendOutreach,
} from '../services/api';
import {
  MailIcon,
  SparklesIcon,
  ShieldAlertIcon,
  CheckCircleIcon,
  AlertTriangleIcon,
  SendIcon,
  EditIcon,
  CheckIcon,
  CopyIcon,
  XIcon,
  ExternalLinkIcon,
  RefreshCwIcon,
  SettingsIcon,
  BuildingIcon,
} from './icons';

interface OutreachConsoleProps {
  selectedLeads: LeadRecord[];
  allLeadsCount: number;
  onSelectAll?: () => void;
  onSelectVerified?: () => void;
  onLogAudit?: (type: 'success' | 'error' | 'info', message: string) => void;
  onDraftCountChange?: (count: number) => void;
  backendStatus?: BackendStatus;
}

export const OutreachConsole: React.FC<OutreachConsoleProps> = ({
  selectedLeads,
  allLeadsCount,
  onSelectAll,
  onSelectVerified,
  onLogAudit,
  onDraftCountChange,
  backendStatus,
}) => {
  // Provider Configuration State
  const [availableProviders, setAvailableProviders] = useState<AIProviderInfo[]>([]);
  const [dispatchStatus, setDispatchStatus] = useState<DispatchStatusInfo | null>(null);
  const [isRefreshingDispatch, setIsRefreshingDispatch] = useState<boolean>(false);
  const [providerType, setProviderType] = useState<'template' | 'ollama' | 'openai'>('template');
  const [modelName, setModelName] = useState<string>('gpt-4o-mini');
  const [apiBase, setApiBase] = useState<string>('https://api.openai.com/v1');
  const [apiKey, setApiKey] = useState<string>('');
  const [showApiKey, setShowApiKey] = useState<boolean>(false);
  const [showConfigPanel, setShowConfigPanel] = useState<boolean>(false);

  // Outreach Personalization Parameters
  const [serviceOffering, setServiceOffering] = useState<string>(
    'AI workflow automation & custom web intelligence pipelines'
  );
  const [tone, setTone] = useState<'professional' | 'consultative' | 'concise'>('professional');
  const [senderName, setSenderName] = useState<string>('Operator');
  const [senderCompany, setSenderCompany] = useState<string>('AgentDesk');

  // Drafts & Workflow State
  const [drafts, setDrafts] = useState<OutreachDraft[]>([]);
  const [isDrafting, setIsDrafting] = useState<boolean>(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [copiedDraftId, setCopiedDraftId] = useState<string | null>(null);

  // Send Confirmation Modal State
  const [confirmModalDraft, setConfirmModalDraft] = useState<OutreachDraft | null>(null);
  const [isSending, setIsSending] = useState<boolean>(false);
  const [sendSuccessMessage, setSendSuccessMessage] = useState<string | null>(null);
  const [sendErrorMessage, setSendErrorMessage] = useState<string | null>(null);

  // Fetch or refresh dispatch status and AI providers
  const refreshDispatchStatus = useCallback(async () => {
    setIsRefreshingDispatch(true);
    try {
      const res = await fetchAIProviders();
      if (res.providers) setAvailableProviders(res.providers);
      if (res.dispatch) setDispatchStatus(res.dispatch);
    } catch {
      // Keep previous cached status on error
    } finally {
      setIsRefreshingDispatch(false);
    }
  }, []);

  // Load available providers and dispatch status on mount
  useEffect(() => {
    refreshDispatchStatus();
  }, [refreshDispatchStatus]);

  // Automatically refresh when backend restarts or transitions to online
  useEffect(() => {
    if (backendStatus?.isOnline) {
      refreshDispatchStatus();
    }
  }, [backendStatus?.isOnline, refreshDispatchStatus]);

  // Update parent with pending drafts count
  useEffect(() => {
    const pending = drafts.filter((d) => d.status === 'drafted' || d.status === 'approved').length;
    if (onDraftCountChange) {
      onDraftCountChange(pending);
    }
  }, [drafts, onDraftCountChange]);

  // Adjust defaults when provider type changes
  const handleProviderTypeChange = (newType: 'template' | 'ollama' | 'openai') => {
    setProviderType(newType);
    if (newType === 'ollama') {
      setModelName('mistral');
      setApiBase('http://localhost:11434/v1');
    } else if (newType === 'openai') {
      setModelName('gpt-4o-mini');
      setApiBase('https://api.openai.com/v1');
    }
  };

  // Generate drafts for selected leads
  const handleGenerateDrafts = async () => {
    if (selectedLeads.length === 0) {
      setDraftError('Please select at least one lead from the table above to draft outreach.');
      return;
    }

    if (!serviceOffering.trim()) {
      setDraftError('Please specify your service or value proposition offering.');
      return;
    }

    if (providerType === 'openai' && !apiKey.trim()) {
      setDraftError('Cloud AI Provider requires an API key. Enter it in Provider Settings.');
      setShowConfigPanel(true);
      return;
    }

    setDraftError(null);
    setSendSuccessMessage(null);
    setSendErrorMessage(null);
    setIsDrafting(true);

    const aiConfig: AIProviderConfig = {
      provider_type: providerType,
      model_name: providerType !== 'template' ? modelName.trim() : undefined,
      api_base: providerType !== 'template' ? apiBase.trim() : undefined,
      api_key: providerType === 'openai' ? apiKey.trim() : undefined,
    };

    onLogAudit?.(
      'info',
      `Launching AI outreach drafting for ${selectedLeads.length} selected lead(s) using ${providerType.toUpperCase()} provider...`
    );

    try {
      const response = await draftOutreach({
        leads: selectedLeads,
        service_offering: serviceOffering.trim(),
        tone,
        sender_name: senderName.trim() || 'Growth Team',
        sender_company: senderCompany.trim() || 'AgentDesk',
        ai_config: aiConfig,
      });

      setDrafts(response.drafts);
      onLogAudit?.(
        'success',
        `Drafted ${response.total} outreach messages (${response.verified_email_count} with verified email, ${response.missing_email_count} missing email) via ${response.provider_used}.`
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to generate outreach drafts';
      setDraftError(msg);
      onLogAudit?.('error', `Outreach drafting failed: ${msg}`);
    } finally {
      setIsDrafting(false);
    }
  };

  // Edit draft subject or body
  const handleUpdateDraft = (draftId: string, field: 'subject' | 'body', value: string) => {
    setDrafts((prev) =>
      prev.map((d) => {
        if (d.id === draftId) {
          return { ...d, [field]: value };
        }
        return d;
      })
    );
  };

  // Toggle approval state
  const handleToggleApproval = (draftId: string) => {
    setDrafts((prev) =>
      prev.map((d) => {
        if (d.id === draftId) {
          if (!d.has_verified_email) return d; // Cannot approve leads without verified email
          const newStatus = d.status === 'approved' ? 'drafted' : 'approved';
          onLogAudit?.(
            'info',
            `Lead "${d.company_name}" draft marked as ${newStatus.toUpperCase()} by operator.`
          );
          return { ...d, status: newStatus };
        }
        return d;
      })
    );
  };

  // Copy draft to clipboard
  const handleCopyDraft = async (draft: OutreachDraft) => {
    const formatted = `Subject: ${draft.subject}\n\n${draft.body}`;
    try {
      await navigator.clipboard.writeText(formatted);
      setCopiedDraftId(draft.id);
      setTimeout(() => setCopiedDraftId(null), 2500);
    } catch {
      // Fallback
    }
  };

  // Open confirmation modal for approved draft
  const handleInitiateSend = (draft: OutreachDraft) => {
    if (!draft.has_verified_email) {
      setSendErrorMessage(`Cannot send to ${draft.company_name}: No verified public email address.`);
      return;
    }
    if (draft.status !== 'approved') {
      setSendErrorMessage(`Approval required: You must explicitly approve the draft for ${draft.company_name} before sending.`);
      return;
    }
    setSendErrorMessage(null);
    setConfirmModalDraft(draft);
  };

  // Execute explicit send upon confirmation
  const handleConfirmSend = async () => {
    if (!confirmModalDraft) return;

    setIsSending(true);
    setSendErrorMessage(null);
    setSendSuccessMessage(null);

    try {
      const response = await sendOutreach({
        draft_id: confirmModalDraft.id,
        approved: true,
        recipient_email: confirmModalDraft.recipient_email,
        subject: confirmModalDraft.subject,
        body: confirmModalDraft.body,
        has_verified_email: confirmModalDraft.has_verified_email,
      });

      const isSim = response.is_simulated ?? true;
      if (!response || response.status === 'failed') {
        throw new Error(response?.message || 'Outreach dispatch was rejected by the provider.');
      }
      // Update draft status to sent and note simulation vs live
      setDrafts((prev) =>
        prev.map((d) =>
          d.id === confirmModalDraft.id
            ? {
                ...d,
                status: 'sent' as const,
                grounding_notes: isSim
                  ? 'Dispatched via simulation mode (safe offline)'
                  : `Dispatched via ${response.provider || 'live provider'}`,
              }
            : d
        )
      );

      const msg = isSim
        ? `[SIMULATION ONLY] Approved draft for ${response.recipient_email} (${confirmModalDraft.company_name}). No real email was delivered (Simulation Mode).`
        : `[LIVE DISPATCH] Real email transmitted via ${response.provider || 'configured provider'} to ${response.recipient_email} (${confirmModalDraft.company_name}).`;

      setSendSuccessMessage(msg);
      onLogAudit?.(isSim ? 'info' : 'success', msg);
      setConfirmModalDraft(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Outbound transmission failed';
      setSendErrorMessage(msg);
      onLogAudit?.('error', `Send failed for ${confirmModalDraft.company_name}: ${msg}`);
    } finally {
      setIsSending(false);
    }
  };

  const verifiedEmailCount = selectedLeads.filter(
    (l) => l.email && l.email.includes('@') && !l.email.includes('(No public')
  ).length;
  const missingEmailCount = selectedLeads.length - verifiedEmailCount;

  return (
    <div className="card" style={{ marginTop: '1.5rem', border: '1px solid rgba(99, 102, 241, 0.3)' }}>
      {/* Header */}
      <div className="card-header" style={{ flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(6, 182, 212, 0.25))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <MailIcon size={18} color="var(--accent-cyan)" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <h3 className="card-title" style={{ fontSize: '1.05rem', margin: 0 }}>
                AI Personalized Outreach Drafting Agent
              </h3>
              <span className="badge badge-active" style={{ fontSize: '0.65rem' }}>
                Zero-Hallucination Grounded
              </span>
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
              Drafts high-converting, personalized outreach strictly grounded in verified public company data.
            </p>
          </div>
        </div>

        {/* Lead Selection Summary & Settings Toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              background: 'rgba(15, 23, 42, 0.8)',
              padding: '0.35rem 0.65rem',
              borderRadius: '6px',
              border: '1px solid var(--border-subtle)',
              fontSize: '0.75rem',
            }}
          >
            <span style={{ color: 'var(--text-muted)' }}>Selected:</span>
            <span style={{ fontWeight: 700, color: selectedLeads.length > 0 ? 'var(--accent-cyan)' : 'var(--text-muted)' }}>
              {selectedLeads.length} / {allLeadsCount}
            </span>
            {selectedLeads.length > 0 && (
              <>
                <span style={{ color: 'var(--border-subtle)' }}>|</span>
                <span style={{ color: '#34d399', fontSize: '0.7rem' }}>
                  {verifiedEmailCount} verified
                </span>
                {missingEmailCount > 0 && (
                  <span style={{ color: '#fbbf24', fontSize: '0.7rem' }}>
                    {missingEmailCount} missing
                  </span>
                )}
              </>
            )}
          </div>

          {allLeadsCount > 0 && (
            <div style={{ display: 'flex', gap: '0.35rem' }}>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ fontSize: '0.72rem', padding: '0.3rem 0.6rem' }}
                onClick={onSelectAll}
                title="Select all extracted leads"
              >
                Select All
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ fontSize: '0.72rem', padding: '0.3rem 0.6rem' }}
                onClick={onSelectVerified}
                title="Select only leads that contain a verified public email"
              >
                Select Verified
              </button>
            </div>
          )}

          <button
            type="button"
            className={`btn btn-secondary ${showConfigPanel ? 'active' : ''}`}
            onClick={() => {
              setShowConfigPanel((prev) => {
                const next = !prev;
                if (next) refreshDispatchStatus();
                return next;
              });
            }}
            style={{ fontSize: '0.75rem', padding: '0.35rem 0.7rem' }}
          >
            <SettingsIcon size={13} color="var(--accent-cyan)" />
            AI Provider Settings
          </button>
        </div>
      </div>

      {/* Safety Policy Reminder Banner */}
      <div
        style={{
          background: 'rgba(99, 102, 241, 0.08)',
          border: '1px solid rgba(99, 102, 241, 0.25)',
          borderRadius: '8px',
          padding: '0.75rem 1rem',
          marginBottom: '1.25rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1rem',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <ShieldAlertIcon size={16} color="var(--accent-indigo)" />
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            <strong style={{ color: 'var(--text-primary)' }}>Human-in-the-Loop Safety Gate:</strong> Every draft can be edited before dispatch.
            Leads without a verified email are automatically blocked from transmission. Sending requires explicit operator confirmation.
          </span>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <span className="badge badge-cyan" style={{ fontSize: '0.65rem' }}>
            AI Drafter: {providerType.toUpperCase()}
          </span>
          {dispatchStatus?.is_live ? (
            <span
              className="badge badge-active"
              style={{ fontSize: '0.65rem' }}
              title={dispatchStatus.notice}
            >
              Dispatch: {dispatchStatus.mode.toUpperCase()} ({dispatchStatus.from_email})
            </span>
          ) : (
            <span
              className="badge badge-warning"
              style={{ fontSize: '0.65rem' }}
              title="Simulation Mode: No real email delivered unless SMTP configured in .env"
            >
              Dispatch: Simulation Mode (Safe Offline)
            </span>
          )}
          <button
            type="button"
            className="btn btn-secondary"
            onClick={refreshDispatchStatus}
            disabled={isRefreshingDispatch}
            title="Recheck dispatch configuration from backend or root .env"
            style={{ fontSize: '0.68rem', padding: '0.22rem 0.55rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}
          >
            <RefreshCwIcon size={11} color="var(--accent-cyan)" />
            {isRefreshingDispatch ? 'Checking...' : 'Check Status'}
          </button>
        </div>
      </div>

      {/* AI Provider & Engine Configuration (Collapsible) */}
      {showConfigPanel && (
        <div
          style={{
            background: 'rgba(15, 23, 42, 0.85)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '8px',
            padding: '1.1rem',
            marginBottom: '1.25rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '1rem',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
            <h4 style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <SettingsIcon size={14} color="var(--accent-cyan)" />
              AI Drafter Provider Configuration
            </h4>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              {availableProviders.map((p) => (
                <span
                  key={p.id}
                  className="badge badge-active"
                  style={{ fontSize: '0.62rem' }}
                  title={p.description}
                >
                  {p.name}: Ready
                </span>
              ))}
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                (Keys never persisted to disk)
              </span>
            </div>
          </div>

          {/* Provider Selection Buttons */}
          <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              className={`mode-switch-btn ${providerType === 'template' ? 'active' : ''}`}
              onClick={() => handleProviderTypeChange('template')}
              style={{ padding: '0.45rem 0.85rem' }}
            >
              <SparklesIcon size={13} color={providerType === 'template' ? 'var(--accent-cyan)' : 'var(--text-muted)'} />
              Built-in Grounded Drafter (Deterministic / Offline)
            </button>
            <button
              type="button"
              className={`mode-switch-btn ${providerType === 'ollama' ? 'active' : ''}`}
              onClick={() => handleProviderTypeChange('ollama')}
              style={{ padding: '0.45rem 0.85rem' }}
            >
              <BuildingIcon size={13} color={providerType === 'ollama' ? 'var(--accent-cyan)' : 'var(--text-muted)'} />
              Local Ollama (Offline LLM)
            </button>
            <button
              type="button"
              className={`mode-switch-btn ${providerType === 'openai' ? 'active' : ''}`}
              onClick={() => handleProviderTypeChange('openai')}
              style={{ padding: '0.45rem 0.85rem' }}
            >
              <MailIcon size={13} color={providerType === 'openai' ? 'var(--accent-cyan)' : 'var(--text-muted)'} />
              Cloud OpenAI-Compatible (OpenAI, Groq, OpenRouter)
            </button>
          </div>

          {/* Provider Specific Inputs */}
          {providerType === 'template' && (
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', background: 'rgba(6, 182, 212, 0.08)', padding: '0.6rem 0.8rem', borderRadius: '6px', border: '1px solid rgba(6, 182, 212, 0.2)' }}>
              &bull; <strong>100% Zero-Hallucination:</strong> Deterministically composes professional outreach solely using the lead&apos;s verified public metadata, company description, and verified extraction fields. Runs instantly with zero cloud dependency.
            </div>
          )}

          {providerType === 'ollama' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0.75rem' }}>
              <div className="form-group">
                <label className="form-label">Ollama Model Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={modelName}
                  onChange={(e) => setModelName(e.target.value)}
                  placeholder="e.g. mistral, llama3, qwen2.5"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Ollama API Base URL</label>
                <input
                  type="text"
                  className="form-input"
                  value={apiBase}
                  onChange={(e) => setApiBase(e.target.value)}
                  placeholder="http://localhost:11434/v1"
                />
              </div>
            </div>
          )}

          {providerType === 'openai' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.75rem' }}>
              <div className="form-group">
                <label className="form-label">Cloud Model Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={modelName}
                  onChange={(e) => setModelName(e.target.value)}
                  placeholder="e.g. gpt-4o-mini, llama-3.3-70b-versatile"
                />
              </div>
              <div className="form-group">
                <label className="form-label">API Base URL</label>
                <input
                  type="text"
                  className="form-input"
                  value={apiBase}
                  onChange={(e) => setApiBase(e.target.value)}
                  placeholder="https://api.openai.com/v1"
                />
              </div>
              <div className="form-group">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <label className="form-label">API Key (Session Only)</label>
                  <button
                    type="button"
                    onClick={() => setShowApiKey((p) => !p)}
                    style={{ background: 'none', border: 'none', color: 'var(--accent-cyan)', fontSize: '0.68rem', cursor: 'pointer' }}
                  >
                    {showApiKey ? 'Hide' : 'Show'}
                  </button>
                </div>
                <input
                  type={showApiKey ? 'text' : 'password'}
                  className="form-input"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-... (never stored in files)"
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Campaign & Value Proposition Parameters */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: '1rem',
          marginBottom: '1.25rem',
        }}
      >
        <div className="form-group" style={{ gridColumn: 'span 2' }}>
          <label className="form-label">
            Your Service / Value Proposition Offering:
          </label>
          <input
            type="text"
            className="form-input"
            value={serviceOffering}
            onChange={(e) => setServiceOffering(e.target.value)}
            placeholder="e.g. AI workflow automation & custom web intelligence pipelines"
            disabled={isDrafting}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Outreach Tone:</label>
          <select
            className="form-select"
            value={tone}
            onChange={(e) => setTone(e.target.value as any)}
            disabled={isDrafting}
            style={{ width: '100%', padding: '0.55rem 0.85rem', fontSize: '0.82rem' }}
          >
            <option value="professional">Professional & Direct</option>
            <option value="consultative">Consultative & Value-Focused</option>
            <option value="concise">Concise & Action-Oriented</option>
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Sender Signature Name:</label>
          <input
            type="text"
            className="form-input"
            value={senderName}
            onChange={(e) => setSenderName(e.target.value)}
            placeholder="e.g. Alex (Growth Lead)"
            disabled={isDrafting}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Sender Organization:</label>
          <input
            type="text"
            className="form-input"
            value={senderCompany}
            onChange={(e) => setSenderCompany(e.target.value)}
            placeholder="e.g. AgentDesk"
            disabled={isDrafting}
          />
        </div>
      </div>

      {/* Action Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.75rem',
          paddingTop: '0.75rem',
          borderTop: '1px solid var(--border-subtle)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleGenerateDrafts}
            disabled={isDrafting || selectedLeads.length === 0}
          >
            {isDrafting ? (
              <>
                <div className="spinner" />
                Generating Personalized Drafts...
              </>
            ) : (
              <>
                <SparklesIcon size={14} color="white" />
                Generate Personalized Drafts ({selectedLeads.length})
              </>
            )}
          </button>

          {drafts.length > 0 && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setDrafts([]);
                setDraftError(null);
                setSendSuccessMessage(null);
              }}
              disabled={isDrafting}
            >
              <RefreshCwIcon size={13} color="var(--text-secondary)" />
              Clear Drafts
            </button>
          )}
        </div>

        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          {selectedLeads.length === 0
            ? 'Select leads in the table above to enable drafting'
            : `Ready to draft personalized emails for ${selectedLeads.length} lead(s)`}
        </span>
      </div>

      {/* Alerts */}
      {draftError && (
        <div
          style={{
            marginTop: '1rem',
            background: 'rgba(239, 68, 68, 0.12)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: '8px',
            padding: '0.65rem 0.9rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.78rem',
            color: '#fca5a5',
          }}
        >
          <AlertTriangleIcon size={16} color="#f87171" />
          <span>{draftError}</span>
        </div>
      )}

      {sendSuccessMessage && (
        <div
          style={{
            marginTop: '1rem',
            background: 'rgba(16, 185, 129, 0.12)',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            borderRadius: '8px',
            padding: '0.65rem 0.9rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.78rem',
            color: '#34d399',
          }}
        >
          <CheckCircleIcon size={16} color="#34d399" />
          <span>{sendSuccessMessage}</span>
        </div>
      )}

      {sendErrorMessage && (
        <div
          style={{
            marginTop: '1rem',
            background: 'rgba(239, 68, 68, 0.12)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: '8px',
            padding: '0.65rem 0.9rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.78rem',
            color: '#fca5a5',
          }}
        >
          <AlertTriangleIcon size={16} color="#f87171" />
          <span>{sendErrorMessage}</span>
        </div>
      )}

      {/* Loading State */}
      {isDrafting && (
        <div
          style={{
            marginTop: '1.25rem',
            background: 'rgba(10, 14, 23, 0.5)',
            border: '1px solid var(--border-active)',
            borderRadius: '8px',
            padding: '2.5rem 1.5rem',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '0.75rem',
          }}
        >
          <div className="spinner" style={{ width: 24, height: 24, borderWidth: 3 }} />
          <div>
            <p style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '0.9rem' }}>
              Synthesizing Grounded Outreach Drafts...
            </p>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
              Extracting verified company facts &bull; Framing business value &bull; Enforcing zero-hallucination rules
            </p>
          </div>
        </div>
      )}

      {/* Empty State when no drafts generated */}
      {!isDrafting && drafts.length === 0 && (
        <div
          style={{
            marginTop: '1.25rem',
            background: 'rgba(10, 14, 23, 0.4)',
            border: '1px dashed var(--border-subtle)',
            borderRadius: '8px',
            padding: '2.5rem 1.5rem',
            textAlign: 'center',
            color: 'var(--text-muted)',
          }}
        >
          <MailIcon size={32} color="var(--border-subtle)" />
          <p style={{ marginTop: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            No Outreach Drafts Generated Yet
          </p>
          <p style={{ fontSize: '0.75rem', maxWidth: '440px', margin: '0.35rem auto 0 auto' }}>
            {selectedLeads.length === 0
              ? 'Select one or more leads from the table above using the checkboxes, then click Generate Personalized Drafts.'
              : `Click "Generate Personalized Drafts (${selectedLeads.length})" to synthesize grounded outreach.`}
          </p>
        </div>
      )}

      {/* Drafts Review Workspace */}
      {!isDrafting && drafts.length > 0 && (
        <div style={{ marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Generated Outreach Drafts ({drafts.length})
            </span>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              Operator Review & Editing Mode: Edit subject and body directly, then approve for sending
            </span>
          </div>

          {drafts.map((draft) => {
            const isApproved = draft.status === 'approved';
            const isSent = draft.status === 'sent';
            const hasVerifiedEmail = draft.has_verified_email;

            return (
              <div
                key={draft.id}
                className="outreach-draft-card"
                style={{
                  background: 'rgba(15, 23, 42, 0.75)',
                  border: isSent
                    ? '1px solid rgba(99, 102, 241, 0.4)'
                    : isApproved
                    ? '1px solid rgba(16, 185, 129, 0.4)'
                    : '1px solid var(--border-subtle)',
                  borderRadius: '10px',
                  padding: '1.25rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.85rem',
                  transition: 'border-color 0.2s ease',
                }}
              >
                {/* Draft Card Header */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                        <BuildingIcon size={14} color="var(--accent-cyan)" />
                        {draft.company_name}
                      </span>

                      {/* Status Badge */}
                      {isSent ? (
                        <span
                          className={draft.grounding_notes?.includes('simulation') ? 'badge badge-warning' : 'badge badge-cyan'}
                          style={{ fontSize: '0.65rem' }}
                        >
                          <CheckCircleIcon size={10} color={draft.grounding_notes?.includes('simulation') ? '#fbbf24' : 'var(--accent-cyan)'} />
                          {draft.grounding_notes?.includes('simulation') ? 'Dispatched (Simulation)' : 'Dispatched (Live Provider)'}
                        </span>
                      ) : isApproved ? (
                        <span className="badge badge-active" style={{ fontSize: '0.65rem' }}>
                          <CheckIcon size={10} color="#34d399" />
                          Approved
                        </span>
                      ) : (
                        <span className="badge badge-warning" style={{ fontSize: '0.65rem' }}>
                          Draft (Pending Review)
                        </span>
                      )}

                      {/* Verified Email Badge */}
                      {hasVerifiedEmail ? (
                        <span
                          className="tag-verified"
                          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}
                          title={`Recipient Email: ${draft.recipient_email}`}
                        >
                          <CheckCircleIcon size={10} color="#34d399" />
                          Verified Email: {draft.recipient_email}
                        </span>
                      ) : (
                        <span
                          className="tag-unverified"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.25rem',
                            color: '#fbbf24',
                            borderColor: 'rgba(245, 158, 11, 0.3)',
                            background: 'rgba(245, 158, 11, 0.1)',
                          }}
                          title="No verified email extracted from public web source"
                        >
                          <AlertTriangleIcon size={10} color="#fbbf24" />
                          No Public Email Listed (Dispatch Blocked)
                        </span>
                      )}
                    </div>

                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.25rem' }}>
                      <span>Recipient: {draft.recipient_name}</span>
                      {draft.source_url && draft.source_url.startsWith('http') && (
                        <>
                          <span>&bull;</span>
                          <a
                            href={draft.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="lead-link"
                            style={{ fontSize: '0.72rem' }}
                          >
                            Source Page
                            <ExternalLinkIcon size={10} color="var(--accent-cyan)" />
                          </a>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Top Right Quick Actions */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => handleCopyDraft(draft)}
                      style={{ fontSize: '0.72rem', padding: '0.3rem 0.65rem' }}
                      title="Copy subject and body to clipboard"
                    >
                      {copiedDraftId === draft.id ? (
                        <>
                          <CheckIcon size={12} color="#34d399" />
                          Copied!
                        </>
                      ) : (
                        <>
                          <CopyIcon size={12} color="var(--text-secondary)" />
                          Copy Draft
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* Grounding Facts Notice */}
                {draft.verified_facts_used && draft.verified_facts_used.length > 0 && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      flexWrap: 'wrap',
                      background: 'rgba(10, 14, 23, 0.5)',
                      padding: '0.35rem 0.6rem',
                      borderRadius: '6px',
                      fontSize: '0.68rem',
                    }}
                  >
                    <span style={{ color: 'var(--text-muted)' }}>Verified Facts Used:</span>
                    {draft.verified_facts_used.map((fact, idx) => (
                      <span key={idx} className="tag-verified" style={{ fontSize: '0.6rem' }}>
                        {fact}
                      </span>
                    ))}
                    <span style={{ color: 'var(--text-muted)', marginLeft: 'auto' }}>
                      {draft.grounding_notes}
                    </span>
                  </div>
                )}

                {/* Missing Email Warning Banner */}
                {!hasVerifiedEmail && (
                  <div
                    style={{
                      background: 'rgba(245, 158, 11, 0.08)',
                      border: '1px dashed rgba(245, 158, 11, 0.3)',
                      borderRadius: '6px',
                      padding: '0.5rem 0.75rem',
                      fontSize: '0.72rem',
                      color: '#fbbf24',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                    }}
                  >
                    <AlertTriangleIcon size={13} color="#fbbf24" />
                    <span>
                      <strong>Safety Lock Engaged:</strong> This lead has no verified public email address. Sending is permanently blocked on backend and UI to prevent unsolicited delivery or hallucinated addresses. You can copy the customized body above for manual contact via the target website&apos;s web form.
                    </span>
                  </div>
                )}

                {/* Editable Subject Field */}
                <div className="form-group">
                  <label className="form-label" style={{ fontSize: '0.72rem' }}>
                    <EditIcon size={11} color="var(--accent-cyan)" />
                    Subject Line (Editable):
                  </label>
                  <input
                    type="text"
                    className="form-input"
                    value={draft.subject}
                    onChange={(e) => handleUpdateDraft(draft.id, 'subject', e.target.value)}
                    disabled={isSent}
                    style={{ fontFamily: 'var(--font-sans)', fontSize: '0.8rem', fontWeight: 600 }}
                  />
                </div>

                {/* Editable Body Field */}
                <div className="form-group">
                  <label className="form-label" style={{ fontSize: '0.72rem' }}>
                    <EditIcon size={11} color="var(--accent-cyan)" />
                    Email Body (Editable & Personalized):
                  </label>
                  <textarea
                    className="form-input"
                    rows={7}
                    value={draft.body}
                    onChange={(e) => handleUpdateDraft(draft.id, 'body', e.target.value)}
                    disabled={isSent}
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.75rem',
                      lineHeight: 1.5,
                      resize: 'vertical',
                      whiteSpace: 'pre-wrap',
                    }}
                  />
                </div>

                {/* Operator Safety Controls & Send Action */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '0.75rem',
                    paddingTop: '0.5rem',
                    borderTop: '1px solid var(--border-subtle)',
                  }}
                >
                  {/* Operator Approval Toggle */}
                  <label
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem',
                      cursor: hasVerifiedEmail && !isSent ? 'pointer' : 'not-allowed',
                      opacity: hasVerifiedEmail ? 1 : 0.45,
                      fontSize: '0.78rem',
                      userSelect: 'none',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isApproved}
                      disabled={!hasVerifiedEmail || isSent}
                      onChange={() => handleToggleApproval(draft.id)}
                      style={{ cursor: hasVerifiedEmail && !isSent ? 'pointer' : 'not-allowed' }}
                    />
                    <span style={{ fontWeight: 600, color: isApproved ? '#34d399' : 'var(--text-secondary)' }}>
                      {isApproved ? 'Approved for Dispatch' : 'Approve Draft for Dispatch'}
                    </span>
                  </label>

                  {/* Send Email Action Button */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <button
                      type="button"
                      className={`btn ${isApproved && hasVerifiedEmail && !isSent ? 'btn-primary' : 'btn-secondary disabled'}`}
                      disabled={!isApproved || !hasVerifiedEmail || isSent}
                      onClick={() => handleInitiateSend(draft)}
                      style={{ fontSize: '0.75rem', padding: '0.4rem 0.85rem' }}
                    >
                      {isSent ? (
                        <>
                          <CheckCircleIcon size={13} color="var(--accent-cyan)" />
                          Sent to {draft.recipient_email}
                        </>
                      ) : (
                        <>
                          <SendIcon size={13} color="white" />
                          Send Outbound Email
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Explicit Send Confirmation Modal */}
      {confirmModalDraft && (
        <div
          className="modal-overlay"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(5, 8, 16, 0.85)',
            backdropFilter: 'blur(6px)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1.5rem',
          }}
        >
          <div
            className="modal-container"
            style={{
              background: 'var(--bg-secondary)',
              border: '1px solid rgba(56, 189, 248, 0.4)',
              borderRadius: '12px',
              maxWidth: '560px',
              width: '100%',
              padding: '1.5rem',
              boxShadow: '0 20px 40px rgba(0, 0, 0, 0.6)',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem',
            }}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 8,
                    background: 'rgba(6, 182, 212, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <ShieldAlertIcon size={18} color="var(--accent-cyan)" />
                </div>
                <div>
                  <h3 style={{ fontSize: '1rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                    {dispatchStatus?.is_live ? 'Confirm Live Email Transmission' : 'Confirm Simulated Email Dispatch'}
                  </h3>
                  <span style={{ fontSize: '0.72rem', color: dispatchStatus?.is_live ? '#34d399' : '#fbbf24' }}>
                    {dispatchStatus?.is_live
                      ? `Live Gateway: ${dispatchStatus.display_name}`
                      : 'Simulation Mode: No real email will be delivered'}
                  </span>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setConfirmModalDraft(null)}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
                disabled={isSending}
              >
                <XIcon size={18} />
              </button>
            </div>

            {/* Recipient Details */}
            <div
              style={{
                background: 'rgba(10, 14, 23, 0.6)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
                padding: '0.75rem',
                fontSize: '0.78rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.35rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Target Company:</span>
                <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{confirmModalDraft.company_name}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Verified Recipient Email:</span>
                <span style={{ color: '#38bdf8', fontFamily: 'var(--font-mono)' }}>{confirmModalDraft.recipient_email}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Subject Line:</span>
                <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{confirmModalDraft.subject}</span>
              </div>
            </div>

            {/* Snippet Preview */}
            <div className="code-box" style={{ maxHeight: '140px', overflowY: 'auto', fontSize: '0.72rem', lineHeight: 1.4 }}>
              {confirmModalDraft.body}
            </div>

            {/* Safety & Mode Warning */}
            <div
              style={{
                background: dispatchStatus?.is_live ? 'rgba(16, 185, 129, 0.08)' : 'rgba(245, 158, 11, 0.08)',
                border: `1px solid ${dispatchStatus?.is_live ? 'rgba(16, 185, 129, 0.25)' : 'rgba(245, 158, 11, 0.25)'}`,
                borderRadius: '6px',
                padding: '0.55rem 0.75rem',
                fontSize: '0.72rem',
                color: dispatchStatus?.is_live ? '#34d399' : '#fbbf24',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
              }}
            >
              <AlertTriangleIcon size={14} color={dispatchStatus?.is_live ? '#34d399' : '#fbbf24'} />
              <span>
                {dispatchStatus?.is_live
                  ? `LIVE OUTBOUND: Clicking confirm will transmit this email via ${dispatchStatus.display_name} to ${confirmModalDraft.recipient_email}.`
                  : 'SIMULATION MODE: No real email will be sent or delivered to any inbox. To enable live delivery, configure your SMTP settings in .env.'}
              </span>
            </div>

            {/* Modal Send Failure Diagnostic */}
            {sendErrorMessage && (
              <div
                style={{
                  background: 'rgba(239, 68, 68, 0.15)',
                  border: '1px solid rgba(239, 68, 68, 0.4)',
                  borderRadius: '6px',
                  padding: '0.6rem 0.8rem',
                  fontSize: '0.74rem',
                  color: '#fca5a5',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                <AlertTriangleIcon size={16} color="#f87171" />
                <span>{sendErrorMessage}</span>
              </div>
            )}

            {/* Modal Actions */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.65rem', marginTop: '0.5rem' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setConfirmModalDraft(null)}
                disabled={isSending}
              >
                Cancel / Keep in Review
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleConfirmSend}
                disabled={isSending || confirmModalDraft.status === 'sent'}
              >
                {isSending ? (
                  <>
                    <div className="spinner" />
                    Transmitting...
                  </>
                ) : (
                  <>
                    <SendIcon size={14} color="white" />
                    {dispatchStatus?.is_live ? 'Confirm & Transmit Real Email' : 'Confirm & Simulate Dispatch'}
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
