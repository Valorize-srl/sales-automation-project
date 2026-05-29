// Use relative URLs so requests go through Next.js rewrites (same origin = no CORS)
// Only use full backend URL for server-side or local dev without rewrites
const API_BASE_URL = "";

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<T> {
    const url = `${this.baseUrl}/api${endpoint}`;
    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      let errorMessage = `API error: ${response.status}`;
      try {
        const errorData = await response.json();
        if (errorData.detail) {
          errorMessage = errorData.detail;
        }
      } catch {
        // If parsing fails, use generic message
      }
      throw new Error(errorMessage);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: "GET" });
  }

  async post<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: "POST",
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async put<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: "PUT",
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async patch<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: "PATCH",
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: "DELETE" });
  }

  async healthCheck(): Promise<{ status: string; version: string }> {
    const response = await fetch(`${this.baseUrl}/health`);
    return response.json();
  }
  async uploadCompaniesCSV(file: File): Promise<import("@/types").CompanyCSVUploadResponse> {
    const formData = new FormData();
    formData.append("file", file);
    const url = `${this.baseUrl}/api/companies/csv/upload`;
    const response = await fetch(url, { method: "POST", body: formData });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Upload error: ${response.status}`);
    }
    return response.json();
  }

  // === Usage Tracking & Settings ===

  async getUsageStats(
    startDate?: string,
    endDate?: string,
    clientTag?: string
  ): Promise<import("@/types").UsageStatsResponse> {
    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    if (clientTag) params.append("client_tag", clientTag);
    const query = params.toString() ? `?${params.toString()}` : "";
    return this.get(`/usage/stats${query}`);
  }

  async getSearchHistory(
    startDate?: string,
    endDate?: string,
    clientTag?: string,
    limit?: number
  ): Promise<import("@/types").SearchHistoryListResponse> {
    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    if (clientTag) params.append("client_tag", clientTag);
    if (limit) params.append("limit", limit.toString());
    const query = params.toString() ? `?${params.toString()}` : "";
    return this.get(`/usage/history${query}`);
  }

  async getClientSummary(): Promise<import("@/types").ClientSummaryResponse> {
    return this.get("/usage/client-summary");
  }

  async getSetting(key: string): Promise<import("@/types").Setting> {
    return this.get(`/settings/${key}`);
  }

  async updateSetting(key: string, value: string): Promise<import("@/types").Setting> {
    return this.put(`/settings/${key}`, { value });
  }

  // === Company Enrichment ===

  async enrichCompany(companyId: number): Promise<import("@/types").EnrichmentResult> {
    return this.post(`/companies/${companyId}/enrich`);
  }

  async enrichCompaniesBatch(
    companyIds: number[],
    force = false
  ): Promise<import("@/types").CompanyEnrichmentResponse> {
    return this.post(`/companies/enrich-batch`, { company_ids: companyIds, force });
  }
  // ============================================================================
  // Lead Lists
  // ============================================================================

  async createLeadList(data: import("@/types").LeadListCreate): Promise<import("@/types").LeadList> {
    return this.post("/lead-lists", data);
  }

  async getLeadLists(params?: { skip?: number; limit?: number }): Promise<{ lists: import("@/types").LeadList[]; total: number }> {
    const query = new URLSearchParams();
    if (params?.skip) query.set("skip", String(params.skip));
    if (params?.limit) query.set("limit", String(params.limit));
    const queryString = query.toString();
    return this.get(`/lead-lists${queryString ? `?${queryString}` : ''}`);
  }

  async getLeadList(id: number): Promise<import("@/types").LeadList> {
    return this.get(`/lead-lists/${id}`);
  }

  async updateLeadList(id: number, data: { name?: string; description?: string; color?: string; icon?: string; client_tag?: string }): Promise<import("@/types").LeadList> {
    return this.put(`/lead-lists/${id}`, data);
  }

  async deleteLeadList(id: number): Promise<void> {
    await this.delete(`/lead-lists/${id}`);
  }

  async addLeadsToList(listId: number, personIds?: number[], companyIds?: number[]): Promise<import("@/types").BulkOperationResult> {
    return this.post(`/lead-lists/${listId}/leads`, { person_ids: personIds, company_ids: companyIds });
  }

  async exportLeadList(id: number): Promise<Blob> {
    const response = await fetch(`${this.baseUrl}/api/lead-lists/${id}/export`);
    if (!response.ok) throw new Error("Export failed");
    return response.blob();
  }

  // ============================================================================
  // Bulk Operations
  // ============================================================================

  async bulkEnrichPeople(person_ids: number[]): Promise<{ enriched_count: number; credits_consumed: number; message: string }> {
    return this.post("/people/bulk-enrich", person_ids);
  }

  async bulkTagPeople(person_ids: number[], tags_to_add?: string[], tags_to_remove?: string[]): Promise<{ people_tagged: number; message: string }> {
    return this.post("/people/bulk-tag", { person_ids, tags_to_add, tags_to_remove });
  }

  async bulkDeletePeople(person_ids: number[]): Promise<{ deleted_count: number; message: string }> {
    return this.post("/people/bulk-delete", person_ids);
  }

  async bulkExportPeople(person_ids: number[]): Promise<Blob> {
    const response = await fetch(`${this.baseUrl}/api/people/bulk-export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(person_ids),
    });
    if (!response.ok) throw new Error("Export failed");
    return response.blob();
  }

  async findPeopleAtCompany(companyId: number, params?: { titles?: string[]; seniorities?: string[]; per_page?: number }): Promise<{ company_id: number; company_name: string; results: Record<string, unknown>[]; total: number }> {
    return this.post(`/companies/${companyId}/find-people`, params || {});
  }

  async findAndImportDecisionMakers(
    companyId: number,
    params?: { titles?: string[]; seniorities?: string[]; per_page?: number },
  ): Promise<{ imported_count: number; candidates: number }> {
    const r = await this.post<{
      candidates: number;
      imported_count: number;
      duplicates_skipped: number;
    }>(`/companies/${companyId}/find-and-import-decision-makers`, {
      titles: params?.titles,
      seniorities: params?.seniorities,
      per_page: params?.per_page ?? 25,
    });
    return { imported_count: r.imported_count, candidates: r.candidates };
  }

  /** Findymail company lookup: fills missing fields (linkedin_url, industry,
   * location, email_domain) on the company by querying Findymail with
   * whatever signal we have (website > linkedin_url > name). */
  async findymailFindCompanyInfo(companyId: number): Promise<{
    company_id: number;
    company_name: string;
    found: boolean;
    updated_fields: string[];
    matched: {
      name: string | null;
      domain: string | null;
      linkedin_url: string | null;
      industry: string | null;
      company_size: string | null;
      city: string | null;
      region: string | null;
      country: string | null;
    } | null;
  }> {
    return this.post(`/companies/${companyId}/findymail-find-company-info`);
  }

  /** Findymail "find by role": given target_titles + the company's domain
   * (derived from email_domain or website), Findymail returns name + email
   * for each contact at that company matching the roles. Persists each new
   * contact as a Person record (dedup by email/linkedin_url). */
  async findDecisionMakersViaFindymail(
    companyId: number,
    targetTitles: string[],
  ): Promise<{
    company_id: number;
    company_name: string;
    domain?: string | null;
    domain_resolved_via?: "db" | "linkedin";
    candidates_found: number;
    imported_count: number;
    duplicates_skipped: number;
    people: Array<{
      id: number;
      first_name: string;
      last_name: string;
      title: string | null;
      email: string | null;
      linkedin_url: string | null;
    }>;
  }> {
    return this.post(`/companies/${companyId}/findymail-find-decision-makers`, {
      target_titles: targetTitles,
    });
  }

  /** Findymail "find DM complete": chains /search/employees → /search/linkedin
   * to return name + linkedin URL + email in one shot. `maxResults` is clamped
   * to [1, 10] server-side. Costs ~1 credit per profile + 1 per email found. */
  async findDMViaLinkedInFindymail(
    companyId: number,
    targetTitles: string[],
    maxResults: number = 5,
  ): Promise<{
    company_id: number;
    company_name: string;
    website?: string | null;
    website_resolved_via?: "db" | "linkedin";
    candidates_found: number;
    with_email: number;
    imported_count: number;
    duplicates_skipped: number;
    people: Array<{
      id: number;
      first_name: string;
      last_name: string;
      title: string | null;
      email: string | null;
      linkedin_url: string | null;
    }>;
  }> {
    return this.post(`/companies/${companyId}/findymail-find-dm-via-linkedin`, {
      target_titles: targetTitles,
      max_results: maxResults,
    });
  }

  /** Findymail enrichment: for every Person linked to this company without an
   * email, look up the address via Findymail (linkedin_url first, name+domain
   * fallback) and persist on Person. */
  async findymailEnrichDecisionMakers(companyId: number): Promise<{
    company_id: number;
    company_name: string;
    checked: number;
    enriched_count: number;
    skipped_no_email_found: number;
    people: Array<{
      id: number;
      first_name: string;
      last_name: string;
      title: string | null;
      email: string | null;
      linkedin_url: string | null;
    }>;
  }> {
    return this.post(`/companies/${companyId}/findymail-enrich-decision-makers`);
  }

  /** Find decision makers via Google -> LinkedIn (no LinkedIn auth — powered by
   * Claude's web_search). Persists matches as Person records linked to the company. */
  async findDecisionMakersViaLinkedIn(
    companyId: number,
    targetTitles: string[],
    maxResults: number = 5,
  ): Promise<{
    company_id: number;
    company_name: string;
    candidates_found: number;
    imported_count: number;
    people: Array<{
      id: number;
      first_name: string;
      last_name: string;
      title: string | null;
      linkedin_url: string;
      location: string | null;
    }>;
  }> {
    return this.post(`/companies/${companyId}/find-decision-makers-linkedin`, {
      target_titles: targetTitles,
      max_results: maxResults,
    });
  }

  async bulkTagCompanies(company_ids: number[], tags_to_add?: string[], tags_to_remove?: string[]): Promise<{ companies_tagged: number; message: string }> {
    return this.post("/companies/bulk-tag", { company_ids, tags_to_add, tags_to_remove });
  }

  async bulkDeleteCompanies(company_ids: number[]): Promise<{ deleted_count: number; message: string }> {
    return this.post("/companies/bulk-delete", company_ids);
  }

  async bulkExportCompanies(company_ids: number[]): Promise<Blob> {
    const response = await fetch(`${this.baseUrl}/api/companies/bulk-export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(company_ids),
    });
    if (!response.ok) throw new Error("Export failed");
    return response.blob();
  }

  // ============================================================================
  // Campaigns
  // ============================================================================

  async getCampaigns(params?: { icp_id?: number; search?: string; status?: string }): Promise<import("@/types").CampaignListResponse> {
    const query = new URLSearchParams();
    if (params?.icp_id) query.set("icp_id", String(params.icp_id));
    if (params?.search) query.set("search", params.search);
    if (params?.status) query.set("status", params.status);
    const queryString = query.toString();
    return this.get(`/campaigns${queryString ? `?${queryString}` : ''}`);
  }

  async getCampaign(campaignId: number): Promise<import("@/types").Campaign> {
    return this.get(`/campaigns/${campaignId}`);
  }

  async createCampaign(data: Record<string, unknown>): Promise<import("@/types").Campaign> {
    return this.post("/campaigns", data);
  }

  async updateCampaign(campaignId: number, data: Record<string, unknown>): Promise<import("@/types").Campaign> {
    return this.put(`/campaigns/${campaignId}`, data);
  }

  async deleteCampaign(campaignId: number): Promise<void> {
    await this.delete(`/campaigns/${campaignId}`);
  }

  async bulkDeleteCampaigns(campaignIds: number[]): Promise<{ deleted: number; instantly_deleted: number; errors: string[]; message: string }> {
    return this.post("/campaigns/bulk-delete", { campaign_ids: campaignIds });
  }

  async syncCampaigns(): Promise<import("@/types").InstantlySyncResponse> {
    return this.post("/campaigns/sync", {});
  }

  async syncAllCampaignMetrics(): Promise<{ synced: number; errors: number; total_campaigns: number; message: string }> {
    return this.post("/campaigns/sync-all-metrics", {});
  }

  async syncCampaignMetrics(campaignId: number): Promise<import("@/types").Campaign> {
    return this.post(`/campaigns/${campaignId}/sync-metrics`, {});
  }

  async activateCampaign(campaignId: number): Promise<import("@/types").Campaign> {
    return this.post(`/campaigns/${campaignId}/activate`, undefined);
  }

  async pauseCampaign(campaignId: number): Promise<import("@/types").Campaign> {
    return this.post(`/campaigns/${campaignId}/pause`, undefined);
  }

  async uploadLeadsToCampaign(campaignId: number, leadIds: number[]): Promise<import("@/types").LeadUploadResponse> {
    return this.post(`/campaigns/${campaignId}/upload-leads`, { lead_ids: leadIds });
  }

  async pushSequences(campaignId: number): Promise<import("@/types").PushSequencesResponse> {
    return this.post(`/campaigns/${campaignId}/push-sequences`, {});
  }
  async getInstantlyAccounts(): Promise<import("@/types").InstantlyEmailAccountListResponse> {
    return this.get("/campaigns/instantly/accounts");
  }

  async addListToCampaign(campaignId: number, leadListId: number): Promise<import("@/types").AddListToCampaignResponse> {
    return this.post(`/campaigns/${campaignId}/add-list`, { lead_list_id: leadListId });
  }

  async getCampaignLists(campaignId: number): Promise<{ campaign_id: number; lists: import("@/types").CampaignLeadListInfo[]; total: number }> {
    return this.get(`/campaigns/${campaignId}/lists`);
  }

  async removeListFromCampaign(campaignId: number, listId: number): Promise<void> {
    await this.delete(`/campaigns/${campaignId}/lists/${listId}`);
  }

  async syncLeadsFromInstantly(campaignId: number): Promise<import("@/types").LeadSyncResponse> {
    return this.post(`/campaigns/${campaignId}/sync-leads`, {});
  }

  async getCampaignDailyAnalytics(campaignId: number, startDate?: string, endDate?: string): Promise<Record<string, unknown>> {
    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    const query = params.toString() ? `?${params.toString()}` : "";
    return this.get(`/campaigns/${campaignId}/daily-analytics${query}`);
  }

  async getInstantlyAccount(email: string): Promise<import("@/types").InstantlyAccountDetails> {
    return this.get(`/campaigns/instantly/accounts/${encodeURIComponent(email)}`);
  }

  async updateInstantlyAccount(email: string, data: Record<string, unknown>): Promise<import("@/types").InstantlyAccountDetails> {
    const url = `/campaigns/instantly/accounts/${encodeURIComponent(email)}`;
    return this.request(url, { method: "PATCH", body: JSON.stringify(data) });
  }

  async manageInstantlyAccount(email: string, action: string): Promise<Record<string, unknown>> {
    return this.post(`/campaigns/instantly/accounts/${encodeURIComponent(email)}/${action}`, {});
  }

  async getWarmupAnalytics(email: string, startDate?: string, endDate?: string): Promise<import("@/types").WarmupAnalytics> {
    const params = new URLSearchParams();
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);
    const query = params.toString() ? `?${params.toString()}` : "";
    return this.get(`/campaigns/instantly/accounts/${encodeURIComponent(email)}/warmup-analytics${query}`);
  }

  // ============================================================================
  // Responses
  // ============================================================================

  async getResponses(params?: { campaign_id?: number; campaign_ids?: string; status?: string; sentiment?: string; date_from?: string; date_to?: string }): Promise<import("@/types").EmailResponseListResponse> {
    const query = new URLSearchParams();
    if (params?.campaign_id) query.set("campaign_id", String(params.campaign_id));
    if (params?.campaign_ids) query.set("campaign_ids", params.campaign_ids);
    if (params?.status) query.set("status", params.status);
    if (params?.sentiment) query.set("sentiment", params.sentiment);
    if (params?.date_from) query.set("date_from", params.date_from);
    if (params?.date_to) query.set("date_to", params.date_to);
    const queryString = query.toString();
    return this.get(`/responses${queryString ? `?${queryString}` : ''}`);
  }

  async fetchReplies(campaignIds: number[]): Promise<import("@/types").FetchRepliesResponse> {
    return this.post("/responses/fetch", { campaign_ids: campaignIds });
  }

  /** Fetch every message in the conversation thread anchored by `responseId`.
   * Messages are returned oldest-first. Used by the detail dialog to render
   * the full back-and-forth when a lead has replied multiple times. */
  async getResponseThread(responseId: number): Promise<import("@/types").EmailResponseListResponse> {
    return this.get(`/responses/${responseId}/thread`);
  }

  async getResponseStats(campaignIds: number[], dateFrom?: string, dateTo?: string): Promise<import("@/types").ResponseStats> {
    const params = new URLSearchParams({ campaign_ids: campaignIds.join(",") });
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    return this.get(`/responses/stats?${params}`);
  }
  async deleteResponse(responseId: number): Promise<void> {
    await this.delete(`/responses/${responseId}`);
  }

  async bulkDeleteResponses(ids: number[]): Promise<{ deleted: number }> {
    return this.post("/responses/bulk-delete", { ids });
  }

  // ============================================================================
  // Dashboard & Analytics
  // ============================================================================

  async getDashboardStats(): Promise<import("@/types").DashboardStats> {
    return this.get("/analytics/dashboard");
  }

  // ============================================================================
  // People & Companies
  // ============================================================================

  async getPeople(params?: { search?: string; industry?: string; client_tag?: string; skip?: number; limit?: number }): Promise<import("@/types").PersonListResponse> {
    const query = new URLSearchParams();
    if (params?.search) query.set("search", params.search);
    if (params?.industry) query.set("industry", params.industry);
    if (params?.client_tag) query.set("client_tag", params.client_tag);
    if (params?.skip) query.set("skip", String(params.skip));
    if (params?.limit) query.set("limit", String(params.limit));
    const queryString = query.toString();
    return this.get(`/people${queryString ? `?${queryString}` : ''}`);
  }

  async deletePerson(personId: number): Promise<void> {
    await this.delete(`/people/${personId}`);
  }

  async updatePerson(personId: number, data: import("@/types").PersonUpdate): Promise<import("@/types").Person> {
    return this.put(`/people/${personId}`, data);
  }

  async getPerson(personId: number): Promise<import("@/types").Person> {
    return this.get(`/people/${personId}`);
  }

  async getPeopleIndustries(): Promise<string[]> {
    return this.get("/people/industries");
  }

  async getClientTags(): Promise<string[]> {
    return this.get("/people/client-tags");
  }

  async getCompanies(params?: { search?: string; industry?: string; client_tag?: string; skip?: number; limit?: number }): Promise<import("@/types").CompanyListResponse> {
    const query = new URLSearchParams();
    if (params?.search) query.set("search", params.search);
    if (params?.industry) query.set("industry", params.industry);
    if (params?.client_tag) query.set("client_tag", params.client_tag);
    if (params?.skip) query.set("skip", String(params.skip));
    if (params?.limit) query.set("limit", String(params.limit));
    const queryString = query.toString();
    return this.get(`/companies${queryString ? `?${queryString}` : ''}`);
  }

  async deleteCompany(companyId: number): Promise<void> {
    await this.delete(`/companies/${companyId}`);
  }

  async updateCompany(companyId: number, data: import("@/types").CompanyUpdate): Promise<import("@/types").Company> {
    return this.put(`/companies/${companyId}`, data);
  }

  /** Quick-create a Person record linked directly to a company (used by the
   * Clay table's "+ Nuovo DM" affordance on the Decision Makers cell). */
  async createCompanyPerson(
    companyId: number,
    data: { first_name: string; last_name: string; email?: string | null; title?: string | null; linkedin_url?: string | null; phone?: string | null },
  ): Promise<{
    id: number;
    first_name: string;
    last_name: string;
    email: string | null;
    title: string | null;
    linkedin_url: string | null;
    phone: string | null;
    company_id: number;
  }> {
    return this.post(`/companies/${companyId}/people`, data);
  }

  async getCompany(companyId: number): Promise<import("@/types").Company> {
    return this.get(`/companies/${companyId}`);
  }
  async saveScrapedDataToCompany(
    companyId: number,
    data: { emails: string[]; linkedin_url?: string | null; phone?: string | null },
  ): Promise<import("@/types").Company> {
    return this.post(`/companies/${companyId}/save-scraped`, data);
  }

  async pushCompanyDecisionMakersToCampaign(
    companyId: number,
    campaignId: number,
  ): Promise<{ company_id: number; campaign_id: number; uploaded: number; campaign_name: string }> {
    return this.post(`/companies/${companyId}/push-to-campaign`, { campaign_id: campaignId });
  }

  async upsertCompanyCustomField(
    companyId: number,
    key: string,
    value: string | null,
  ): Promise<import("@/types").Company> {
    return this.put(`/companies/${companyId}/custom-field`, { key, value });
  }

  async listCustomFieldKeys(): Promise<string[]> {
    return this.get("/companies/custom-field-keys");
  }

  async listActivity(params: {
    target_type?: "account" | "contact";
    target_id?: number;
    action?: string;
    actor?: string;
    page?: number;
    page_size?: number;
  }): Promise<{
    activities: Array<{
      id: number;
      target_type: string;
      target_id: number;
      action: string;
      payload: Record<string, unknown> | null;
      actor: string | null;
      created_at: string;
    }>;
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
  }> {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
    });
    const qs = q.toString();
    return this.get(`/activity${qs ? `?${qs}` : ""}`);
  }

  async getCompaniesFiltered(
    filters: import("@/types").CompanyFilters & { page?: number; page_size?: number },
  ): Promise<import("@/types").CompanyListResponse> {
    const qs = this._encodeCompanyFilterQuery(filters);
    return this.get(`/companies${qs ? `?${qs}` : ""}`);
  }

  async getCompanyIdsFiltered(filters: import("@/types").CompanyFilters): Promise<number[]> {
    const qs = this._encodeCompanyFilterQuery(filters);
    return this.get(`/companies/ids${qs ? `?${qs}` : ""}`);
  }

  private _encodeCompanyFilterQuery(filters: import("@/types").CompanyFilters & { page?: number; page_size?: number }): string {
    const q = new URLSearchParams();
    const advanced: Record<string, unknown> = {};
    Object.entries(filters).forEach(([k, v]) => {
      if (v === undefined || v === null || v === "") return;
      if (k === "cf" || k === "name_contains") {
        advanced[k] = v;
        return;
      }
      q.set(k, String(v));
    });
    if (Object.keys(advanced).length > 0) {
      q.set("filters", JSON.stringify(advanced));
    }
    return q.toString();
  }

  async addCompaniesToList(listId: number, companyIds: number[]): Promise<{ companies_affected: number; message: string }> {
    return this.post(`/lead-lists/${listId}/companies/add`, { company_ids: companyIds });
  }

  async removeCompaniesFromList(listId: number, companyIds: number[]): Promise<{ companies_affected: number; message: string }> {
    return this.post(`/lead-lists/${listId}/companies/remove`, { company_ids: companyIds });
  }

  async listLeadLists(): Promise<{ lists: import("@/types").LeadList[]; total: number }> {
    return this.get("/lead-lists");
  }
  async getCompanyDetail(companyId: number): Promise<import("@/types").CompanyDetailResponse> {
    return this.get(`/companies/${companyId}/detail`);
  }

  async getCompanyCampaigns(companyId: number): Promise<{ campaigns: import("@/types").CampaignSummary[] }> {
    return this.get(`/companies/${companyId}/campaigns`);
  }

  async getPersonCampaigns(personId: number): Promise<{ campaigns: import("@/types").CampaignSummary[] }> {
    return this.get(`/people/${personId}/campaigns`);
  }

  async getCompanyIndustries(): Promise<string[]> {
    return this.get("/companies/industries");
  }

  // --- Prospecting (Apollo Search People) ---

  async toolsSearchPeople(params: import("@/types").ApolloSearchPeopleParams): Promise<import("@/types").ToolSearchResponse> {
    return this.post("/tools/apollo/search-people", params);
  }

  async toolsImportLeads(params: import("@/types").ImportLeadsParams): Promise<import("@/types").ImportLeadsResponse> {
    return this.post("/tools/import-leads", params);
  }

  // --- Native website scraper ---

  async scrapeWebsite(url: string): Promise<import("@/types").WebsiteScrapeResult> {
    return this.post("/scraper/scrape", { url });
  }

  async scrapeWebsitesBulk(urls: string[], concurrency = 5): Promise<import("@/types").WebsiteScrapeResult[]> {
    return this.post("/scraper/scrape-bulk", { urls, concurrency });
  }
}

export const api = new ApiClient(API_BASE_URL);
