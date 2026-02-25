// === Enums ===

export type ICPStatus = "draft" | "active" | "archived";
export type LeadSource = "csv" | "apollo" | "manual";
export type CampaignStatus = "draft" | "active" | "paused" | "completed" | "scheduled" | "error";
export type MessageDirection = "inbound" | "outbound";
export type Sentiment = "positive" | "negative" | "neutral" | "interested";
export type ResponseStatus = "pending" | "ai_replied" | "human_approved" | "sent" | "ignored";

// === Models ===

export interface ICP {
  id: number;
  name: string;
  description: string | null;
  industry: string | null;
  company_size: string | null;
  job_titles: string | null;
  geography: string | null;
  revenue_range: string | null;
  keywords: string | null;
  raw_input: string | null;
  status: ICPStatus;
  created_at: string;
}

export interface Lead {
  id: number;
  icp_id: number;
  first_name: string;
  last_name: string;
  email: string;
  company: string | null;
  job_title: string | null;
  industry: string | null;
  linkedin_url: string | null;
  phone: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  zip_code: string | null;
  country: string | null;
  website: string | null;
  custom_fields: Record<string, string> | null;
  source: LeadSource;
  verified: boolean;
  score: number | null;
  client_tag: string | null;
  created_at: string;
}

export interface Campaign {
  id: number;
  icp_id: number | null;
  icp_name: string | null;
  instantly_campaign_id: string | null;
  name: string;
  status: CampaignStatus;
  subject_lines: string | null;
  email_templates: string | null;
  total_sent: number;
  total_opened: number;
  total_replied: number;
  created_at: string;
  ai_agent_id: number | null;
  ai_agent_name: string | null;
}

export interface EmailResponse {
  id: number;
  campaign_id: number;
  lead_id: number | null;
  instantly_email_id: string | null;
  from_email: string | null;
  sender_email: string | null;
  subject: string | null;
  thread_id: string | null;
  message_body: string | null;
  direction: MessageDirection;
  sentiment: Sentiment | null;
  sentiment_score: number | null;
  ai_suggested_reply: string | null;
  human_approved_reply: string | null;
  status: ResponseStatus;
  received_at: string | null;
  created_at: string;
}

export interface EmailResponseWithDetails extends EmailResponse {
  lead_name: string | null;
  lead_email: string | null;
  lead_company: string | null;
  campaign_name: string | null;
}

export interface Person {
  id: number;
  first_name: string;
  last_name: string;
  company_id: number | null;
  company_name: string | null;
  email: string;
  linkedin_url: string | null;
  phone: string | null;
  industry: string | null;
  location: string | null;
  client_tag: string | null;
  created_at: string;
}

export interface Company {
  id: number;
  name: string;
  email: string | null;
  email_domain: string | null;
  phone: string | null;
  linkedin_url: string | null;
  industry: string | null;
  location: string | null;
  signals: string | null;
  website: string | null;
  client_tag: string | null;
  // Enrichment fields
  generic_emails?: string[];
  enrichment_source?: "apollo" | "web_scrape" | "both";
  enrichment_date?: string;
  enrichment_status?: "pending" | "completed" | "failed" | "not_needed";
  created_at: string;
  people_count: number;
}

export interface PersonListResponse {
  people: Person[];
  total: number;
}

export interface CompanyListResponse {
  companies: Company[];
  total: number;
}

export interface PersonCSVMapping {
  first_name: string | null;
  last_name: string | null;
  company_name: string | null;
  email: string | null;
  linkedin_url: string | null;
  phone: string | null;
  industry: string | null;
  location: string | null;
}

export interface CompanyCSVMapping {
  name: string | null;
  email: string | null;
  phone: string | null;
  linkedin_url: string | null;
  industry: string | null;
  location: string | null;
  signals: string | null;
  website: string | null;
}

export interface PersonCSVUploadResponse {
  headers: string[];
  mapping: PersonCSVMapping;
  rows: Record<string, string>[];
  preview_rows: Record<string, string>[];
  total_rows: number;
  unmapped_headers: string[];
}

export interface CompanyCSVUploadResponse {
  headers: string[];
  mapping: CompanyCSVMapping;
  rows: Record<string, string>[];
  preview_rows: Record<string, string>[];
  total_rows: number;
  unmapped_headers: string[];
}

