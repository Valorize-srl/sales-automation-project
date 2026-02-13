// === Enums ===

export type ICPStatus = "draft" | "active" | "archived";
export type LeadSource = "csv" | "apollo" | "manual";
export type CampaignStatus = "draft" | "active" | "paused" | "completed";
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
}

export interface EmailResponse {
  id: number;
  campaign_id: number;
  lead_id: number;
  message_body: string | null;
  direction: MessageDirection;
  sentiment: Sentiment | null;
  sentiment_score: number | null;
  ai_suggested_reply: string | null;
  human_approved_reply: string | null;
  status: ResponseStatus;
  created_at: string;
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
