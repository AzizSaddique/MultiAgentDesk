import React from 'react';
import { AgentModel } from '../types/agent';
import { SearchIcon, LockIcon, PlusIcon, LayersIcon, HistoryIcon, CompassIcon } from './icons';
import { BackendStatus } from '../hooks/useBackendStatus';

interface SidebarProps {
  agents: AgentModel[];
  selectedAgentId: string;
  onSelectAgent: (id: string) => void;
  activeView: 'agent' | 'discovery' | 'environment' | 'history';
  onSelectView: (view: 'agent' | 'discovery' | 'environment' | 'history') => void;
  backendStatus?: BackendStatus;
}

export const Sidebar: React.FC<SidebarProps> = ({
  agents,
  selectedAgentId,
  onSelectAgent,
  activeView,
  onSelectView,
  backendStatus,
}) => {
  return (
    <aside className="sidebar">
      {/* Header / Brand */}
      <div className="sidebar-header">
        <div className="brand-badge">
          <div className="brand-icon">AD</div>
          <div className="brand-text">
            <h1>AgentDesk</h1>
            <span>Desktop Suite</span>
          </div>
        </div>
      </div>

      {/* Workflows & Primary Engines */}
      <div className="sidebar-section-title">
        <span>Autonomous Suite</span>
        <span className="badge badge-cyan">Engines</span>
      </div>

      <div style={{ padding: '0 0.75rem', display: 'flex', flexDirection: 'column', gap: '0.45rem', marginBottom: '0.75rem' }}>
        <button
          className={`agent-item ${activeView === 'discovery' ? 'selected' : ''}`}
          onClick={() => onSelectView('discovery')}
          style={{
            position: 'relative',
            background: activeView === 'discovery' ? 'rgba(6, 182, 212, 0.14)' : 'rgba(15, 23, 42, 0.6)',
            borderColor: activeView === 'discovery' ? 'var(--accent-cyan)' : 'var(--border-subtle)',
            boxShadow: activeView === 'discovery' ? '0 0 16px rgba(6, 182, 212, 0.18)' : 'none',
          }}
          title="Automated Lead Discovery (Autonomous Web & Directory Search)"
        >
          <div
            className="agent-item-icon"
            style={{
              background: activeView === 'discovery' ? 'linear-gradient(135deg, rgba(6,182,212,0.35), rgba(59,130,246,0.35))' : 'var(--bg-tertiary)',
              color: 'var(--accent-cyan)',
              border: activeView === 'discovery' ? '1px solid rgba(6,182,212,0.5)' : '1px solid transparent',
            }}
          >
            <CompassIcon size={17} color="var(--accent-cyan)" />
          </div>
          <div className="agent-item-content">
            <div className="agent-item-title-row">
              <span className="agent-item-name" style={{ fontWeight: 700 }}>Lead Discovery</span>
              <span className="badge badge-active" style={{ fontSize: '0.62rem' }}>
                <span className="badge-dot" />
                Live
              </span>
            </div>
            <p className="agent-item-desc">Autonomous Web & Registry Search</p>
          </div>
        </button>

        <button
          className={`agent-item ${activeView === 'history' ? 'selected' : ''}`}
          onClick={() => onSelectView('history')}
          style={{
            background: activeView === 'history' ? 'rgba(6, 182, 212, 0.14)' : 'transparent',
            borderColor: activeView === 'history' ? 'var(--accent-cyan)' : 'transparent',
          }}
          title="Outreach History & Dispatch Audit"
        >
          <div className="agent-item-icon">
            <HistoryIcon size={16} color={activeView === 'history' ? 'var(--accent-cyan)' : 'var(--text-muted)'} />
          </div>
          <div className="agent-item-content">
            <div className="agent-item-title-row">
              <span className="agent-item-name">Outreach History</span>
              <span className="badge" style={{ background: 'rgba(148, 163, 184, 0.1)', color: 'var(--text-muted)', fontSize: '0.62rem' }}>
                Audit
              </span>
            </div>
            <p className="agent-item-desc">Persistent Dispatch Records</p>
          </div>
        </button>
      </div>

      {/* Agents Section */}
      <div className="sidebar-section-title">
        <span>Agent Manager</span>
        <span className="badge badge-cyan">{agents.length} Registered</span>
      </div>

      <div className="agent-list">
        {agents.map((agent) => {
          const isSelected = activeView === 'agent' && selectedAgentId === agent.id;
          const isDisabled = agent.status === 'disabled' || agent.status === 'coming-soon';

          return (
            <button
              key={agent.id}
              className={`agent-item ${isSelected ? 'selected' : ''} ${isDisabled ? 'disabled' : ''}`}
              onClick={() => {
                if (!isDisabled) {
                  onSelectAgent(agent.id);
                  onSelectView('agent');
                }
              }}
              disabled={isDisabled}
              title={isDisabled ? `${agent.name} (Coming Soon)` : agent.name}
            >
              <div className="agent-item-icon">
                {isDisabled ? (
                  <LockIcon size={16} color="var(--text-muted)" />
                ) : (
                  <SearchIcon size={16} color="var(--accent-cyan)" />
                )}
              </div>
              <div className="agent-item-content">
                <div className="agent-item-title-row">
                  <span className="agent-item-name">{agent.name}</span>
                  <span
                    className={`badge ${
                      agent.status === 'active'
                        ? 'badge-active'
                        : 'badge-disabled'
                    }`}
                  >
                    {agent.status === 'active' ? (
                      <>
                        <span className="badge-dot" />
                        Active
                      </>
                    ) : (
                      'Soon'
                    )}
                  </span>
                </div>
                <p className="agent-item-desc">{agent.description}</p>
              </div>
            </button>
          );
        })}

        {/* Disabled Add Agent placeholder */}
        <button className="agent-item disabled" style={{ borderStyle: 'dashed', borderColor: 'var(--border-subtle)' }} disabled>
          <div className="agent-item-icon">
            <PlusIcon size={16} color="var(--text-muted)" />
          </div>
          <div className="agent-item-content">
            <span className="agent-item-name" style={{ color: 'var(--text-muted)' }}>+ Add Custom Agent</span>
            <p className="agent-item-desc">Multi-agent architecture staged</p>
          </div>
        </button>
      </div>

      {/* Sidebar Footer */}
      <div className="sidebar-footer">
        <button
          className={`btn btn-secondary ${activeView === 'environment' ? 'selected' : ''}`}
          style={{
            width: '100%',
            justifyContent: 'flex-start',
            padding: '0.65rem 0.85rem',
            background: activeView === 'environment' ? 'rgba(6, 182, 212, 0.15)' : undefined,
            borderColor: activeView === 'environment' ? 'var(--accent-cyan)' : undefined,
          }}
          onClick={() => onSelectView('environment')}
        >
          <LayersIcon size={16} color="var(--accent-cyan)" />
          <span>System Environment Status</span>
        </button>
        <div style={{ marginTop: '0.65rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>Tauri v2.2 Shell</span>
          <span className="badge badge-active" style={{ fontSize: '0.6rem' }}>Online</span>
        </div>
        <div style={{ marginTop: '0.35rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>FastAPI Microservice</span>
          <span className={`badge ${backendStatus?.isOnline ? 'badge-active' : 'badge-offline'}`} style={{ fontSize: '0.6rem' }}>
            <span className="badge-dot" />
            {backendStatus?.isOnline ? 'Online' : 'Offline'}
          </span>
        </div>
      </div>
    </aside>

  );
};
