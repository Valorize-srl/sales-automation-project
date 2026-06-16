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
  lead_category: string | null;
  /** Number of messages in this conversation (same campaign + lead email).
   * The list endpoint groups multi-reply threads and returns the latest
   * message with this count; single-message rows have thread_count=1. */
  thread_count?: number;
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
  title: string | null;
  industry: string | null;
  location: string | null;
  client_tag: string | null;
  notes: string | null;
  tags: string[] | null;
  converted_at: string | null;
  created_at: string;
}

export interface PersonUpdate {
  first_name?: string;
  last_name?: string;
  email?: string;
  company_name?: string;
  linkedin_url?: string;
  phone?: string;
  title?: string;
  industry?: string;
  location?: string;
  client_tag?: string;
  notes?: string;
  converted?: boolean;
}

export interface CompanyCreate {
  name: string;
  email?: string | null;
  phone?: string | null;
  linkedin_url?: string | null;
  industry?: string | null;
  location?: string | null;
  province?: string | null;
  zip_code?: string | null;
  signals?: string | null;
  website?: string | null;
  notes?: string | null;
  revenue?: number | null;
  employee_count?: number | null;
  vat_number?: string | null;
  tax_id?: string | null;
  source_company_id?: string | null;
}

export interface CompanyUpdate {
  name?: string | null;
  email?: string | null;
  phone?: string | null;
  linkedin_url?: string | null;
  industry?: string | null;
  location?: string | null;
  province?: string | null;
  zip_code?: string | null;
  signals?: string | null;
  website?: string | null;
  client_tag?: string | null;
  notes?: string | null;
  revenue?: number | null;
  employee_count?: number | null;
  vat_number?: string | null;
  tax_id?: string | null;
  source_company_id?: string | null;
  generic_emails?: string[] | null;
}

export type PriorityTier = "A" | "B" | "C";
export type LifecycleStage = "new" | "enriched" | "ready_for_outreach";

export interface DecisionMakerSummary {
  id: number;
  first_name: string | null;
  last_name: string | null;
  title: string | null;
  email: string | null;
  linkedin_url: string | null;
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
  province: string | null;
  zip_code: string | null;
  signals: string | null;
  website: string | null;
  client_tag: string | null;
  notes: string | null;
  // Raw firmographics
  revenue: number | null;
  employee_count: number | null;
  // Fiscal IDs
  vat_number: string | null;
  tax_id: string | null;
  // External origin id (e.g. Seikoo company id); null = manual / other source
  source_company_id: string | null;
  custom_fields: Record<string, string> | null;
  list_ids?: number[];
  // Aggregated work emails of decision makers (Person.email of linked persons)
  work_emails?: string[];
  // Compact summary of linked decision makers (people)
  decision_makers?: DecisionMakerSummary[];
  // Enrichment fields
  generic_emails?: string[];
  enrichment_source?: "apollo" | "web_scrape" | "both";
  enrichment_date?: string;
  enrichment_status?: "pending" | "completed" | "failed" | "not_needed";
  // ICP scoring fields (populated by Lead Planner & Scorer)
  icp_score?: number | null;
  priority_tier?: PriorityTier | null;
  lifecycle_stage?: LifecycleStage | null;
  revenue_band?: string | null;
  employee_count_band?: string | null;
  industry_standardized?: string | null;
  reason_summary?: string | null;
  last_scored_at?: string | null;
  scored_with_icp_id?: number | null;
  created_at: string;
  people_count: number;
}