export interface AnalyticsEntry {
  id: number;
  campaign_id: number;
  date: string;
  emails_sent: number;
  opens: number;
  replies: number;
  positive_replies: number;
  meetings_booked: number;
}

// === API Responses ===

export interface HealthCheckResponse {
  status: string;
  version: string;
  environment: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ICPExtracted {
  name: string;
  description?: string | null;
  industry?: string | null;
  company_size?: string | null;
  job_titles?: string | null;
  geography?: string | null;
  revenue_range?: string | null;
  keywords?: string | null;
}

export interface ICPListResponse {
  icps: ICP[];
  total: number;
}

export interface FileUploadResponse {
  filename: string;
  text: string;
  length: number;
}

export interface LeadListResponse {
  leads: Lead[];
  total: number;
}

export interface CSVColumnMapping {
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  company: string | null;
  job_title: string | null;
  industry: string | null;
  linkedin_url: string | null;
  phone: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  zip_code: string | null;
  country: string | null;
  website: string | null;
}

export interface CSVUploadResponse {
  headers: string[];
  mapping: CSVColumnMapping;
  rows: Record<string, string>[];
  preview_rows: Record<string, string>[];
  total_rows: number;
  unmapped_headers: string[];
}

export interface CSVImportResponse {
  imported: number;
  duplicates_skipped: number;
  errors: number;
}

export interface CampaignListResponse {
  campaigns: Campaign[];
  total: number;
}

export interface InstantlySyncResponse {
  imported: number;
  updated: number;
  errors: number;
}

export interface LeadUploadResponse {
  pushed: number;
  errors: number;
}

export interface EmailStep {
  step: number;
  subject: string;
  body: string;
  wait_days: number;
}

export interface EmailTemplateGenerateResponse {
  subject_lines: string[];
  email_steps: EmailStep[];
}

export interface EmailResponseListResponse {
  responses: EmailResponseWithDetails[];
  total: number;
}

export interface FetchRepliesResponse {
  fetched: number;
  skipped: number;
  errors: number;
}

export interface SendReplyResponse {
  success: boolean;
  message: string;
}

export interface InstantlyEmailAccount {
  email: string;
  first_name: string | null;
  last_name: string | null;
  status: number | null;
}

export interface InstantlyEmailAccountListResponse {
  accounts: InstantlyEmailAccount[];
  total: number;
}

export interface PushSequencesResponse {
  success: boolean;
  steps_pushed: number;
  message: string;
}

export interface DashboardChartEntry {
  date: string;
  sent: number;
  replies: number;
}

export interface DashboardStats {
  people_count: number;
  companies_count: number;
  active_campaigns: number;
  total_sent: number;
  total_opened: number;
  total_replied: number;
  chart_data: DashboardChartEntry[];
}

export interface ApolloPersonResult {
  first_name: string;
  last_name: string;
  title: string | null;
  company: string | null;
  linkedin_url: string | null;
  location: string | null;
  email: string | null;
  phone: string | null;
  website: string | null;
  industry: string | null;
  apollo_id?: string;
  is_enriched?: boolean;
}

export interface ApolloEnrichResponse {
  enriched: Record<string, { id: string; email?: string; phone?: string; direct_phone?: string; linkedin_url?: string; first_name?: string; last_name?: string; city?: string; state?: string; country?: string }>;
  credits_consumed: number;
  enriched_count: number;
}

export interface ApolloCompanyResult {
  name: string;
  industry: string | null;
  size: string | null;
  website: string | null;
  linkedin_url: string | null;
  location: string | null;
  email: string | null;
  phone: string | null;
  signals: string | null;
}

export interface ApolloUsage {
  apollo_credits: number;
  claude_tokens: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  };
  estimated_cost_usd: {
    apollo_usd: number;
    claude_usd: number;
    total_usd: number;
  };
}

export interface ApolloSearchResponse {
  results: ApolloPersonResult[] | ApolloCompanyResult[];
  total: number;
  search_type: "people" | "companies";
  returned: number;
  credits_consumed?: number;
  usage?: ApolloUsage;
}

export interface ApolloImportResponse {
  imported: number;
  duplicates_skipped: number;
  errors: number;
}

// === Usage Tracking & Settings ===

