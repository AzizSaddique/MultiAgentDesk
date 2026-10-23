import { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { AgentDetail } from './components/AgentDetail';
import { EnvironmentStatus } from './components/EnvironmentStatus';
import { OutreachHistory } from './components/OutreachHistory';
import { AgentModel } from './types/agent';
import { useBackendStatus } from './hooks/useBackendStatus';

const INITIAL_AGENTS: AgentModel[] = [
  {
    id: 'agent-1',
    name: 'Agent 1: Lead Researcher',
    badge: 'Active',
    category: 'Lead Generation & Outreach',
    description: 'Automates compliant public business research, extracts publicly listed emails, drafts personalized emails, and enforces an explicit human approval gate before dispatch.',
    status: 'active',
    version: '0.1.0',
    capabilities: [
      'Permitted public business research via browser automation',
      'Extraction of public company profiles and business emails',
      'Structured CSV and Excel lead record export',
      'Service-tailored personalized email drafting',
      'Human-in-the-loop review, edit, approve, and reject console',
      'Zero-dispatch safety gate requiring explicit approval',
      'Comprehensive task audit, error tracing, and activity logging'
    ],
    stages: [
      {
        id: 1,
        title: 'Browser Intelligence Gathering',
        description: 'Research permitted public business information via Playwright browser automation without interacting with restricted portals.',
        status: 'ready'
      },
      {
        id: 2,
        title: 'Company & Contact Extraction',
        description: 'Parse and save company identity, website, executive names, and publicly listed business email addresses.',
        status: 'ready'
      },
      {
        id: 3,
        title: 'Structured Dataset Export',
        description: 'Export structured lead datasets into clean CSV and Microsoft Excel (.xlsx) formats with column validation.',
        status: 'ready'
      },
      {
        id: 4,
        title: 'AI Email Draft Generation',
        description: 'Generate tailored email drafts using structured prompts mapped to specific client service offerings.',
        status: 'ready'
      },
      {
        id: 5,
        title: 'Human Review & Edit Console',
        description: 'Provide an interactive review interface allowing the human operator to inspect, edit, or reject any generated draft.',
        status: 'ready'
      },
      {
        id: 6,
        title: 'Explicit Approval Safety Gate',
        description: 'Hard safety gate preventing automatic sending. Transmission is blocked until an explicit operator approval action is recorded.',
        status: 'locked'
      },
      {
        id: 7,
        title: 'Audit & Telemetry Logging',
        description: 'Record full run status, scraper execution metrics, API failures, approval decisions, and dispatch timestamps.',
        status: 'pending'
      }
    ]
  },
  {
    id: 'agent-2',
    name: 'Agent 2: Competitor Intelligence',
    badge: 'Coming Soon',
    category: 'Market Analytics',
    description: 'Monitors competitor pricing pages, product updates, and public press releases. (Placeholder for future multi-agent expansion).',
    status: 'coming-soon',
    version: '0.0.1',
    capabilities: ['Competitor monitoring', 'Price change alerts'],
    stages: []
  },
  {
    id: 'agent-3',
    name: 'Agent 3: Customer Service & FAQ Engine',
    badge: 'Coming Soon',
    category: 'Support Automation',
    description: 'Ingests knowledge bases and drafts contextual customer responses for human review. (Placeholder for future multi-agent expansion).',
    status: 'coming-soon',
    version: '0.0.1',
    capabilities: ['FAQ ingestion', 'Contextual draft synthesis'],
    stages: []
  },
  {
    id: 'agent-4',
    name: 'Agent 4: Multi-Channel Dispatcher',
    badge: 'Coming Soon',
    category: 'Communications',
    description: 'Coordinates social and multi-channel outreach schedules with unified approval tokens. (Placeholder for future multi-agent expansion).',
    status: 'coming-soon',
    version: '0.0.1',
    capabilities: ['Multi-channel queueing', 'Rate limit manager'],
    stages: []
  }
];

export function App() {
  const [agents] = useState<AgentModel[]>(INITIAL_AGENTS);
  const [selectedAgentId, setSelectedAgentId] = useState<string>('agent-1');
  const [activeView, setActiveView] = useState<'agent' | 'environment' | 'history'>('agent');
  const backendStatus = useBackendStatus();

  const selectedAgent = agents.find((a) => a.id === selectedAgentId) || agents[0];

  return (
    <div className="app-container">
      <Sidebar
        agents={agents}
        selectedAgentId={selectedAgentId}
        onSelectAgent={setSelectedAgentId}
        activeView={activeView}
        onSelectView={setActiveView}
        backendStatus={backendStatus}
      />
      <main className="main-content">
        <Header activeView={activeView} currentAgent={selectedAgent} backendStatus={backendStatus} />
        {activeView === 'agent' ? (
          <AgentDetail
            agent={selectedAgent}
            backendStatus={backendStatus}
            onNavigateToHistory={() => setActiveView('history')}
          />
        ) : activeView === 'environment' ? (
          <EnvironmentStatus backendStatus={backendStatus} />
        ) : (
          <OutreachHistory
            backendStatus={backendStatus}
            onNavigateToConsole={() => setActiveView('agent')}
          />
        )}
      </main>
    </div>
  );
}

export default App;
