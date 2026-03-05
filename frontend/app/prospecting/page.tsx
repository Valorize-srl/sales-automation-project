"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Search, Loader2, Plus, MessageSquare, Table2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageBubble } from "@/components/chat/message-bubble";
import { ChatInput } from "@/components/chat/chat-input";
import { ApolloPreviewCard } from "@/components/chat/apollo-preview-card";
import { useChatSession, ApolloResultsData } from "@/hooks/useChatSession";
import { ApolloSearchResponse } from "@/types";

export default function ProspectingPage() {
  const { context, sendMessage, createNewSession, error, onApolloResultsCallback } =
    useChatSession();

  // Results panel state
  const [apolloResults, setApolloResults] = useState<ApolloSearchResponse | null>(null);
  const [showResults, setShowResults] = useState(false);

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
      createNewSession({ title: "Prospecting Session" });
    }
  }, [context, createNewSession]); // eslint-disable-line react-hooks/exhaustive-deps

  // Wire up apollo results callback from chat SSE
  useEffect(() => {
    onApolloResultsCallback.current = (data: ApolloResultsData) => {
      setApolloResults({
        results: data.results as unknown as ApolloSearchResponse["results"],
        total: data.total,
        search_type: data.search_type as "people" | "companies",
        returned: data.returned,
        credits_consumed: 0,
      });
      setShowResults(true);
    };
  }, [onApolloResultsCallback]);

  // Chat send handler
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
    setShowResults(false);
    await createNewSession({ title: "Prospecting Session" });
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
            Parla con l&apos;AI per trovare lead
          </p>
        </div>
        <div className="flex items-center gap-2">
          {apolloResults && (
            <Button
              variant={showResults ? "default" : "outline"}
              size="sm"
              onClick={() => setShowResults(!showResults)}
              className="gap-1.5"
            >
              <Table2 className="h-4 w-4" />
              Risultati ({apolloResults.returned})
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={handleNewSession} className="gap-1.5">
            <Plus className="h-4 w-4" />
            Nuova Sessione
          </Button>
        </div>
      </div>

      {/* Split View */}
      <div className="flex-1 flex gap-4 min-h-0">
        {/* LEFT PANEL: AI Chat */}
        <div className={`flex flex-col min-h-0 border rounded-lg bg-card ${showResults && apolloResults ? "w-[60%]" : "w-full"}`}>
          {/* Chat Header */}
          <div className="flex items-center gap-2 px-4 py-3 border-b">
            <MessageSquare className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium">AI Prospecting Assistant</span>
            {context?.isStreaming && (
              <Loader2 className="h-3 w-3 animate-spin text-muted-foreground ml-auto" />
            )}
          </div>

          {/* Messages */}
          <ScrollArea className="flex-1 px-3">
            {context?.messages.length === 0 && (
              <div className="flex items-center justify-center h-full min-h-[300px]">
                <div className="text-center text-muted-foreground px-6 max-w-md">
                  <MessageSquare className="h-10 w-10 mx-auto mb-3 opacity-30" />
                  <p className="text-base font-medium mb-2">Ciao! Dimmi che tipo di lead stai cercando</p>
                  <p className="text-sm mb-4">
                    Descrivimi il tuo cliente ideale e ti aiuto a trovare le lead giuste su Apollo.
                  </p>
                  <div className="text-xs space-y-1.5 text-left bg-muted/50 rounded-lg p-3">
                    <p className="font-medium mb-1">Esempi:</p>
                    <p>&bull; &ldquo;Cerco CEO di aziende vinicole in Toscana&rdquo;</p>
                    <p>&bull; &ldquo;Trova marketing manager nel settore tech a Milano&rdquo;</p>
                    <p>&bull; &ldquo;Aziende di e-commerce con 50-200 dipendenti in Italia&rdquo;</p>
                  </div>
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
                    ? "Ricerca su Apollo in corso..."
                    : context.currentToolExecution.tool === "update_icp_draft"
                    ? "Aggiornamento ICP..."
                    : context.currentToolExecution.tool === "save_icp"
                    ? "Salvataggio ICP..."
                    : context.currentToolExecution.tool === "import_leads"
                    ? "Importazione lead..."
                    : `${context.currentToolExecution.tool}...`}
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

        {/* RIGHT PANEL: Results (only when there are results and panel is open) */}
        {showResults && apolloResults && (
          <div className="w-[40%] flex flex-col min-h-0 border rounded-lg bg-card">
            <div className="flex items-center justify-between px-4 py-3 border-b">
              <span className="text-sm font-medium">
                Risultati ({apolloResults.returned} di {apolloResults.total})
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowResults(false)}
                className="h-7 text-xs"
              >
                Chiudi
              </Button>
            </div>
            <ScrollArea className="flex-1">
              <ApolloPreviewCard
                data={apolloResults}
                onImported={(target, count) => {
                  console.log(`${count} ${target} imported`);
                }}
              />
            </ScrollArea>
          </div>
        )}
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
