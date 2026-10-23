import React from 'react';
import { AgentModel } from '../types/agent';
import { SearchIcon, LockIcon, PlusIcon, LayersIcon, HistoryIcon } from './icons';
import { BackendStatus } from '../hooks/useBackendStatus';

interface SidebarProps {
  agents: AgentModel[];
  selectedAgentId: string;
  onSelectAgent: (id: string) => void;
  activeView: 'agent' | 'environment' | 'history';
  onSelectView: (view: 'agent' | 'environment' | 'history') => void;
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
          className={`btn btn-secondary ${activeView === 'history' ? 'selected' : ''}`}
          style={{
            width: '100%',
            justifyContent: 'flex-start',
            padding: '0.65rem 0.85rem',
            marginBottom: '0.5rem',
            background: activeView === 'history' ? 'rgba(6, 182, 212, 0.15)' : undefined,
            borderColor: activeView === 'history' ? 'var(--accent-cyan)' : undefined,
          }}
          onClick={() => onSelectView('history')}
        >
          <HistoryIcon size={16} color="var(--accent-cyan)" />
          <span>Outreach History & Audit</span>
        </button>
        <button
          className={`btn btn-secondary ${activeView === 'environment' ? 'selected' : ''}`}
          style={{ width: '100%', justifyContent: 'flex-start', padding: '0.65rem 0.85rem' }}
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
