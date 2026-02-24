const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

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
    claude_tokens?: {
      input_tokens: number;
      output_tokens: number;
      total_tokens: number;
    };
  }): Promise<import("@/types").ApolloSearchResponse> {
    return this.post("/chat/apollo/search", params);
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

  async streamChatSession(
    sessionUuid: string,
    message: string,
    fileContent: string | null,
    onText: (text: string) => void,
    onToolStart: (tool: string, input: Record<string, unknown>) => void,
    onToolComplete: (tool: string, summary: Record<string, unknown>) => void,
    onDone: () => void,
    onError: (error: Error) => void
  ): Promise<void> {
    const url = `${this.baseUrl}/api/chat/sessions/${sessionUuid}/stream`;
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, file_content: fileContent }),
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
    return this.fetch("/ai-agents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
  }

  async getAIAgents(params?: { is_active?: boolean; skip?: number; limit?: number }): Promise<{ agents: import("@/types").AIAgent[]; total: number }> {
    const query = new URLSearchParams();
    if (params?.is_active !== undefined) query.set("is_active", String(params.is_active));
    if (params?.skip) query.set("skip", String(params.skip));
    if (params?.limit) query.set("limit", String(params.limit));

    return this.fetch(`/ai-agents?${query}`);
  }

  async getAIAgent(id: number): Promise<import("@/types").AIAgent> {
    return this.fetch(`/ai-agents/${id}`);
  }

  async updateAIAgent(id: number, data: import("@/types").AIAgentUpdate): Promise<import("@/types").AIAgent> {
    return this.fetch(`/ai-agents/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
  }

  async deleteAIAgent(id: number): Promise<void> {
    await this.fetch(`/ai-agents/${id}`, { method: "DELETE" });
  }

  async uploadKnowledgeBase(id: number, data: { source_type: string; content: string; files_metadata?: any[] }): Promise<import("@/types").AIAgent> {
    return this.fetch(`/ai-agents/${id}/knowledge-base`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
  }

  async executeApolloSearch(id: number, params: import("@/types").AIAgentApolloSearchRequest): Promise<import("@/types").ApolloSearchResult> {
    return this.fetch(`/ai-agents/${id}/search-apollo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
  }

  async estimateEnrichCost(id: number, person_ids?: number[], company_ids?: number[]): Promise<import("@/types").EnrichEstimate> {
    return this.fetch(`/ai-agents/${id}/estimate-enrich`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ person_ids, company_ids }),
    });
  }

  async enrichLeads(id: number, person_ids?: number[], company_ids?: number[]): Promise<{ enriched_count: number; credits_consumed: number; credits_remaining: number }> {
    return this.fetch(`/ai-agents/${id}/enrich-leads`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ person_ids, company_ids }),
    });
  }

  async getAIAgentStats(id: number): Promise<import("@/types").AIAgentStats> {
    return this.fetch(`/ai-agents/${id}/stats`);
  }

  // ============================================================================
  // Lead Lists
  // ============================================================================

  async createLeadList(data: import("@/types").LeadListCreate): Promise<import("@/types").LeadList> {
    return this.fetch("/lead-lists", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
  }

  async getLeadLists(params?: { ai_agent_id?: number; skip?: number; limit?: number }): Promise<{ lists: import("@/types").LeadList[]; total: number }> {
    const query = new URLSearchParams();
    if (params?.ai_agent_id) query.set("ai_agent_id", String(params.ai_agent_id));
    if (params?.skip) query.set("skip", String(params.skip));
    if (params?.limit) query.set("limit", String(params.limit));

    return this.fetch(`/lead-lists?${query}`);
  }

  async getLeadList(id: number): Promise<import("@/types").LeadList> {
    return this.fetch(`/lead-lists/${id}`);
  }

  async updateLeadList(id: number, data: { name?: string; description?: string }): Promise<import("@/types").LeadList> {
    return this.fetch(`/lead-lists/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
  }

  async deleteLeadList(id: number): Promise<void> {
    await this.fetch(`/lead-lists/${id}`, { method: "DELETE" });
  }

  async exportLeadList(id: number): Promise<Blob> {
    const response = await fetch(`${this.baseURL}/lead-lists/${id}/export`);
    if (!response.ok) throw new Error("Export failed");
    return response.blob();
  }

  // ============================================================================
  // Bulk Operations
  // ============================================================================

  async bulkEnrichPeople(person_ids: number[]): Promise<{ enriched_count: number; credits_consumed: number; message: string }> {
    return this.fetch("/people/bulk-enrich", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(person_ids),
    });
  }

  async bulkTagPeople(person_ids: number[], tags_to_add?: string[], tags_to_remove?: string[]): Promise<{ people_tagged: number; message: string }> {
    return this.fetch("/people/bulk-tag", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ person_ids, tags_to_add, tags_to_remove }),
    });
  }

  async bulkDeletePeople(person_ids: number[]): Promise<{ deleted_count: number; message: string }> {
    return this.fetch("/people/bulk-delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(person_ids),
    });
  }

  async bulkExportPeople(person_ids: number[]): Promise<Blob> {
    const response = await fetch(`${this.baseURL}/people/bulk-export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(person_ids),
    });
    if (!response.ok) throw new Error("Export failed");
    return response.blob();
  }

  async bulkTagCompanies(company_ids: number[], tags_to_add?: string[], tags_to_remove?: string[]): Promise<{ companies_tagged: number; message: string }> {
    return this.fetch("/companies/bulk-tag", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ company_ids, tags_to_add, tags_to_remove }),
    });
  }

  async bulkDeleteCompanies(company_ids: number[]): Promise<{ deleted_count: number; message: string }> {
    return this.fetch("/companies/bulk-delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(company_ids),
    });
  }

  async bulkExportCompanies(company_ids: number[]): Promise<Blob> {
    const response = await fetch(`${this.baseURL}/companies/bulk-export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(company_ids),
    });
    if (!response.ok) throw new Error("Export failed");
    return response.blob();
  }

  // ============================================================================
  // AI Replies
  // ============================================================================

  async generateAIReply(responseId: number, aiAgentId?: number): Promise<{ subject: string; body: string; tone: string; call_to_action: string }> {
    return this.fetch(`/responses/${responseId}/generate-ai-reply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ai_agent_id: aiAgentId }),
    });
  }

  async approveAndSendReply(responseId: number, approved_body: string, approved_subject?: string, sender_email?: string): Promise<{ status: string; message: string }> {
    return this.fetch(`/responses/${responseId}/approve-and-send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved_body, approved_subject, sender_email }),
    });
  }

  async ignoreResponse(responseId: number): Promise<{ status: string; message: string }> {
    return this.fetch(`/responses/${responseId}/ignore`, {
      method: "POST",
    });
  }
}

export const api = new ApiClient(API_BASE_URL);
