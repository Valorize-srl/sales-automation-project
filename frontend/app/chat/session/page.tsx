"use client";

import { useState, useRef, useEffect, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { FileText, SlidersHorizontal, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageBubble } from "@/components/chat/message-bubble";
import { ChatInput } from "@/components/chat/chat-input";
import { SessionSidebar } from "@/components/chat/session-sidebar";
import { ApolloSearchForm, ApolloFormFilters } from "@/components/chat/apollo-search-form";
import { ApolloPreviewCard } from "@/components/chat/apollo-preview-card";
import { ApolloCreditsCard } from "@/components/chat/apollo-credits-card";
import { useChatSession } from "@/hooks/useChatSession";
import { api } from "@/lib/api";
import { ApolloSearchResponse } from "@/types";

function SessionChatPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionUuid = searchParams.get("session_uuid");

  const { context, sendMessage, createNewSession, error } = useChatSession(sessionUuid || undefined);

  const [input, setInput] = useState("");
  const [uploadedFileContent, setUploadedFileContent] = useState<string | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [showSearchForm, setShowSearchForm] = useState(false);
  const [apolloSearching, setApolloSearching] = useState(false);
  const [apolloResults, setApolloResults] = useState<ApolloSearchResponse | null>(null);
  const [apolloCreditsUsed, setApolloCreditsUsed] = useState<number | null>(null);
  const [currentClientTag, setCurrentClientTag] = useState<string | undefined>(undefined);

  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [context?.messages, apolloResults, scrollToBottom]);

  // Auto-create session if no session_uuid in URL
  useEffect(() => {
    if (!sessionUuid && !context) {
      createNewSession().then((uuid) => {
        if (uuid) {
          router.push(`/chat/session?session_uuid=${uuid}`);
        }
      });
    }
  }, [sessionUuid, context, createNewSession, router]);

  const runApolloSearch = useCallback(
    async (params: {
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
    }) => {
      console.log("🚀 Running Apollo search with params:", params);
      setApolloSearching(true);
      setApolloResults(null);
      setCurrentClientTag(params.client_tag);
      try {
        const result = await api.apolloSearch(params);
        console.log("✅ Apollo search result:", result);

        // Calculate usage with Claude tokens + Apollo credits
        if (params.claude_tokens && result.credits_consumed !== undefined) {
          console.log("💰 Calculating costs with tokens:", params.claude_tokens);
          const apollo_credits = result.credits_consumed;
          const apollo_cost = apollo_credits * 0.1;
          const claude_input_cost = (params.claude_tokens.input_tokens / 1_000_000) * 3.0;
          const claude_output_cost = (params.claude_tokens.output_tokens / 1_000_000) * 15.0;
          const claude_total_cost = claude_input_cost + claude_output_cost;

          result.usage = {
            apollo_credits,
            claude_tokens: params.claude_tokens,
            estimated_cost_usd: {
              apollo_usd: parseFloat(apollo_cost.toFixed(4)),
              claude_usd: parseFloat(claude_total_cost.toFixed(4)),
              total_usd: parseFloat((apollo_cost + claude_total_cost).toFixed(4)),
            },
          };
        }

        setApolloResults(result);
        if (result.credits_consumed !== undefined) {
          setApolloCreditsUsed(result.credits_consumed);
        }
      } catch (err) {
        console.error("Apollo search error:", err);
      } finally {
        setApolloSearching(false);
      }
    },
    []
  );

  const handleFormSearch = useCallback(
    (formFilters: ApolloFormFilters) => {
      setShowSearchForm(false);
      const { search_type, per_page, client_tag, ...filters } = formFilters;
      runApolloSearch({
        search_type,
        filters: filters as Record<string, unknown>,
        per_page,
        client_tag,
      });
    },
    [runApolloSearch]
  );

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed && !uploadedFileContent) return;
    if (context?.isStreaming) return;

    const userContent = uploadedFileName
      ? `${trimmed}\n\n[Attached file: ${uploadedFileName}]`
      : trimmed;

    setInput("");

    try {
      await sendMessage(userContent, uploadedFileContent || undefined);
      setUploadedFileContent(null);
      setUploadedFileName(null);
    } catch (err) {
      console.error("Send message error:", err);
    }
  };

  const handleFileSelect = async (file: File) => {
    setUploading(true);
    try {
      const result = await api.uploadFile(file);
      setUploadedFileContent(result.text);
      setUploadedFileName(result.filename);
    } catch (err) {
      console.error("Upload error:", err);
    } finally {
      setUploading(false);
    }
  };

  const handleFileClear = () => {
    setUploadedFileContent(null);
    setUploadedFileName(null);
  };

  const handleEnrichCompanies = async () => {
    if (!context?.lastSearchResults?.company_ids.length) return;

    await sendMessage(
      `Enrich these companies with contact emails from their websites: ${context.lastSearchResults.company_ids.join(", ")}`
    );
  };

  if (!context && !error) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-48px)]">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-muted-foreground">Creating session...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-48px)]">
        <div className="text-center">
          <p className="text-destructive mb-4">Error: {error.message}</p>
          <Button onClick={() => createNewSession()}>Create New Session</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-4 h-[calc(100vh-48px)]">
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex items-center justify-between px-1 pb-4">
          <div>
            <h1 className="text-2xl font-bold">AI Chat</h1>
            <p className="text-sm text-muted-foreground">
              Conversational ICP definition and lead search
            </p>
          </div>
          <div className="flex items-center gap-2">
            <ApolloCreditsCard creditsUsed={apolloCreditsUsed} />
            <Button
              variant="outline"
              size="sm"
              className="gap-1"
              onClick={() => {
                setShowSearchForm((v) => !v);
                setApolloResults(null);
              }}
            >
              <SlidersHorizontal className="h-4 w-4" />
              Advanced Search
            </Button>
            <Link href="/chat/icp">
              <Button variant="outline" size="sm" className="gap-1">
                <FileText className="h-4 w-4" />
                Saved ICPs
              </Button>
            </Link>
          </div>
        </div>

        {showSearchForm && (
          <div className="mb-3">
            <ApolloSearchForm
              onSearch={handleFormSearch}
              onClose={() => setShowSearchForm(false)}
              loading={apolloSearching}
            />
          </div>
        )}

        <ScrollArea className="flex-1 px-1">
          {context?.messages.length === 0 && !showSearchForm && (
            <div className="flex items-center justify-center h-full min-h-[300px]">
              <div className="text-center">
                <p className="text-muted-foreground mb-2">
                  Start a conversation to define your ICP or search for leads.
                </p>
                <p className="text-sm text-muted-foreground">
                  Try: &ldquo;Find SEO specialists in Italy&rdquo; or use Advanced Search.
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
                isStreaming={context.isStreaming && i === context.messages.length - 1}
              />
            ))}
          {context?.currentToolExecution && (
            <div className="flex items-center gap-2 px-4 py-3 text-sm text-muted-foreground bg-muted/50 rounded-lg my-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>
                {context.currentToolExecution.tool === "search_apollo" && "Searching Apollo..."}
                {context.currentToolExecution.tool === "enrich_companies" && "Enriching companies..."}
                {context.currentToolExecution.tool === "save_icp" && "Saving ICP..."}
                {context.currentToolExecution.tool === "update_icp_draft" && "Updating ICP draft..."}
                {context.currentToolExecution.tool === "verify_emails" && "Verifying emails..."}
                {!["search_apollo", "enrich_companies", "save_icp", "update_icp_draft", "verify_emails"].includes(
                  context.currentToolExecution.tool
                ) && `Executing ${context.currentToolExecution.tool}...`}
              </span>
            </div>
          )}
          {apolloSearching && (
            <div className="flex items-center gap-2 px-4 py-3 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Searching Apollo…
            </div>
          )}
          {apolloResults && (
            <ApolloPreviewCard
              data={apolloResults}
              clientTag={currentClientTag}
              autoEnrich={false}
              onImported={(target, count) => {
                console.log(`${count} ${target} imported successfully.`);
              }}
            />
          )}
          <div ref={bottomRef} />
        </ScrollArea>

        <ChatInput
          input={input}
          onInputChange={setInput}
          onSend={handleSend}
          onFileSelect={handleFileSelect}
          onFileClear={handleFileClear}
          uploadedFileName={uploading ? "Uploading..." : uploadedFileName}
          isStreaming={context?.isStreaming || uploading}
        />
      </div>

      {/* Session Sidebar */}
      <div className="w-80 flex-shrink-0">
        <SessionSidebar
          currentIcp={context?.currentIcp || null}
          lastSearchResults={context?.lastSearchResults || null}
          sessionStats={{
            totalCost: context?.sessionStats.totalCost || 0,
            messageCount: context?.sessionStats.messageCount || 0,
            apolloCredits: context?.sessionStats.apolloCredits || 0,
          }}
          onEnrichCompanies={handleEnrichCompanies}
        />
      </div>
    </div>
  );
}

export default function SessionChatPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-[calc(100vh-48px)]">
          <div className="text-center">
            <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-primary" />
            <p className="text-muted-foreground">Loading session...</p>
          </div>
        </div>
      }
    >
      <SessionChatPageContent />
    </Suspense>
  );
}
