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

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: "DELETE" });
  }

  async healthCheck(): Promise<{ status: string; version: string }> {
    const response = await fetch(`${this.baseUrl}/health`);
    return response.json();
  }

  async streamChat(
    messages: { role: string; content: string }[],
    fileContent: string | null,
    onText: (text: string) => void,
    onIcpExtracted: (data: Record<string, string>) => void,
    onDone: () => void,
    onError: (error: Error) => void,
    onApolloSearchParams?: (event: { data: Record<string, unknown>; claude_tokens?: { input_tokens: number; output_tokens: number; total_tokens: number } }) => void
  ): Promise<void> {
    const url = `${this.baseUrl}/api/chat/stream`;
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages, file_content: fileContent }),
      });

      if (!response.ok) {
        throw new Error(`Chat error: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const parsed = JSON.parse(line.slice(6));
              if (parsed.type === "text") onText(parsed.content);
              else if (parsed.type === "icp_extracted") onIcpExtracted(parsed.data);
              else if (parsed.type === "apollo_search_params") onApolloSearchParams?.(parsed);
              else if (parsed.type === "done") onDone();
              else if (parsed.type === "error") onError(new Error(parsed.content));
            } catch {
              // Skip malformed SSE lines
            }
          }
        }
      }
    } catch (err) {
      onError(err instanceof Error ? err : new Error(String(err)));
    }
  }

  async apolloSearch(params: {
    search_type: "people" | "companies";
    filters: Record<string, unknown>;
    per_page?: number;
    client_tag?: string;
    auto_enrich?: boolean;
    claude_tokens?: {
      input_tokens: number;
      output_tokens: number;
      total_tokens: number;
    };
  }): Promise<import("@/types").ApolloSearchResponse> {
    return this.post("/chat/apollo/search", params);
  }

  async apolloEnrichPeople(people: Record<string, unknown>[], source: "apollo" | "apify" = "apollo"): Promise<import("@/types").ApolloEnrichResponse> {
    return this.post("/chat/apollo/enrich", { people, source });
  }

  async apolloImport(
    results: Record<string, unknown>[],
    target: "people" | "companies",
    client_tag?: string,
    auto_enrich?: boolean
  ): Promise<import("@/types").ApolloImportResponse> {
    return this.post("/chat/apollo/import", { results, target, client_tag, auto_enrich });
  }

  async uploadFile(file: File): Promise<{ filename: string; text: string; length: number }> {
    const formData = new FormData();
    formData.append("file", file);
    const url = `${this.baseUrl}/api/chat/upload`;
    const response = await fetch(url, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) throw new Error(`Upload error: ${response.status}`);
    return response.json();
  }

  async uploadCSV(file: File): Promise<import("@/types").CSVUploadResponse> {
    const formData = new FormData();
    formData.append("file", file);
    const url = `${this.baseUrl}/api/leads/csv/upload`;
    const response = await fetch(url, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Upload error: ${response.status}`);
    }
    return response.json();
  }

  async uploadPeopleCSV(file: File): Promise<import("@/types").PersonCSVUploadResponse> {
    const formData = new FormData();
    formData.append("file", file);
    const url = `${this.baseUrl}/api/people/csv/upload`;
    const response = await fetch(url, { method: "POST", body: formData });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Upload error: ${response.status}`);
    }
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

  // === Session-based Conversational Chat ===

  async createChatSession(
    request: import("@/types").CreateSessionRequest
  ): Promise<import("@/types").SessionResponse> {
    return this.post(`/chat/sessions`, request);
  }

  async getChatSession(sessionUuid: string): Promise<import("@/types").SessionWithMessages> {
    return this.get(`/chat/sessions/${sessionUuid}`);
  }

  async listChatSessions(
    clientTag?: string,
    status?: string,
    limit = 50,
    offset = 0
  ): Promise<import("@/types").SessionListResponse> {
    const params = new URLSearchParams();
    if (clientTag) params.append("client_tag", clientTag);
    if (status) params.append("status", status);
    params.append("limit", limit.toString());
    params.append("offset", offset.toString());
    const query = params.toString() ? `?${params.toString()}` : "";
    return this.get(`/chat/sessions${query}`);
  }

  async archiveChatSession(sessionUuid: string): Promise<{ status: string; session_uuid: string }> {
    return this.delete(`/chat/sessions/${sessionUuid}`);
  }

  async saveSearchContext(
    sessionUuid: string,
    data: { search_type: string; total: number; returned: number; filters: Record<string, unknown> }
  ): Promise<void> {
    await this.post(`/chat/sessions/${sessionUuid}/search-context`, data);
  }

  async streamChatSession(
    sessionUuid: string,
    message: string,
    fileContent: string | null,
    onText: (text: string) => void,
    onToolStart: (tool: string, input: Record<string, unknown>) => void,
    onToolComplete: (tool: string, summary: Record<string, unknown>) => void,
    onDone: () => void,
    onError: (error: Error) => void,
    options?: {
      mode?: string;
      onApolloResults?: (data: { results: Record<string, unknown>[]; total: number; search_type: string; returned: number; search_params: Record<string, unknown> }) => void;
    }
  ): Promise<void> {
    const url = `${this.baseUrl}/api/chat/sessions/${sessionUuid}/stream`;
    try {
      const body: Record<string, unknown> = { message, file_content: fileContent };
      if (options?.mode) body.mode = options.mode;

      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        throw new Error(`Chat error: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim() || !line.startsWith("data: ")) continue;

          try {
            const data = JSON.parse(line.substring(6));

            if (data.type === "text") {
              onText(data.content);
            } else if (data.type === "tool_start") {
              onToolStart(data.tool, data.input);
            } else if (data.type === "tool_complete") {
              onToolComplete(data.tool, data.summary);
            } else if (data.type === "apollo_results") {
              options?.onApolloResults?.(data.data);
            } else if (data.type === "done") {
              onDone();
            } else if (data.type === "error") {
              onError(new Error(data.message || data.error));
            }
          } catch (err) {
            console.error("Failed to parse SSE event:", line, err);
          }
        }
      }
    } catch (err) {
      onError(err instanceof Error ? err : new Error(String(err)));
    }
  }

  // ============================================================================
  // AI Agents
  // ============================================================================

  async createAIAgent(data: import("@/types").AIAgentCreate): Promise<import("@/types").AIAgent> {
    return this.post("/ai-agents", data);
  }

  async getAIAgents(params?: { is_active?: boolean; skip?: number; limit?: number }): Promise<{ agents: import("@/types").AIAgent[]; total: number }> {
    const query = new URLSearchParams();
    if (params?.is_active !== undefined) query.set("is_active", String(params.is_active));
    if (params?.skip) query.set("skip", String(params.skip));
    if (params?.limit) query.set("limit", String(params.limit));
    const queryString = query.toString();
    return this.get(`/ai-agents${queryString ? `?${queryString}` : ''}`);
  }

  async getAIAgent(id: number): Promise<import("@/types").AIAgent> {
    return this.get(`/ai-agents/${id}`);
  }

  async updateAIAgent(id: number, data: import("@/types").AIAgentUpdate): Promise<import("@/types").AIAgent> {
    return this.put(`/ai-agents/${id}`, data);
  }

  async deleteAIAgent(id: number): Promise<void> {
    await this.delete(`/ai-agents/${id}`);
  }

  async uploadKnowledgeBase(id: number, data: { source_type: string; content: string; files_metadata?: any[] }): Promise<import("@/types").AIAgent> {
    return this.post(`/ai-agents/${id}/knowledge-base`, data);
  }

  async executeApolloSearch(id: number, params: import("@/types").AIAgentApolloSearchRequest): Promise<import("@/types").ApolloSearchResult> {
    return this.post(`/ai-agents/${id}/search-apollo`, params);
  }

  async estimateEnrichCost(id: number, person_ids?: number[], company_ids?: number[]): Promise<import("@/types").EnrichEstimate> {
    return this.post(`/ai-agents/${id}/estimate-enrich`, { person_ids, company_ids });
  }

  async enrichLeads(id: number, person_ids?: number[], company_ids?: number[]): Promise<{ enriched_count: number; credits_consumed: number; credits_remaining: number }> {
    return this.post(`/ai-agents/${id}/enrich-leads`, { person_ids, company_ids });
  }

  async getAIAgentStats(id: number): Promise<import("@/types").AIAgentStats> {
    return this.get(`/ai-agents/${id}/stats`);
  }

  async getAssociatedCampaigns(agentId: number): Promise<{ campaigns: any[]; total: number }> {
    return this.get(`/ai-agents/${agentId}/campaigns`);
  }

  async associateCampaigns(agentId: number, campaignIds: number[]): Promise<{ campaigns_associated: number; message: string }> {
    return this.post(`/ai-agents/${agentId}/campaigns`, { campaign_ids: campaignIds });
  }

  async disassociateCampaign(agentId: number, campaignId: number): Promise<void> {
    await this.delete(`/ai-agents/${agentId}/campaigns/${campaignId}`);
  }

  // ============================================================================
  // Lead Lists
  // ============================================================================

  async createLeadList(data: import("@/types").LeadListCreate): Promise<import("@/types").LeadList> {
    return this.post("/lead-lists", data);
  }

  async getLeadLists(params?: { ai_agent_id?: number; skip?: number; limit?: number }): Promise<{ lists: import("@/types").LeadList[]; total: number }> {
    const query = new URLSearchParams();
    if (params?.ai_agent_id) query.set("ai_agent_id", String(params.ai_agent_id));
    if (params?.skip) query.set("skip", String(params.skip));
    if (params?.limit) query.set("limit", String(params.limit));
    const queryString = query.toString();
    return this.get(`/lead-lists${queryString ? `?${queryString}` : ''}`);
  }

  async getLeadList(id: number): Promise<import("@/types").LeadList> {
    return this.get(`/lead-lists/${id}`);
  }

  async updateLeadList(id: number, data: { name?: string; description?: string }): Promise<import("@/types").LeadList> {
    return this.put(`/lead-lists/${id}`, data);
  }

  async deleteLeadList(id: number): Promise<void> {
    await this.delete(`/lead-lists/${id}`);
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

  async generateTemplates(campaignId: number, data: { icp_id?: number; additional_context?: string; num_subject_lines?: number; num_steps?: number }): Promise<import("@/types").EmailTemplateGenerateResponse> {
    return this.post(`/campaigns/${campaignId}/generate-templates`, data);
  }

  async getInstantlyAccounts(): Promise<import("@/types").InstantlyEmailAccountListResponse> {
    return this.get("/campaigns/instantly/accounts");
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

  async generateReply(responseId: number): Promise<import("@/types").EmailResponseWithDetails> {
    return this.post(`/responses/${responseId}/generate-reply`);
  }

  async approveReply(responseId: number, editedReply?: string): Promise<import("@/types").EmailResponseWithDetails> {
    return this.post(`/responses/${responseId}/approve`, { edited_reply: editedReply });
  }

  async sendReply(responseId: number): Promise<import("@/types").SendReplyResponse> {
    return this.post(`/responses/${responseId}/send`);
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

  async getPeopleIndustries(): Promise<string[]> {
    return this.get("/people/industries");
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

  async getCompanyIndustries(): Promise<string[]> {
    return this.get("/companies/industries");
  }

  // ============================================================================
  // AI Replies
  // ============================================================================

  async generateAIReply(responseId: number, aiAgentId?: number): Promise<{ subject: string; body: string; tone: string; call_to_action: string }> {
    return this.post(`/responses/${responseId}/generate-ai-reply`, { ai_agent_id: aiAgentId });
  }

  async approveAndSendReply(responseId: number, approved_body: string, approved_subject?: string, sender_email?: string): Promise<{ status: string; message: string }> {
    return this.post(`/responses/${responseId}/approve-and-send`, { approved_body, approved_subject, sender_email });
  }

  async ignoreResponse(responseId: number): Promise<{ status: string; message: string }> {
    return this.post(`/responses/${responseId}/ignore`, undefined);
  }
}

export const api = new ApiClient(API_BASE_URL);
