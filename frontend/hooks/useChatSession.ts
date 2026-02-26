import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import type {
  ChatSession,
  ChatMessageModel,
  SessionSummary,
  CreateSessionRequest,
} from "@/types";

export interface ApolloResultsData {
  results: Record<string, unknown>[];
  total: number;
  search_type: string;
  returned: number;
  search_params: Record<string, unknown>;
}

interface ChatSessionContext {
  sessionUuid: string | null;
  messages: ChatMessageModel[];
  currentIcp: Record<string, unknown> | null;
  lastSearchResults: {
    type: string;
    count: number;
    company_ids: number[];
  } | null;
  sessionStats: {
    totalCost: number;
    messageCount: number;
    apolloCredits: number;
  };
  isLoading: boolean;
  isStreaming: boolean;
  currentToolExecution: {
    tool: string;
    input: Record<string, unknown>;
  } | null;
  apolloResults: ApolloResultsData | null;
  apolloSearching: boolean;
}

interface UseChatSessionReturn {
  context: ChatSessionContext | null;
  sendMessage: (message: string, fileContent?: string, mode?: string) => Promise<void>;
  refreshSession: () => Promise<void>;
  createNewSession: (request?: CreateSessionRequest) => Promise<string>;
  error: Error | null;
  onApolloResultsCallback: React.MutableRefObject<((data: ApolloResultsData) => void) | null>;
}

export function useChatSession(initialSessionUuid?: string): UseChatSessionReturn {
  const [context, setContext] = useState<ChatSessionContext | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const onApolloResultsCallback = useRef<((data: ApolloResultsData) => void) | null>(null);

  const loadSession = useCallback(async (sessionUuid: string) => {
    try {
      setError(null);
      setContext((prev) => prev ? { ...prev, isLoading: true } : null);

      const data = await api.getChatSession(sessionUuid);

      const session = data.session as ChatSession;
      const messages = data.messages as ChatMessageModel[];
      const summary = data.summary as SessionSummary;

      // Extract last search results from session metadata
      const lastSearchResults = session.session_metadata?.last_apollo_search
        ? {
            type: (session.session_metadata.last_apollo_search as Record<string, unknown>).type as string,
            count: (session.session_metadata.last_apollo_search as Record<string, unknown>).count as number,
            company_ids: (session.session_metadata.last_apollo_search as Record<string, unknown>).company_ids as number[],
          }
        : null;

      setContext((prev) => ({
        sessionUuid: session.session_uuid,
        messages,
        currentIcp: session.current_icp_draft,
        lastSearchResults,
        sessionStats: {
          totalCost: session.total_cost_usd,
          messageCount: summary.message_count,
          apolloCredits: session.total_apollo_credits,
        },
        isLoading: false,
        isStreaming: false,
        currentToolExecution: null,
        apolloResults: prev?.apolloResults ?? null,
        apolloSearching: false,
      }));
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setContext((prev) => prev ? { ...prev, isLoading: false } : null);
    }
  }, []);

  const createNewSession = useCallback(async (request?: CreateSessionRequest) => {
    try {
      setError(null);
      const sessionResponse = await api.createChatSession(request || {});

      setContext({
        sessionUuid: sessionResponse.session_uuid,
        messages: [],
        currentIcp: null,
        lastSearchResults: null,
        sessionStats: {
          totalCost: 0,
          messageCount: 0,
          apolloCredits: 0,
        },
        isLoading: false,
        isStreaming: false,
        currentToolExecution: null,
        apolloResults: null,
        apolloSearching: false,
      });

      return sessionResponse.session_uuid;
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      throw err;
    }
  }, []);

  const sendMessage = useCallback(
    async (message: string, fileContent?: string, mode?: string) => {
      if (!context?.sessionUuid) {
        throw new Error("No active session");
      }

      // Abort any existing streaming
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();

      try {
        setError(null);

        // Add user message optimistically
        const userMessage: ChatMessageModel = {
          id: Date.now(), // Temporary ID
          session_id: -1,
          role: "user",
          content: message,
          tool_calls: null,
          tool_results: null,
          input_tokens: 0,
          output_tokens: 0,
          message_metadata: fileContent ? { has_file_attachment: true } : null,
          created_at: new Date().toISOString(),
        };

        setContext((prev) =>
          prev
            ? {
                ...prev,
                messages: [...prev.messages, userMessage],
                isStreaming: true,
                currentToolExecution: null,
              }
            : null
        );

        // Accumulate assistant response
        let assistantContent = "";

        await api.streamChatSession(
          context.sessionUuid,
          message,
          fileContent || null,
          // onText
          (text: string) => {
            assistantContent += text;
            setContext((prev) => {
              if (!prev) return null;

              const messages = [...prev.messages];
              const lastMessage = messages[messages.length - 1];

              if (lastMessage && lastMessage.role === "assistant") {
                // Update existing assistant message
                lastMessage.content = assistantContent;
              } else {
                // Add new assistant message
                messages.push({
                  id: Date.now() + 1,
                  session_id: -1,
                  role: "assistant",
                  content: assistantContent,
                  tool_calls: null,
                  tool_results: null,
                  input_tokens: 0,
                  output_tokens: 0,
                  message_metadata: null,
                  created_at: new Date().toISOString(),
                });
              }

              return { ...prev, messages };
            });
          },
          // onToolStart
          (tool: string, input: Record<string, unknown>) => {
            setContext((prev) =>
              prev
                ? {
                    ...prev,
                    currentToolExecution: { tool, input },
                    apolloSearching: tool === "search_apollo" ? true : prev.apolloSearching,
                  }
                : null
            );
          },
          // onToolComplete
          (tool: string, summary: Record<string, unknown>) => {
            console.log(`Tool ${tool} completed:`, summary);
            setContext((prev) =>
              prev
                ? {
                    ...prev,
                    currentToolExecution: null,
                    apolloSearching: tool === "search_apollo" ? false : prev.apolloSearching,
                  }
                : null
            );
          },
          // onDone
          () => {
            setContext((prev) =>
              prev
                ? {
                    ...prev,
                    isStreaming: false,
                    currentToolExecution: null,
                    apolloSearching: false,
                  }
                : null
            );

            // Reload session to get updated metadata and stats
            if (context.sessionUuid) {
              loadSession(context.sessionUuid);
            }
          },
          // onError
          (err: Error) => {
            setError(err);
            setContext((prev) =>
              prev
                ? {
                    ...prev,
                    isStreaming: false,
                    currentToolExecution: null,
                    apolloSearching: false,
                  }
                : null
            );
          },
          // options
          {
            mode,
            onApolloResults: (data) => {
              setContext((prev) =>
                prev
                  ? { ...prev, apolloResults: data, apolloSearching: false }
                  : null
              );
              // Call external callback (used by prospecting page)
              onApolloResultsCallback.current?.(data);
            },
          }
        );
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
        setContext((prev) =>
          prev
            ? {
                ...prev,
                isStreaming: false,
                currentToolExecution: null,
                apolloSearching: false,
              }
            : null
        );
      }
    },
    [context?.sessionUuid, loadSession]
  );

  const refreshSession = useCallback(async () => {
    if (context?.sessionUuid) {
      await loadSession(context.sessionUuid);
    }
  }, [context?.sessionUuid, loadSession]);

  // Load session on mount
  useEffect(() => {
    if (initialSessionUuid) {
      loadSession(initialSessionUuid);
    }
  }, [initialSessionUuid, loadSession]);

  return {
    context,
    sendMessage,
    refreshSession,
    createNewSession,
    error,
    onApolloResultsCallback,
  };
}
