"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Search, Loader2, Plus, MessageSquare, Tag } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageBubble } from "@/components/chat/message-bubble";
import { ChatInput } from "@/components/chat/chat-input";
import { ApolloSearchForm, ApolloFormFilters } from "@/components/chat/apollo-search-form";
import { ApolloPreviewCard } from "@/components/chat/apollo-preview-card";
import { useChatSession, ApolloResultsData } from "@/hooks/useChatSession";
import { api } from "@/lib/api";
import { ApolloSearchResponse } from "@/types";

export default function ProspectingPage() {
  const { context, sendMessage, createNewSession, error, onApolloResultsCallback } =
    useChatSession();

  // Session client tag (for cost tracking per client)
  const [sessionClientTag, setSessionClientTag] = useState("");
  const clientTagTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Left panel state
  const [apolloResults, setApolloResults] = useState<ApolloSearchResponse | null>(null);
  const [apolloSearching, setApolloSearching] = useState(false);
  const [currentClientTag, setCurrentClientTag] = useState<string | undefined>();
  const [currentAutoEnrich, setCurrentAutoEnrich] = useState(false);
  const [formFilters, setFormFilters] = useState<Partial<ApolloFormFilters> | undefined>();

  // Chat state
  const [chatInput, setChatInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [context?.messages, scrollToBottom]);

  // Auto-create session on mount
  useEffect(() => {
    if (!context) {
      createNewSession({
        title: "Prospecting Session",
        client_tag: sessionClientTag || undefined,
      });
    }
  }, [context, createNewSession]); // eslint-disable-line react-hooks/exhaustive-deps

  // Debounced update of session client_tag on the server
  const handleClientTagChange = useCallback(
    (value: string) => {
      setSessionClientTag(value);
      setCurrentClientTag(value || undefined);

      // Debounce the API call (wait 800ms after user stops typing)
      if (clientTagTimerRef.current) {
        clearTimeout(clientTagTimerRef.current);
      }
      clientTagTimerRef.current = setTimeout(() => {
        if (context?.sessionUuid) {
          api.updateChatSession(context.sessionUuid, {
            client_tag: value || undefined,
          }).catch(console.error);
        }
      }, 800);
    },
    [context?.sessionUuid]
  );

  // Wire up apollo results callback from chat SSE
  useEffect(() => {
    onApolloResultsCallback.current = (data: ApolloResultsData) => {
      // Convert SSE data to ApolloSearchResponse format
      setApolloResults({
        results: data.results as unknown as ApolloSearchResponse["results"],
        total: data.total,
        search_type: data.search_type as "people" | "companies",
        returned: data.returned,
        credits_consumed: 0,
      });
      // Update form filters from chat search params
      if (data.search_params) {
        setFormFilters(data.search_params as Partial<ApolloFormFilters>);
      }
      setApolloSearching(false);
    };
  }, [onApolloResultsCallback]);

  // Form search handler (left panel)
  const handleFormSearch = useCallback(
    async (filters: ApolloFormFilters) => {
      setApolloSearching(true);
      setApolloResults(null);
      setCurrentAutoEnrich(filters.auto_enrich || false);

      // Sync client_tag from form to session
      if (filters.client_tag) {
        setSessionClientTag(filters.client_tag);
        setCurrentClientTag(filters.client_tag);
        if (context?.sessionUuid) {
          api.updateChatSession(context.sessionUuid, {
            client_tag: filters.client_tag,
          }).catch(console.error);
        }
      }

      try {
        const { search_type, per_page, client_tag, auto_enrich, ...rest } = filters;
        const result = await api.apolloSearch({
          search_type,
          filters: rest as Record<string, unknown>,
          per_page,
          client_tag,
          auto_enrich,
        });
        setApolloResults(result);

        // Send search context to chat session so AI knows what was searched
        if (context?.sessionUuid) {
          api.saveSearchContext(context.sessionUuid, {
            search_type,
            total: result.total,
            returned: result.returned,
            filters: rest as Record<string, unknown>,
          }).catch(console.error);
        }
      } catch (err) {
        console.error("Apollo search error:", err);
      } finally {
        setApolloSearching(false);
      }
    },
    [context?.sessionUuid]
  );

  // Chat send handler (right panel)
  const handleChatSend = async () => {
    const trimmed = chatInput.trim();
    if (!trimmed || context?.isStreaming) return;

    setChatInput("");
    try {
      await sendMessage(trimmed, undefined, "prospecting");
    } catch (err) {
      console.error("Send message error:", err);
    }
  };

  // New session handler
  const handleNewSession = async () => {
    setApolloResults(null);
    setFormFilters(undefined);
    await createNewSession({
      title: "Prospecting Session",
      client_tag: sessionClientTag || undefined,
    });
  };

  if (!context && !error) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-48px)]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-48px)]">
      {/* Header */}
      <div className="flex items-center justify-between px-1 pb-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Search className="h-6 w-6" />
            Prospecting
          </h1>
          <p className="text-sm text-muted-foreground">
            Search with the form, refine with AI chat
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <Tag className="h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Client / Project tag..."
              value={sessionClientTag}
              onChange={(e) => handleClientTagChange(e.target.value)}
              className="h-8 w-[200px] text-sm"
            />
          </div>
          <Button variant="outline" size="sm" onClick={handleNewSession} className="gap-1.5">
            <Plus className="h-4 w-4" />
            New Session
          </Button>
        </div>
      </div>

      {/* Split View */}
      <div className="flex-1 flex gap-4 min-h-0">
        {/* LEFT PANEL: Form + Results (60%) */}
        <div className="w-[60%] flex flex-col min-h-0 gap-4">
          {/* Search Form (collapsible) */}
          <div className="flex-shrink-0">
            <ApolloSearchForm
              onSearch={handleFormSearch}
              loading={apolloSearching}
              initialFilters={formFilters}
              collapsible
            />
          </div>

          {/* Results */}
          <ScrollArea className="flex-1">
            {apolloSearching && (
              <div className="flex items-center justify-center py-12">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="h-5 w-5 animate-spin" />
                  <span>Searching Apollo...</span>
                </div>
              </div>
            )}

            {apolloResults && (
              <ApolloPreviewCard
                data={apolloResults}
                clientTag={currentClientTag}
                autoEnrich={currentAutoEnrich}
                onImported={(target, count) => {
                  console.log(`${count} ${target} imported`);
                }}
              />
            )}

            {!apolloResults && !apolloSearching && (
              <div className="flex items-center justify-center py-12 text-muted-foreground">
                <div className="text-center">
                  <Search className="h-12 w-12 mx-auto mb-3 opacity-20" />
                  <p className="text-sm">Use the form above to search Apollo</p>
                  <p className="text-xs mt-1">or ask the AI to search for you</p>
                </div>
              </div>
            )}
          </ScrollArea>
        </div>

        {/* RIGHT PANEL: AI Chat (40%) */}
        <div className="w-[40%] flex flex-col min-h-0 border rounded-lg bg-card">
          {/* Chat Header */}
          <div className="flex items-center gap-2 px-4 py-3 border-b">
            <MessageSquare className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium">AI Search Assistant</span>
            {context?.isStreaming && (
              <Loader2 className="h-3 w-3 animate-spin text-muted-foreground ml-auto" />
            )}
          </div>

          {/* Messages */}
          <ScrollArea className="flex-1 px-3">
            {context?.messages.length === 0 && (
              <div className="flex items-center justify-center h-full min-h-[200px]">
                <div className="text-center text-muted-foreground px-4">
                  <MessageSquare className="h-8 w-8 mx-auto mb-2 opacity-30" />
                  <p className="text-sm mb-1">AI Search Assistant</p>
                  <p className="text-xs">
                    Search from the form first, then ask me to refine the results.
                    <br />
                    Example: &ldquo;Filtra solo C-suite&rdquo; or &ldquo;Cerca CEO in Milano&rdquo;
                  </p>
                </div>
              </div>
            )}
            {context?.messages
              .filter((msg) => msg.role !== "tool_result")
              .map((msg, i) => (
                <MessageBubble
                  key={msg.id}
                  message={{ role: msg.role as "user" | "assistant", content: msg.content }}
                  isStreaming={
                    context.isStreaming &&
                    i === context.messages.filter((m) => m.role !== "tool_result").length - 1
                  }
                />
              ))}
            {context?.currentToolExecution && (
              <div className="flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground bg-muted/50 rounded-lg my-2">
                <Loader2 className="h-3 w-3 animate-spin" />
                <span>
                  {context.currentToolExecution.tool === "search_apollo"
                    ? "Searching Apollo..."
                    : context.currentToolExecution.tool === "update_icp_draft"
                    ? "Updating ICP..."
                    : context.currentToolExecution.tool === "save_icp"
                    ? "Saving ICP..."
                    : `Running ${context.currentToolExecution.tool}...`}
                </span>
              </div>
            )}
            <div ref={bottomRef} />
          </ScrollArea>

          {/* Chat Input */}
          <div className="border-t">
            <ChatInput
              input={chatInput}
              onInputChange={setChatInput}
              onSend={handleChatSend}
              onFileSelect={() => {}}
              onFileClear={() => {}}
              uploadedFileName={null}
              isStreaming={context?.isStreaming || false}
            />
          </div>
        </div>
      </div>

      {/* Error display */}
      {error && (
        <div className="mt-2 p-3 bg-destructive/10 text-destructive text-sm rounded-lg">
          {error.message}
        </div>
      )}
    </div>
  );
}
