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
  source_url?: string;
  description?: string;
  verified_fields?: string[];
  is_live?: boolean;
}

export interface ResearchRequest {
  topic: string;
  industry: string;
  location: string;
  max_results?: number;
  mode?: 'demo' | 'live';
  urls?: string[];
  follow_links?: boolean;
  max_pages_per_domain?: number;
}

export interface CrawlDiagnostic {
  url: string;
  status: string;
  reason: string;
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
  pages_crawled?: number;
  diagnostics?: CrawlDiagnostic[];
}

export interface AIProviderInfo {
  id: string;
  name: string;
  description: string;
  requires_key: boolean;
  is_available: boolean;
}

export interface AIProviderConfig {
  provider_type: 'template' | 'ollama' | 'openai';
  model_name?: string;
  api_base?: string;
  api_key?: string;
}

export interface OutreachDraft {
  id: string;
  lead_id: string;
  company_name: string;
  recipient_name: string;
  recipient_role: string;
  recipient_email: string;
  has_verified_email: boolean;
  subject: string;
  body: string;
  status: 'drafted' | 'approved' | 'rejected' | 'sent';
  created_at: string;
  source_url: string;
  grounding_notes: string;
  verified_facts_used: string[];
}

export interface OutreachDraftRequest {
  leads: LeadRecord[];
  service_offering: string;
  tone?: 'professional' | 'consultative' | 'concise';
  sender_name?: string;
  sender_company?: string;
  ai_config?: AIProviderConfig;
}

export interface OutreachDraftResponse {
  drafts: OutreachDraft[];
  total: number;
  verified_email_count: number;
  missing_email_count: number;
  provider_used: string;
}

export interface SendOutreachRequest {
  draft_id: string;
  approved: boolean;
  recipient_email: string;
  subject: string;
  body: string;
  has_verified_email?: boolean;
}

export interface DispatchStatusInfo {
  mode: 'simulation' | 'smtp' | 'resend';
  is_live: boolean;
  display_name: string;
  from_email: string;
  is_configured: boolean;
  notice: string;
}

export interface ProvidersResponse {
  providers: AIProviderInfo[];
  dispatch?: DispatchStatusInfo;
}

export interface SendOutreachResponse {
  draft_id: string;
  status: string;
  recipient_email: string;
  message: string;
  dispatched_at: string;
  is_simulated?: boolean;
  provider?: string;
}


