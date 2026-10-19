import React from 'react';
import { AgentModel } from '../types/agent';
import { TerminalIcon, ShieldAlertIcon } from './icons';
import { BackendStatus } from '../hooks/useBackendStatus';

interface HeaderProps {
  activeView: 'agent' | 'environment';
  currentAgent?: AgentModel;
  backendStatus?: BackendStatus;
}

export const Header: React.FC<HeaderProps> = ({ activeView, currentAgent, backendStatus }) => {
  const isOnline = backendStatus?.isOnline ?? false;

  return (
    <header className="top-header">
      <div className="header-title-section">
        <div>
          <h2 className="header-title">
            {activeView === 'agent' ? currentAgent?.name : 'Prerequisite & Environment Verification'}
          </h2>
        </div>
        {activeView === 'agent' && (
          <span className="badge badge-active">
            <span className="badge-dot" />
            Ready for Backend Orchestrator
          </span>
        )}
      </div>

      <div className="header-actions">
        {/* Backend Connection Status */}
        <div
          title={isOnline ? `FastAPI Backend Online (${backendStatus?.data?.service || 'AgentDesk API'} at 127.0.0.1:8000)` : 'FastAPI Backend is currently not reachable at 127.0.0.1:8000'}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.45rem',
            background: 'var(--bg-tertiary)',
            padding: '0.35rem 0.65rem',
            borderRadius: '6px',
            fontSize: '0.72rem',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <span className={`badge ${isOnline ? 'badge-active' : 'badge-offline'}`}>
            <span className="badge-dot" />
            {isOnline ? 'Backend Online' : 'Backend Offline'}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--bg-tertiary)', padding: '0.35rem 0.65rem', borderRadius: '6px', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
          <TerminalIcon size={14} color="var(--accent-cyan)" />
          <span>Workspace:</span>
          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>AgentDesk</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.25)', padding: '0.35rem 0.65rem', borderRadius: '6px', fontSize: '0.72rem', color: '#fbbf24' }}>
          <ShieldAlertIcon size={14} color="#fbbf24" />
          <span>Explicit Human Approval: <strong>Enforced</strong></span>
        </div>
      </div>
    </header>
  );
};