export interface PersonListResponse {
  people: Person[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface CompanyListResponse {
  companies: Company[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface CompanyCSVMapping {
  name: string | null;
  email: string | null;
  phone: string | null;
  linkedin_url: string | null;
  industry: string | null;
  location: string | null;
  province: string | null;
  signals: string | null;
  website: string | null;
  revenue: string | null;
  employee_count: string | null;
}

export interface CompanyCSVUploadResponse {
  headers: string[];
  mapping: CompanyCSVMapping;
  rows: Record<string, string>[];
  preview_rows: Record<string, string>[];
  total_rows: number;
  unmapped_headers: string[];
}

// === API Responses ===

export interface ICPListResponse {
  icps: ICP[];
  total: number;
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

export interface ResponseStatsChartEntry {
  date: string;
  interested: number;
  positive: number;
  neutral: number;
  negative: number;
}

export interface ResponseStats {
  total: number;
  by_sentiment: Record<string, number>;
  by_status: Record<string, number>;
  chart_data: ResponseStatsChartEntry[];
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
  opens: number;
  replies: number;
}

export interface DashboardIntentEntry {
  category: string;
  count: number;
}

export interface DashboardTopCampaign {
  id: number;
  name: string;
  total_sent: number;
  total_opened: number;
  total_replied: number;
  reply_rate: number;
}

export interface DashboardStats {
  people_count: number;
  companies_count: number;
  active_campaigns: number;
  total_sent: number;
  total_opened: number;
  total_replied: number;
  converted_count: number;
  chart_data: DashboardChartEntry[];
  intent_breakdown: DashboardIntentEntry[];
  top_campaigns: DashboardTopCampaign[];
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
    by_tool?: Record<string, number>;
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

export interface ClientCostSummary {
  client_tag: string;
  total_sessions: number;
  total_searches: number;
  total_apollo_credits: number;
  total_claude_input_tokens: number;
  total_claude_output_tokens: number;
  cost_apollo_usd: number;
  cost_claude_usd: number;
  total_cost_usd: number;
  first_activity: string | null;
  last_activity: string | null;
}

export interface ClientSummaryResponse {
  clients: ClientCostSummary[];
  totals: {
    total_cost_usd: number;
    total_apollo_credits: number;
    total_claude_tokens: number;
    total_clients: number;
  };
}

export interface Setting {
  key: string;
  value: string;
  description: string | null;
  updated_at: string;
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

// === AI Agents System ===

export interface LeadList {
  id: number;
  ai_agent_id: number | null;
  name: string;
  description: string | null;
  client_tag: string | null;
  color: string | null;
  icon: string | null;
  filters_snapshot: Record<string, unknown> | null;
  people_count: number;
  companies_count: number;
  /** Distinct DMs (Person rows) with a populated email that belong to any
   * company in this list — i.e. the "ready-to-push" count for outreach. */
  dm_with_email_count: number;
  created_at: string;
  updated_at: string;
  total_leads: number;
}

// === Filters for the Companies dashboard ===
export interface CompanyFilters {
  search?: string;
  industry?: string;
  province?: string;
  location?: string;
  client_tag?: string;
  priority_tier?: "A" | "B" | "C";
  lifecycle_stage?: "new" | "enriched" | "ready_for_outreach";
  list_id?: number;
  has_email?: boolean;
  has_phone?: boolean;
  has_linkedin?: boolean;
  has_website?: boolean;
  has_score?: boolean;
  has_decision_makers?: boolean;
  has_dm_with_email?: boolean;
  has_dm_with_linkedin?: boolean;
  revenue_min?: number;
  revenue_max?: number;
  employee_count_min?: number;
  employee_count_max?: number;
  score_min?: number;
  score_max?: number;
  decision_maker_name_contains?: string;
  // CAP prefix match (e.g. "20" → 20xxx Milano area)
  zip_code_prefix?: string;
  // Presence toggle for VAT number / Partita IVA
  has_vat?: boolean;
  // Prefix match on the indexed fiscal columns (B-tree, sub-ms latency)
  vat_number_prefix?: string;
  tax_id_prefix?: string;
  // Eolo coverage clusters — union match on companies whose zip_code is
  // in the CAP set of any of the listed clusters. Backend converts the
  // array to a comma-separated string via String(array) in the encoder.
  eolo_clusters?: string[];
  // Advanced filters (encoded as the `filters` JSON query param)
  cf?: Record<string, string | { eq?: string; contains?: string; min?: number; max?: number }>;
  name_contains?: string;
}

export interface LeadListCreate {
  name: string;
  ai_agent_id?: number;
  client_tag?: string;
  description?: string;
  filters_snapshot?: Record<string, any>;
  person_ids?: number[];
  company_ids?: number[];
}

export interface CampaignLeadListInfo {
  id: number;
  name: string;
  client_tag: string | null;
  people_count: number;
  companies_count: number;
  pushed_to_instantly: boolean;
  pushed_count: number;
  added_at: string | null;
}

export interface AddListToCampaignResponse {
  campaign_id: number;
  lead_list_id: number;
  lead_list_name: string;
  people_in_list: number;
  valid_leads?: number;
  pushed_to_instantly: number;
  errors: number;
  skipped_invalid?: number;
  error_details?: string[];
  message: string;
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

// === Detail Dialog Types ===

export interface CampaignSummary {
  id: number;
  name: string;
  status: string;
  total_sent: number;
  total_opened: number;
  total_replied: number;
}

export interface PersonSummary {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
  linkedin_url: string | null;
  title: string | null;
  location: string | null;
  converted_at: string | null;
}

export interface CompanyDetailResponse {
  company: Company;
  people: PersonSummary[];
  campaigns: CampaignSummary[];
}

// ── Prospecting Tools (Apollo Search People only) ──────────────────

export interface ToolSearchResponse {
  results: Record<string, unknown>[];
  total: number;
  credits_used: number;
  cost_usd: number;
}

export interface ImportLeadsResponse {
  imported: number;
  skipped: number;
  errors: number;
  message: string;
}

export interface ApolloSearchPeopleParams {
  person_titles?: string[];
  person_locations?: string[];
  person_seniorities?: string[];
  organization_keywords?: string[];
  organization_sizes?: string[];
  keywords?: string;
  per_page?: number;
  client_tag?: string;
}

export interface ImportLeadsParams {
  results: Record<string, unknown>[];
  import_type: "people" | "companies";
  client_tag?: string;
  list_id?: number;
}

export interface WebsiteScrapeResult {
  url: string;
  emails: string[];
  linkedin_url: string | null;
  pages_visited: number;
  error: string | null;
}
