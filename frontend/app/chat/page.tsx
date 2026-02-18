"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import Link from "next/link";
import { FileText, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageBubble } from "@/components/chat/message-bubble";
import { ChatInput } from "@/components/chat/chat-input";
import { ICPPreviewCard } from "@/components/chat/icp-preview-card";
import { ApolloSearchForm, ApolloFormFilters } from "@/components/chat/apollo-search-form";
import { ApolloPreviewCard } from "@/components/chat/apollo-preview-card";
import { api } from "@/lib/api";
import { ChatMessage, ICPExtracted, ApolloSearchResponse } from "@/types";

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [extractedIcp, setExtractedIcp] = useState<ICPExtracted | null>(null);
  const [uploadedFileContent, setUploadedFileContent] = useState<string | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [showSearchForm, setShowSearchForm] = useState(false);
  const [apolloSearching, setApolloSearching] = useState(false);
  const [apolloResults, setApolloResults] = useState<ApolloSearchResponse | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, apolloResults, extractedIcp, scrollToBottom]);

  const runApolloSearch = useCallback(async (params: {
    search_type: "people" | "companies";
    filters: Record<string, unknown>;
    per_page?: number;
  }) => {
    setApolloSearching(true);
    setApolloResults(null);
    try {
      const result = await api.apolloSearch(params);
      setApolloResults(result);
    } catch (err) {
      // Show error as assistant message
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Apollo search error: ${err instanceof Error ? err.message : "unknown error"}`,
        },
      ]);
    } finally {
      setApolloSearching(false);
    }
  }, []);

  const handleApolloSearchParams = useCallback(
    (data: Record<string, unknown>) => {
      const { search_type, per_page, ...rest } = data;
      const filters: Record<string, unknown> = {};
      if (rest.person_titles) filters.person_titles = rest.person_titles;
      if (rest.person_locations) filters.person_locations = rest.person_locations;
      if (rest.person_seniorities) filters.person_seniorities = rest.person_seniorities;
      if (rest.organization_locations) filters.organization_locations = rest.organization_locations;
      if (rest.organization_keywords) filters.organization_keywords = rest.organization_keywords;
      if (rest.organization_sizes) filters.organization_sizes = rest.organization_sizes;
      if (rest.keywords) filters.keywords = rest.keywords;

      runApolloSearch({
        search_type: search_type as "people" | "companies",
        filters,
        per_page: typeof per_page === "number" ? per_page : 25,
      });
    },
    [runApolloSearch]
  );

  const handleFormSearch = useCallback(
    (formFilters: ApolloFormFilters) => {
      setShowSearchForm(false);
      const { search_type, per_page, ...filters } = formFilters;
      runApolloSearch({ search_type, filters: filters as Record<string, unknown>, per_page });
    },
    [runApolloSearch]
  );

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed && !uploadedFileContent) return;
    if (isStreaming) return;

    const userContent = uploadedFileName
      ? `${trimmed}\n\n[Attached file: ${uploadedFileName}]`
      : trimmed;

    const userMessage: ChatMessage = { role: "user", content: userContent };
    const newMessages = [...messages, userMessage];

    setMessages([...newMessages, { role: "assistant", content: "" }]);
    setInput("");
    setIsStreaming(true);
    setExtractedIcp(null);
    setApolloResults(null);

    const apiMessages = [
      ...messages.map((m) => ({ role: m.role, content: m.content })),
      { role: "user", content: trimmed || "Please analyze the uploaded document." },
    ];

    await api.streamChat(
      apiMessages,
      uploadedFileContent,
      // onText
      (text) => {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          updated[updated.length - 1] = { ...last, content: last.content + text };
          return updated;
        });
      },
      // onIcpExtracted
      (data) => {
        setExtractedIcp(data as unknown as ICPExtracted);
      },
      // onDone
      () => {
        setIsStreaming(false);
        setUploadedFileContent(null);
        setUploadedFileName(null);
      },
      // onError
      (err) => {
        console.error("Chat error:", err);
        setIsStreaming(false);
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          updated[updated.length - 1] = {
            ...last,
            content: `Error: ${err.message}. Please try again.`,
          };
          return updated;
        });
      },
      // onApolloSearchParams
      handleApolloSearchParams
    );
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

  const rawInput = messages.map((m) => `${m.role}: ${m.content}`).join("\n");

  return (
    <div className="flex flex-col h-[calc(100vh-48px)]">
      <div className="flex items-center justify-between px-1 pb-4">
        <div>
          <h1 className="text-2xl font-bold">AI Chat</h1>
          <p className="text-sm text-muted-foreground">
            Define your ICP or search for leads on Apollo
          </p>
        </div>
        <div className="flex items-center gap-2">
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
        {messages.length === 0 && !showSearchForm && (
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
        {messages.map((msg, i) => (
          <MessageBubble
            key={i}
            message={msg}
            isStreaming={isStreaming && i === messages.length - 1}
          />
        ))}
        {extractedIcp && <ICPPreviewCard data={extractedIcp} rawInput={rawInput} />}
        {apolloSearching && (
          <div className="flex items-center gap-2 px-4 py-3 text-sm text-muted-foreground">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Searching Apollo…
          </div>
        )}
        {apolloResults && (
          <ApolloPreviewCard
            data={apolloResults}
            onImported={(target, count) => {
              setMessages((prev) => [
                ...prev,
                {
                  role: "assistant",
                  content: `${count} ${target} imported successfully.`,
                },
              ]);
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
        isStreaming={isStreaming || uploading}
      />
    </div>
  );
}
