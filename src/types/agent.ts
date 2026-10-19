export type AgentStatus = 'active' | 'configured' | 'disabled' | 'coming-soon';

export interface AgentStage {
  id: number;
  title: string;
  description: string;
  status: 'pending' | 'ready' | 'locked';
}

export interface AgentModel {
  id: string;
  name: string;
  badge: string;
  category: string;
  description: string;
  status: AgentStatus;
  version: string;
  stages: AgentStage[];
  capabilities: string[];
}

export interface EnvironmentPrerequisite {
  name: string;
  version: string;
  status: 'verified' | 'action-required' | 'optional';
  details: string;
}
