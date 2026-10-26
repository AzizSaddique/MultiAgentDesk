import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  OutreachHistoryItem,
  OutreachHistoryResponse,
  HistoryFilterParams,
} from '../types/agent';
import { fetchOutreachHistory, downloadHistoryCsv } from '../services/api';
import { BackendStatus } from '../hooks/useBackendStatus';
import {
  HistoryIcon,
  SearchIcon,
  FilterIcon,
  DownloadIcon,
  RefreshCwIcon,
  AlertTriangleIcon,
  EyeIcon,
  XIcon,
  CalendarIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  MailIcon,
} from './icons';

interface OutreachHistoryProps {
  backendStatus?: BackendStatus;
  onNavigateToConsole?: () => void;
}

export const OutreachHistory: React.FC<OutreachHistoryProps> = ({
  backendStatus,
  onNavigateToConsole,
}) => {
  // Query & Filter State
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [debouncedQuery, setDebouncedQuery] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(15);

  // Data State
  const [data, setData] = useState<OutreachHistoryResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Selected Item for Detail Modal
  const [selectedItem, setSelectedItem] = useState<OutreachHistoryItem | null>(null);

  // Debounce search query changes
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedQuery(searchQuery.trim());
      setPage(1); // Reset to first page on search change
    }, 350);
    return () => clearTimeout(handler);
  }, [searchQuery]);

  // Reset page when filters change
  const handleStatusChange = (newStatus: string) => {
    setStatusFilter(newStatus);
    setPage(1);
  };

  const handleStartDateChange = (val: string) => {
    setStartDate(val);
    setPage(1);
  };

  const handleEndDateChange = (val: string) => {
    setEndDate(val);
    setPage(1);
  };

  const clearAllFilters = () => {
    setStatusFilter('');
    setSearchQuery('');
    setDebouncedQuery('');
    setStartDate('');
    setEndDate('');
    setPage(1);
  };

  // Quick Date Range Presets
  const applyDatePreset = (preset: 'today' | '7days' | '30days' | 'all') => {
    if (preset === 'all') {
      setStartDate('');
      setEndDate('');
      setPage(1);
      return;
    }

    const now = new Date();
    const todayStr = now.toISOString().split('T')[0];

    if (preset === 'today') {
      setStartDate(todayStr);
      setEndDate(todayStr);
    } else if (preset === '7days') {
      const past = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      setStartDate(past.toISOString().split('T')[0]);
      setEndDate(todayStr);
    } else if (preset === '30days') {
      const past = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      setStartDate(past.toISOString().split('T')[0]);
      setEndDate(todayStr);
    }
    setPage(1);
  };

  // Fetch History from Backend
  const loadHistory = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);

    const params: HistoryFilterParams = {
      page,
      page_size: pageSize,
    };
    if (statusFilter) params.status = statusFilter;
    if (debouncedQuery) params.query = debouncedQuery;
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;

    try {
      const res = await fetchOutreachHistory(params);
      setData(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load outreach history.';
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, statusFilter, debouncedQuery, startDate, endDate]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // CSV Export handler
  const handleExportCsv = async () => {
    setIsExporting(true);
    try {
      const params: HistoryFilterParams = {};
      if (statusFilter) params.status = statusFilter;
      if (debouncedQuery) params.query = debouncedQuery;
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;

      await downloadHistoryCsv(params);
    } catch (err: unknown) {
      alert(`Export error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsExporting(false);
    }
  };

  // Format timestamp helper
  const formatDateTime = (isoString: string) => {
    try {
      const date = new Date(isoString);
      if (isNaN(date.getTime())) return isoString;
      return new Intl.DateTimeFormat(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        second: '2-digit',
      }).format(date);
    } catch {
      return isoString;
    }
  };

  const getStatusBadge = (item: OutreachHistoryItem) => {
    const s = item.status.toLowerCase();
    if (s === 'sent') {
      return (
        <span
          className="badge badge-active"
          style={{
            background: 'rgba(16, 185, 129, 0.15)',
            color: '#34d399',
            border: '1px solid rgba(16, 185, 129, 0.4)',
            fontWeight: 700,
          }}
          title="Delivered via live email provider"
        >
          <span className="badge-dot" />
          SENT (LIVE)
        </span>
      );
    }
    if (s === 'simulated' || item.is_simulated) {
      return (
        <span
          className="badge badge-warning"
          style={{
            background: 'rgba(245, 158, 11, 0.15)',
            color: '#fbbf24',
            border: '1px solid rgba(245, 158, 11, 0.4)',
            fontWeight: 700,
          }}
          title="Simulated dispatch - Offline test run. No real email was transmitted."
        >
          <span className="badge-dot" style={{ background: '#fbbf24' }} />
          SIMULATED
        </span>
      );
    }
    if (s === 'failed') {
      return (
        <span
          className="badge badge-offline"
          style={{
            background: 'rgba(239, 68, 68, 0.15)',
            color: '#f87171',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            fontWeight: 700,
          }}
          title={item.error_message || 'Dispatch attempt failed'}
        >
          <span className="badge-dot" style={{ background: '#f87171' }} />
          FAILED
        </span>
      );
    }
    if (s === 'drafted') {
      return (
        <span
          className="badge badge-cyan"
          style={{
            background: 'rgba(6, 182, 212, 0.15)',
            color: '#38bdf8',
            border: '1px solid rgba(6, 182, 212, 0.4)',
          }}
          title="Draft generated, pending human review and approval"
        >
          DRAFTED
        </span>
      );
    }
    return (
      <span className="badge badge-disabled">
        {item.status.toUpperCase()}
      </span>
    );
  };

  const getProviderBadge = (providerMode?: string | null) => {
    if (!providerMode) return <span style={{ color: 'var(--text-muted)' }}>—</span>;
    const p = providerMode.toLowerCase();
    let label = providerMode.toUpperCase();
    let bg = 'rgba(100, 116, 139, 0.2)';
    let color = 'var(--text-secondary)';

    if (p.includes('smtp')) {
      bg = 'rgba(99, 102, 241, 0.15)';
      color = '#a5b4fc';
      label = 'SMTP';
    } else if (p.includes('resend')) {
      bg = 'rgba(168, 85, 247, 0.15)';
      color = '#c084fc';
      label = 'RESEND';
    } else if (p.includes('simulation') || p.includes('mock')) {
      bg = 'rgba(245, 158, 11, 0.1)';
      color = '#fbbf24';
      label = 'SIMULATION';
    }

    return (
      <span
        style={{
          fontSize: '0.68rem',
          padding: '0.15rem 0.45rem',
          borderRadius: '4px',
          background: bg,
          color,
          fontFamily: 'var(--font-mono)',
          fontWeight: 600,
        }}
      >
        {label}
      </span>
    );
  };

  const hasActiveFilters = Boolean(statusFilter || searchQuery || startDate || endDate);

  const statusCounts = useMemo(() => {
    return (
      data?.status_counts || {
        sent: 0,
        simulated: 0,
        failed: 0,
        drafted: 0,
      }
    );
  }, [data]);

  const totalEntries = data?.total ?? 0;
  const totalPages = data?.total_pages ?? 1;

  return (
    <div className="agent-detail" style={{ flex: 1, overflowY: 'auto', padding: '1.5rem' }}>
      {/* Top Banner / Metrics Card */}
      <div
        className="card"
        style={{
          marginBottom: '1.25rem',
          border: '1px solid rgba(6, 182, 212, 0.25)',
          background: 'radial-gradient(ellipse at top left, rgba(6, 182, 212, 0.08), transparent 60%), var(--bg-card)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div
              style={{
                width: 38,
                height: 38,
                borderRadius: 10,
                background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-indigo))',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 4px 12px rgba(6, 182, 212, 0.25)',
              }}
            >
              <HistoryIcon size={20} color="#ffffff" />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <h2 style={{ fontSize: '1.2rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                  Persistent Outreach History & Audit
                </h2>
                <span className="badge badge-active" style={{ fontSize: '0.65rem' }}>
                  SQLite Persistent
                </span>
              </div>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                Complete audit trail of all outreach drafts and dispatch attempts. Persisted across backend restarts in <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)' }}>storage/dispatches.db</code>.
              </p>
            </div>
          </div>

          {/* Quick Actions */}
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={loadHistory}
              disabled={isLoading}
              title="Refresh history table"
              style={{ fontSize: '0.75rem', padding: '0.45rem 0.75rem' }}
            >
              <RefreshCwIcon size={14} color="var(--accent-cyan)" className={isLoading ? 'spin-icon' : ''} />
              <span>Refresh</span>
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleExportCsv}
              disabled={isExporting || totalEntries === 0}
              title="Export current filtered history to CSV"
              style={{ fontSize: '0.75rem', padding: '0.45rem 0.75rem' }}
            >
              <DownloadIcon size={14} color="var(--accent-cyan)" />
              <span>{isExporting ? 'Exporting...' : 'Export CSV'}</span>
            </button>
            {onNavigateToConsole && (
              <button
                type="button"
                className="btn btn-primary"
                onClick={onNavigateToConsole}
                style={{ fontSize: '0.75rem', padding: '0.45rem 0.85rem' }}
              >
                <MailIcon size={14} color="#ffffff" />
                <span>Go to Outreach Console</span>
              </button>
            )}
          </div>
        </div>

        {/* Metric Summary Counters */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
            gap: '0.75rem',
            marginTop: '1.25rem',
            paddingTop: '1.25rem',
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
          <div
            onClick={() => handleStatusChange('')}
            style={{
              background: !statusFilter ? 'rgba(6, 182, 212, 0.12)' : 'var(--bg-tertiary)',
              border: `1px solid ${!statusFilter ? 'var(--accent-cyan)' : 'var(--border-subtle)'}`,
              borderRadius: '8px',
              padding: '0.65rem 0.85rem',
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
              Total Events
            </div>
            <div style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: '0.15rem' }}>
              {totalEntries}
            </div>
          </div>

          <div
            onClick={() => handleStatusChange('sent')}
            style={{
              background: statusFilter === 'sent' ? 'rgba(16, 185, 129, 0.18)' : 'var(--bg-tertiary)',
              border: `1px solid ${statusFilter === 'sent' ? '#10b981' : 'var(--border-subtle)'}`,
              borderRadius: '8px',
              padding: '0.65rem 0.85rem',
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            <div style={{ fontSize: '0.7rem', color: '#34d399', textTransform: 'uppercase', fontWeight: 600 }}>
              Live Sent
            </div>
            <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#34d399', marginTop: '0.15rem' }}>
              {statusCounts.sent ?? 0}
            </div>
          </div>

          <div
            onClick={() => handleStatusChange('simulated')}
            style={{
              background: statusFilter === 'simulated' ? 'rgba(245, 158, 11, 0.18)' : 'var(--bg-tertiary)',
              border: `1px solid ${statusFilter === 'simulated' ? '#f59e0b' : 'var(--border-subtle)'}`,
              borderRadius: '8px',
              padding: '0.65rem 0.85rem',
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            <div style={{ fontSize: '0.7rem', color: '#fbbf24', textTransform: 'uppercase', fontWeight: 600 }}>
              Simulated
            </div>
            <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#fbbf24', marginTop: '0.15rem' }}>
              {statusCounts.simulated ?? 0}
            </div>
          </div>

          <div
            onClick={() => handleStatusChange('failed')}
            style={{
              background: statusFilter === 'failed' ? 'rgba(239, 68, 68, 0.18)' : 'var(--bg-tertiary)',
              border: `1px solid ${statusFilter === 'failed' ? '#ef4444' : 'var(--border-subtle)'}`,
              borderRadius: '8px',
              padding: '0.65rem 0.85rem',
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            <div style={{ fontSize: '0.7rem', color: '#f87171', textTransform: 'uppercase', fontWeight: 600 }}>
              Failed
            </div>
            <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#f87171', marginTop: '0.15rem' }}>
              {statusCounts.failed ?? 0}
            </div>
          </div>

          <div
            onClick={() => handleStatusChange('drafted')}
            style={{
              background: statusFilter === 'drafted' ? 'rgba(6, 182, 212, 0.18)' : 'var(--bg-tertiary)',
              border: `1px solid ${statusFilter === 'drafted' ? 'var(--accent-cyan)' : 'var(--border-subtle)'}`,
              borderRadius: '8px',
              padding: '0.65rem 0.85rem',
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            <div style={{ fontSize: '0.7rem', color: 'var(--accent-cyan)', textTransform: 'uppercase', fontWeight: 600 }}>
              Drafted
            </div>
            <div style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--accent-cyan)', marginTop: '0.15rem' }}>
              {statusCounts.drafted ?? 0}
            </div>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div
        className="card"
        style={{
          marginBottom: '1.25rem',
          padding: '1rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.75rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
          {/* Search Input */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: '1 1 260px' }}>
            <div
              style={{
                position: 'relative',
                width: '100%',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <div style={{ position: 'absolute', left: 10, pointerEvents: 'none', color: 'var(--text-muted)' }}>
                <SearchIcon size={14} />
              </div>
              <input
                type="text"
                className="input-field"
                placeholder="Search recipient, company, subject, URL, or error..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  paddingLeft: '2rem',
                  fontSize: '0.8rem',
                  height: '34px',
                  background: 'var(--bg-secondary)',
                  width: '100%',
                }}
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  style={{
                    position: 'absolute',
                    right: 8,
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                  }}
                  title="Clear search"
                >
                  <XIcon size={14} />
                </button>
              )}
            </div>
          </div>

          {/* Status Filter Dropdown */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
            <FilterIcon size={14} color="var(--accent-cyan)" />
            <select
              value={statusFilter}
              onChange={(e) => handleStatusChange(e.target.value)}
              className="input-field"
              style={{
                height: '34px',
                fontSize: '0.8rem',
                padding: '0 0.5rem',
                background: 'var(--bg-secondary)',
                minWidth: '130px',
              }}
            >
              <option value="">All Statuses</option>
              <option value="sent">Live Sent</option>
              <option value="simulated">Simulated</option>
              <option value="failed">Failed</option>
              <option value="drafted">Drafted</option>
            </select>
          </div>

          {/* Date Range Inputs */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', flexWrap: 'wrap' }}>
            <CalendarIcon size={14} color="var(--accent-cyan)" />
            <input
              type="date"
              className="input-field"
              value={startDate}
              onChange={(e) => handleStartDateChange(e.target.value)}
              style={{
                height: '34px',
                fontSize: '0.75rem',
                padding: '0 0.4rem',
                background: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
              }}
              title="Filter from start date"
            />
            <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>to</span>
            <input
              type="date"
              className="input-field"
              value={endDate}
              onChange={(e) => handleEndDateChange(e.target.value)}
              style={{
                height: '34px',
                fontSize: '0.75rem',
                padding: '0 0.4rem',
                background: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
              }}
              title="Filter to end date"
            />
          </div>

          {/* Quick Date Presets */}
          <div style={{ display: 'flex', gap: '0.3rem', alignItems: 'center' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => applyDatePreset('today')}
              style={{ fontSize: '0.7rem', padding: '0.25rem 0.5rem', height: '32px' }}
            >
              Today
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => applyDatePreset('7days')}
              style={{ fontSize: '0.7rem', padding: '0.25rem 0.5rem', height: '32px' }}
            >
              7D
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => applyDatePreset('30days')}
              style={{ fontSize: '0.7rem', padding: '0.25rem 0.5rem', height: '32px' }}
            >
              30D
            </button>
          </div>

          {/* Reset Filters */}
          {hasActiveFilters && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={clearAllFilters}
              style={{
                fontSize: '0.72rem',
                padding: '0.25rem 0.6rem',
                height: '32px',
                color: '#f87171',
                borderColor: 'rgba(239, 68, 68, 0.3)',
              }}
              title="Reset all search queries and filters"
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* Backend Offline Banner */}
      {backendStatus && !backendStatus.isOnline && (
        <div
          style={{
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.35)',
            borderRadius: '8px',
            padding: '0.75rem 1rem',
            marginBottom: '1rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#f87171', fontSize: '0.8rem' }}>
            <AlertTriangleIcon size={16} color="#f87171" />
            <span>FastAPI backend is offline (127.0.0.1:8000). Start the backend via <code>start-backend.ps1</code> or <code>npm run backend</code> to view and export records.</span>
          </div>
        </div>
      )}

      {/* Error Banner */}
      {errorMessage && (
        <div
          style={{
            background: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.35)',
            borderRadius: '8px',
            padding: '0.75rem 1rem',
            marginBottom: '1rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#f87171', fontSize: '0.8rem' }}>
            <AlertTriangleIcon size={16} color="#f87171" />
            <span>{errorMessage}</span>
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={loadHistory}
            style={{ fontSize: '0.72rem', padding: '0.25rem 0.5rem' }}
          >
            Retry
          </button>
        </div>
      )}

      {/* History Table Container */}
      <div
        className="card"
        style={{
          padding: 0,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div style={{ overflowX: 'auto', width: '100%' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.8rem' }}>
            <thead>
              <tr
                style={{
                  background: 'rgba(15, 23, 42, 0.85)',
                  borderBottom: '1px solid var(--border-subtle)',
                  color: 'var(--text-muted)',
                  fontSize: '0.7rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}
              >
                <th style={{ padding: '0.75rem 1rem' }}>Timestamp</th>
                <th style={{ padding: '0.75rem 1rem' }}>Status</th>
                <th style={{ padding: '0.75rem 1rem' }}>Provider</th>
                <th style={{ padding: '0.75rem 1rem' }}>Recipient & Lead</th>
                <th style={{ padding: '0.75rem 1rem' }}>Subject & Snippet</th>
                <th style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={6} style={{ padding: '2.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
                      <RefreshCwIcon size={22} color="var(--accent-cyan)" className="spin-icon" />
                      <span>Loading persistent outreach records...</span>
                    </div>
                  </td>
                </tr>
              )}

              {!isLoading && (!data?.items || data.items.length === 0) && (
                <tr>
                  <td colSpan={6} style={{ padding: '3.5rem 1.5rem', textAlign: 'center' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem', maxWidth: '420px', margin: '0 auto' }}>
                      <div
                        style={{
                          width: 48,
                          height: 48,
                          borderRadius: '50%',
                          background: 'rgba(100, 116, 139, 0.15)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: 'var(--text-muted)',
                        }}
                      >
                        <HistoryIcon size={24} />
                      </div>
                      <h4 style={{ margin: 0, fontSize: '0.95rem', color: 'var(--text-primary)' }}>
                        {hasActiveFilters ? 'No Matching Outreach Records' : 'No Outreach History Yet'}
                      </h4>
                      <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                        {hasActiveFilters
                          ? 'Try broadening your search query, status selection, or date range filters.'
                          : 'Previous email drafts and dispatch attempts will automatically appear here once generated in the Outreach Console.'}
                      </p>
                      {hasActiveFilters ? (
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={clearAllFilters}
                          style={{ fontSize: '0.75rem', marginTop: '0.5rem' }}
                        >
                          Clear Filters
                        </button>
                      ) : onNavigateToConsole ? (
                        <button
                          type="button"
                          className="btn btn-primary"
                          onClick={onNavigateToConsole}
                          style={{ fontSize: '0.75rem', marginTop: '0.5rem' }}
                        >
                          Open Outreach Console
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              )}

              {!isLoading &&
                data?.items?.map((item) => {
                  return (
                    <tr
                      key={item.id}
                      style={{
                        borderBottom: '1px solid var(--border-subtle)',
                        transition: 'background 0.15s',
                        cursor: 'pointer',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = 'rgba(30, 41, 59, 0.6)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'transparent';
                      }}
                      onClick={() => setSelectedItem(item)}
                    >
                      {/* Timestamp */}
                      <td style={{ padding: '0.75rem 1rem', whiteSpace: 'nowrap' }}>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-primary)', fontWeight: 600 }}>
                          {formatDateTime(item.dispatched_at)}
                        </div>
                        <div
                          style={{
                            fontSize: '0.65rem',
                            color: 'var(--text-muted)',
                            fontFamily: 'var(--font-mono)',
                          }}
                          title="Original UTC timestamp"
                        >
                          {item.dispatched_at}
                        </div>
                      </td>

                      {/* Status */}
                      <td style={{ padding: '0.75rem 1rem', whiteSpace: 'nowrap' }}>
                        {getStatusBadge(item)}
                      </td>

                      {/* Provider */}
                      <td style={{ padding: '0.75rem 1rem', whiteSpace: 'nowrap' }}>
                        {getProviderBadge(item.provider_mode)}
                      </td>

                      {/* Recipient & Lead */}
                      <td style={{ padding: '0.75rem 1rem', maxWidth: '240px' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
                          <span
                            style={{
                              fontFamily: 'var(--font-mono)',
                              fontSize: '0.76rem',
                              color: 'var(--accent-cyan)',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                            title={item.recipient_email}
                          >
                            {item.recipient_email}
                          </span>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
                            {item.recipient_name && (
                              <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                                {item.recipient_name}
                              </span>
                            )}
                            {item.company_name && (
                              <span
                                style={{
                                  fontSize: '0.68rem',
                                  color: 'var(--text-muted)',
                                  background: 'rgba(100, 116, 139, 0.15)',
                                  padding: '0.1rem 0.35rem',
                                  borderRadius: '3px',
                                  maxWidth: '120px',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap',
                                }}
                                title={item.company_name}
                              >
                                {item.company_name}
                              </span>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Subject & Snippet */}
                      <td style={{ padding: '0.75rem 1rem', maxWidth: '300px' }}>
                        <div
                          style={{
                            fontWeight: 600,
                            color: 'var(--text-primary)',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            fontSize: '0.78rem',
                          }}
                          title={item.subject}
                        >
                          {item.subject || '(No Subject)'}
                        </div>
                        {item.body_snippet && (
                          <div
                            style={{
                              fontSize: '0.7rem',
                              color: 'var(--text-muted)',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                              marginTop: '0.1rem',
                            }}
                            title={item.body_snippet}
                          >
                            {item.body_snippet}
                          </div>
                        )}
                        {item.error_message && (
                          <div
                            style={{
                              fontSize: '0.68rem',
                              color: '#f87171',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                              marginTop: '0.15rem',
                            }}
                            title={item.error_message}
                          >
                            Error: {item.error_message}
                          </div>
                        )}
                      </td>

                      {/* Actions */}
                      <td style={{ padding: '0.75rem 1rem', textAlign: 'right', whiteSpace: 'nowrap' }}>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedItem(item);
                          }}
                          style={{ fontSize: '0.7rem', padding: '0.25rem 0.5rem' }}
                          title="View detailed record"
                        >
                          <EyeIcon size={12} color="var(--accent-cyan)" />
                          <span>Details</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        {totalEntries > 0 && (
          <div
            style={{
              padding: '0.75rem 1rem',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              borderTop: '1px solid var(--border-subtle)',
              background: 'rgba(15, 23, 42, 0.7)',
              flexWrap: 'wrap',
              gap: '0.75rem',
              fontSize: '0.75rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'var(--text-muted)' }}>
              <span>
                Showing {Math.min((page - 1) * pageSize + 1, totalEntries)} to{' '}
                {Math.min(page * pageSize, totalEntries)} of {totalEntries} entries
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <span>Per page:</span>
                <select
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setPage(1);
                  }}
                  className="input-field"
                  style={{
                    height: '26px',
                    fontSize: '0.72rem',
                    padding: '0 0.35rem',
                    background: 'var(--bg-secondary)',
                  }}
                >
                  <option value={10}>10</option>
                  <option value={15}>15</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={page <= 1 || isLoading}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                style={{ padding: '0.3rem 0.6rem', fontSize: '0.72rem' }}
              >
                <ChevronLeftIcon size={12} />
                <span>Previous</span>
              </button>

              <span style={{ color: 'var(--text-secondary)', padding: '0 0.4rem', fontFamily: 'var(--font-mono)' }}>
                Page {page} of {totalPages}
              </span>

              <button
                type="button"
                className="btn btn-secondary"
                disabled={page >= totalPages || isLoading}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                style={{ padding: '0.3rem 0.6rem', fontSize: '0.72rem' }}
              >
                <span>Next</span>
                <ChevronRightIcon size={12} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Record Detail Modal */}
      {selectedItem && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.75)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1.5rem',
            backdropFilter: 'blur(3px)',
          }}
          onClick={() => setSelectedItem(null)}
        >
          <div
            className="card"
            style={{
              width: '100%',
              maxWidth: '650px',
              maxHeight: '85vh',
              overflowY: 'auto',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-active)',
              boxShadow: '0 20px 40px rgba(0, 0, 0, 0.5)',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.75rem' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <h3 style={{ fontSize: '1.05rem', margin: 0, color: 'var(--text-primary)' }}>
                    Outreach Dispatch Record
                  </h3>
                  {getStatusBadge(selectedItem)}
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '0.2rem' }}>
                  Record ID: {selectedItem.id} {selectedItem.draft_id ? `| Draft ID: ${selectedItem.draft_id}` : ''}
                </div>
              </div>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setSelectedItem(null)}
                style={{ padding: '0.3rem', borderRadius: '50%' }}
              >
                <XIcon size={16} />
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', fontSize: '0.8rem' }}>
              {/* Recipient Card */}
              <div
                style={{
                  background: 'var(--bg-tertiary)',
                  padding: '0.75rem 1rem',
                  borderRadius: '6px',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                  <div>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Recipient Email:</span>
                    <div style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)', fontWeight: 600 }}>
                      {selectedItem.recipient_email}
                    </div>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Recipient Contact:</span>
                    <div style={{ color: 'var(--text-primary)' }}>
                      {selectedItem.recipient_name || 'N/A'}
                    </div>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Target Company:</span>
                    <div style={{ color: 'var(--text-primary)' }}>
                      {selectedItem.company_name || 'N/A'}
                    </div>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Provider Mode:</span>
                    <div style={{ marginTop: '0.15rem' }}>
                      {getProviderBadge(selectedItem.provider_mode)}
                    </div>
                  </div>
                </div>

                {selectedItem.source_url && (
                  <div style={{ marginTop: '0.5rem', paddingTop: '0.5rem', borderTop: '1px solid var(--border-subtle)' }}>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Research Source URL: </span>
                    <a
                      href={selectedItem.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: 'var(--accent-cyan)', textDecoration: 'underline', wordBreak: 'break-all' }}
                    >
                      {selectedItem.source_url}
                    </a>
                  </div>
                )}
              </div>

              {/* Subject */}
              <div>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
                  Email Subject
                </span>
                <div
                  style={{
                    background: 'var(--bg-tertiary)',
                    padding: '0.65rem 0.85rem',
                    borderRadius: '6px',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-primary)',
                    fontWeight: 600,
                    marginTop: '0.25rem',
                  }}
                >
                  {selectedItem.subject}
                </div>
              </div>

              {/* Body Snippet */}
              <div>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>
                  Email Body Content
                </span>
                <div
                  style={{
                    background: 'var(--bg-tertiary)',
                    padding: '0.85rem',
                    borderRadius: '6px',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-secondary)',
                    whiteSpace: 'pre-wrap',
                    fontFamily: 'var(--font-sans)',
                    lineHeight: 1.6,
                    maxHeight: '220px',
                    overflowY: 'auto',
                    marginTop: '0.25rem',
                  }}
                >
                  {selectedItem.body_snippet || '(No body snippet stored)'}
                </div>
              </div>

              {/* Error Message if Failed */}
              {selectedItem.error_message && (
                <div
                  style={{
                    background: 'rgba(239, 68, 68, 0.1)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    padding: '0.75rem',
                    borderRadius: '6px',
                    color: '#f87171',
                  }}
                >
                  <span style={{ fontWeight: 700, fontSize: '0.72rem', textTransform: 'uppercase' }}>
                    Failure Diagnostics (Sanitized):
                  </span>
                  <div style={{ marginTop: '0.25rem', fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                    {selectedItem.error_message}
                  </div>
                </div>
              )}

              {/* Timestamps */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  background: 'rgba(15, 23, 42, 0.5)',
                  padding: '0.5rem 0.75rem',
                  borderRadius: '6px',
                  fontSize: '0.7rem',
                  color: 'var(--text-muted)',
                }}
              >
                <span>Local Time: {formatDateTime(selectedItem.dispatched_at)}</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>UTC: {selectedItem.dispatched_at}</span>
              </div>
            </div>

            {/* Modal Footer */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.75rem' }}>
              <div>
                {(selectedItem.status === 'drafted' || selectedItem.status === 'approved') && onNavigateToConsole && (
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => {
                      setSelectedItem(null);
                      onNavigateToConsole();
                    }}
                    style={{ fontSize: '0.74rem', padding: '0.35rem 0.75rem' }}
                  >
                    Open in Outreach Console &rarr;
                  </button>
                )}
              </div>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setSelectedItem(null)}
              >
                Close Record
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
