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

export interface LeadRecord {
  id: string;
  company_name: string;
  contact_name: string;
  contact_role: string;
  email: string;
  website: string;
  industry: string;
  location: string;
  source_note: string;
  created_at: string;
}

export interface ResearchRequest {
  topic: string;
  industry: string;
  location: string;
  max_results?: number;
}

export interface ResearchResponse {
  topic: string;
  industry: string;
  location: string;
  provider: string;
  is_demo: boolean;
  disclaimer: string;
  total_results: number;
  leads: LeadRecord[];
}