export interface SearchHistory {
  id: number;
  search_type: "people" | "companies";
  search_query: string | null;
  filters_applied: Record<string, unknown>;
  results_count: number;
  apollo_credits_consumed: number;
  claude_input_tokens: number;
  claude_output_tokens: number;
  cost_apollo_usd: number;
  cost_claude_usd: number;
  cost_total_usd: number;
  client_tag: string | null;
  icp_id: number | null;
  created_at: string;
}

export interface UsageStats {
  total_searches: number;
  total_results: number;
  total_apollo_credits: number;
  total_claude_input_tokens: number;
  total_claude_output_tokens: number;
  total_cost_usd: number;
  cost_breakdown: {
    apollo_usd: number;
    claude_usd: number;
  };
  searches_by_day: Array<{
    date: string;
    count: number;
    cost_usd: number;
  }>;
}

export interface UsageStatsResponse {
  stats: UsageStats;
  date_range: {
    start_date: string;
    end_date: string;
  };
}

export interface SearchHistoryListResponse {
  history: SearchHistory[];
  total: number;
}

export interface Setting {
  key: string;
  value: string;
  description: string | null;
  updated_at: string;
}

export interface ApolloSearchRequest {
  search_type: "people" | "companies";
  filters: {
    person_titles?: string[];
    person_locations?: string[];
    person_seniorities?: string[];
    organization_locations?: string[];
    organization_keywords?: string[];
    organization_sizes?: string[];
    technologies?: string[];
    keywords?: string;
  };
  per_page?: number;
  client_tag?: string;
  claude_tokens?: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  };
}

export interface ApolloImportRequest {
  results: Array<Record<string, unknown>>;
  target: "people" | "companies";
  client_tag?: string;
  auto_enrich?: boolean; // Auto-enrich companies with website scraping
}

// === Enrichment ===

export interface EnrichmentResult {
  company_id: number;
  company_name: string;
  status: "completed" | "failed" | "skipped";
  emails_found: string[];
  error?: string;
}

export interface CompanyEnrichmentResponse {
  enriched: number;
  failed: number;
  skipped: number;
  results: EnrichmentResult[];
}

// === Session-based Chat ===

export type SessionStatus = "active" | "archived" | "completed";

export interface ChatSession {
  id: number;
  session_uuid: string;
  title: string | null;
  icp_id: number | null;
  current_icp_draft: Record<string, unknown> | null;
  session_metadata: Record<string, unknown> | null;
  total_claude_input_tokens: number;
  total_claude_output_tokens: number;
  total_apollo_credits: number;
  total_cost_usd: number;
  client_tag: string | null;
  status: SessionStatus;
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
}

