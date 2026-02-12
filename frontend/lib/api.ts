const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
      throw new Error(`API error: ${response.status} ${response.statusText}`);
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
    onError: (error: Error) => void
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
}

export const api = new ApiClient(API_BASE_URL);
