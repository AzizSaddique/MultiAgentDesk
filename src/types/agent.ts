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

export interface OutreachHistoryItem {
  id: string;
  draft_id?: string | null;
  recipient_email: string;
  recipient_name?: string | null;
  company_name?: string | null;
  subject: string;
  body_snippet?: string | null;
  source_url?: string | null;
  status: 'simulated' | 'sent' | 'failed' | 'drafted' | string;
  provider_mode?: string | null;
  dispatched_at: string;
  error_message?: string | null;
  is_simulated: boolean;
  delivery_metadata?: Record<string, any> | null;
}

export interface OutreachHistoryResponse {
  items: OutreachHistoryItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  status_counts: Record<string, number>;
}

export interface HistoryFilterParams {
  status?: string;
  query?: string;
  start_date?: string;
  end_date?: string;
  page?: number;
  page_size?: number;
}

export interface DiscoveryPlan {
  original_prompt: string;
  industry: string;
  location_region?: string | null;
  location_city?: string | null;
  location_country?: string | null;
  keywords: string[];
  target_lead_count: number;
  company_size_criteria?: string | null;
  service_criteria?: string | null;
  desired_contact_info: string[];
  search_language: string;
  max_crawl_depth: number;
  max_pages_per_domain: number;
  is_ambiguous: boolean;
  clarification_question?: string | null;
}

export interface DiscoveryPlanRequest {
  prompt: string;
  ai_config?: AIProviderConfig;
}

export interface DiscoveryJobCreateRequest {
  plan: DiscoveryPlan;
  search_provider?: string;
  ai_config?: AIProviderConfig;
}

export interface DiscoveredLeadRecord {
  id: string;
  job_id: string;
  company_name: string;
  website: string;
  industry?: string;
  city?: string;
  country?: string;
  services_description?: string;
  email?: string;
  email_verification_status: 'verified_public' | 'found_unverified' | 'not_found' | 'invalid';
  phone?: string;
  phone_verification_status: 'verified_public' | 'unverified' | 'not_found';
  source_urls: string[];
  discovery_source: string;
  discovery_query: string;
  discovered_at: string;
  relevance_score: number;
  relevance_explanation: string;
  research_status: 'completed' | 'skipped' | 'failed';
  failure_reason?: string | null;
  verified_fields: string[];
  is_live: boolean;
}

export interface DiscoveryJob {
  id: string;
  prompt: string;
  status: 'pending' | 'running' | 'completed' | 'cancelled' | 'failed';
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  provider_used: string;
  total_target: number;
  discovered_count: number;
  verified_email_count: number;
  duplicate_count: number;
  skipped_count: number;
  failed_count: number;
  progress_percent: number;
  current_stage?: string;
  plan_json?: string;
  error_message?: string | null;
}

export interface DiscoveryJobResponse {
  job: DiscoveryJob;
  leads: DiscoveredLeadRecord[];
}

export interface DiscoveredLeadsResponse {
  leads: DiscoveredLeadRecord[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  verification_counts: Record<string, number>;
}

export interface SearchProviderInfo {
  id: string;
  name: string;
  description: string;
  is_configured: boolean;
  requires_key: boolean;
  notice: string;
}

export interface SearchProvidersResponse {
  providers: SearchProviderInfo[];
}

export interface TransferToOutreachRequest {
  job_id: string;
  lead_ids: string[];
}