export interface ChatMessageModel {
  id: number;
  session_id: number;
  role: "user" | "assistant" | "tool_result";
  content: string;
  tool_calls: unknown[] | null;
  tool_results: unknown[] | null;
  input_tokens: number;
  output_tokens: number;
  message_metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface ToolExecution {
  id: number;
  session_id: number;
  message_id: number | null;
  tool_name: string;
  tool_call_id: string;
  tool_input: Record<string, unknown>;
  tool_output: Record<string, unknown>;
  status: "success" | "error" | "partial";
  error_message: string | null;
  execution_time_ms: number | null;
  credits_consumed: number;
  cost_usd: number;
  created_at: string;
}

export interface SessionSummary {
  session_id: number;
  session_uuid: string;
  message_count: number;
  tool_stats: Record<string, number>;
  total_claude_input_tokens: number;
  total_claude_output_tokens: number;
  total_apollo_credits: number;
  total_cost_usd: number;
  status: SessionStatus;
  created_at: string;
  last_message_at: string | null;
}

export interface SessionWithMessages {
  session: ChatSession;
  messages: ChatMessageModel[];
  summary: SessionSummary;
}

export interface SessionListItem {
  session_uuid: string;
  title: string | null;
  status: SessionStatus;
  client_tag: string | null;
  created_at: string;
  last_message_at: string | null;
  total_cost_usd: number;
  message_count: number;
}

export interface SessionListResponse {
  sessions: SessionListItem[];
  limit: number;
  offset: number;
}

export interface CreateSessionRequest {
  client_tag?: string;
  title?: string;
}

export interface ChatStreamRequest {
  message: string;
  file_content?: string;
}

export interface SessionResponse {
  session_uuid: string;
  title: string | null;
  status: SessionStatus;
  client_tag: string | null;
  created_at: string;
  last_message_at: string | null;
  total_cost_usd: number;
  total_claude_input_tokens: number;
  total_claude_output_tokens: number;
  total_apollo_credits: number;
}

export interface SSETextEvent {
  type: "text";
  content: string;
}

export interface SSEToolStartEvent {
  type: "tool_start";
  tool: string;
  input: Record<string, unknown>;
}

export interface SSEToolCompleteEvent {
  type: "tool_complete";
  tool: string;
  summary: Record<string, unknown>;
}

export interface SSEDoneEvent {
  type: "done";
}

export interface SSEErrorEvent {
  type: "error";
  error: string;
  message: string;
}

export type SSEEvent =
  | SSETextEvent
  | SSEToolStartEvent
  | SSEToolCompleteEvent
  | SSEDoneEvent
  | SSEErrorEvent;

// === AI Agents System ===

export interface AIAgent {
  id: number;
  name: string;
  client_tag: string;
  description: string | null;
  icp_config: Record<string, any>;
  signals_config: Record<string, any> | null;
  knowledge_base_text: string | null;
  knowledge_base_source: string | null;
  knowledge_base_files: Array<{filename: string; upload_date: string; size: number}> | null;
  apollo_credits_allocated: number;
  apollo_credits_consumed: number;
  last_credits_reset: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  created_by: number | null;
  credits_remaining: number;
  credits_percentage_used: number;
}

export interface AIAgentCreate {
  name: string;
  client_tag: string;
  description?: string;
  icp_config: Record<string, any>;
  signals_config?: Record<string, any>;
  apollo_credits_allocated?: number;
}

export interface AIAgentUpdate {
  name?: string;
  client_tag?: string;
  description?: string;
  icp_config?: Record<string, any>;
  signals_config?: Record<string, any>;
  apollo_credits_allocated?: number;
  is_active?: boolean;
}

export interface AIAgentStats {
  agent_id: number;
  agent_name: string;
  client_tag: string;
  total_leads: number;
  total_people: number;
  total_companies: number;
  apollo_credits_allocated: number;
  apollo_credits_consumed: number;
  apollo_credits_remaining: number;
  apollo_credits_percentage_used: number;
  lists_created: number;
  campaigns_connected: number;
  signals_detected: number;
}

export interface LeadList {
  id: number;
  ai_agent_id: number;
  name: string;
  description: string | null;
  filters_snapshot: Record<string, any> | null;
  people_count: number;
  companies_count: number;
  created_at: string;
  updated_at: string;
  total_leads: number;
}

export interface LeadListCreate {
  ai_agent_id: number;
  name: string;
  description?: string;
  filters_snapshot?: Record<string, any>;
}

export interface AIAgentApolloSearchRequest {
  per_page?: number;
  auto_create_list?: boolean;
  list_name?: string;
}

export interface ApolloSearchResult {
  list_id: number | null;
  list_name: string | null;
  results_count: number;
  people_count: number;
  companies_count: number;
  credits_consumed: number;
  credits_remaining: number;
}

export interface EnrichEstimate {
  total_leads: number;
  apollo_credits_needed: number;
  estimated_cost_usd: number;
}

export interface BulkOperationResult {
  people_affected: number;
  companies_affected: number;
  message: string;
}

// === Instantly Account & Warmup ===

export interface InstantlyAccountDetails {
  email: string;
  first_name: string | null;
  last_name: string | null;
  status: number;
  warmup_status: string | null;
  warmup_limit: number | null;
  daily_limit: number | null;
  sending_gap: number | null;
  tracking_domain_name: string | null;
}

export interface WarmupAnalytics {
  emails_sent: number;
  emails_received: number;
  inbox_rate: number;
  spam_rate: number;
  reply_rate: number;
  daily_data: Array<{
    date: string;
    sent: number;
    received: number;
    inbox: number;
    spam: number;
  }>;
}

export interface LeadSyncResponse {
  imported: number;
  skipped: number;
  errors: number;
  message: string;
}

export interface DailyAnalyticsEntry {
  date: string;
  emails_sent: number;
  opens: number;
  clicks: number;
  replies: number;
  bounces: number;
}
