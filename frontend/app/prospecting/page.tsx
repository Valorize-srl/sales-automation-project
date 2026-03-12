"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Search, Loader2, Plus, MessageSquare, Table2, Download, Bot } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { MessageBubble } from "@/components/chat/message-bubble";
import { ChatInput } from "@/components/chat/chat-input";
import { ApolloPreviewCard } from "@/components/chat/apollo-preview-card";
import { useChatSession, ApolloResultsData, CsvReadyData } from "@/hooks/useChatSession";
import { ApolloSearchResponse, AIAgent } from "@/types";
import { api } from "@/lib/api";

const TOOL_LABELS: Record<string, string> = {
  search_apollo: "Ricerca su Apollo...",
  search_google_maps: "Ricerca su Google Maps...",
  scrape_websites: "Estrazione contatti dai siti web...",
  search_linkedin_companies: "Ricerca aziende su LinkedIn...",
  search_linkedin_people: "Ricerca decision maker su LinkedIn...",
  update_icp_draft: "Aggiornamento ICP...",
  save_icp: "Salvataggio ICP...",
  import_leads: "Importazione lead...",
  generate_csv: "Generazione CSV...",
  get_session_context: "Recupero contesto...",
};

function downloadBase64Csv(filename: string, base64: string) {
  const raw = atob(base64);
  const blob = new Blob([raw], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ProspectingPage() {
  const { context, sendMessage, createNewSession, error, onApolloResultsCallback, onCsvReadyCallback } =
    useChatSession();

  // Agent selector state
  const [agents, setAgents] = useState<AIAgent[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>("");
  const [agentsLoading, setAgentsLoading] = useState(true);

  // Results panel state
  const [apolloResults, setApolloResults] = useState<ApolloSearchResponse | null>(null);
  const [showResults, setShowResults] = useState(false);

  // CSV state
  const [csvData, setCsvData] = useState<CsvReadyData | null>(null);

  // Chat state
  const [chatInput, setChatInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [context?.messages, scrollToBottom]);

  // Load available agents on mount
  useEffect(() => {
    api.getAIAgents({ is_active: true })
      .then((data) => setAgents(data.agents || []))
      .catch((err) => console.error("Failed to load agents:", err))
      .finally(() => setAgentsLoading(false));
  }, []);

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

  // Wire up CSV ready callback
  useEffect(() => {
    onCsvReadyCallback.current = (data: CsvReadyData) => {
      setCsvData(data);
    };
  }, [onCsvReadyCallback]);

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
    setCsvData(null);
    const agentId = selectedAgentId ? Number(selectedAgentId) : undefined;
    const agentName = agents.find((a) => a.id === agentId)?.name;
    await createNewSession({
      title: agentName ? `Prospecting — ${agentName}` : "Prospecting Session",
      ai_agent_id: agentId,
    });
  };

  // Handle agent selection change — create new session with agent
  const handleAgentChange = async (value: string) => {
    setSelectedAgentId(value);
    setApolloResults(null);
    setShowResults(false);
    setCsvData(null);
    const agentId = value ? Number(value) : undefined;
    const agentName = agents.find((a) => a.id === agentId)?.name;
    await createNewSession({
      title: agentName ? `Prospecting — ${agentName}` : "Prospecting Session",
      ai_agent_id: agentId,
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
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between px-1 pb-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Search className="h-6 w-6" />
            Prospecting
          </h1>
          <p className="text-sm text-muted-foreground">
            Ricerca lead B2B interattiva con AI
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Agent selector */}
          {!agentsLoading && agents.length > 0 && (
            <Select value={selectedAgentId} onValueChange={handleAgentChange}>
              <SelectTrigger className="w-[200px] h-9">
                <Bot className="h-4 w-4 mr-1.5 flex-shrink-0" />
                <SelectValue placeholder="Seleziona agente" />
              </SelectTrigger>
              <SelectContent>
                {agents.map((agent) => (
                  <SelectItem key={agent.id} value={String(agent.id)}>
                    {agent.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {csvData && (
            <Button
              variant="default"
              size="sm"
              onClick={() => downloadBase64Csv(csvData.filename, csvData.content_base64)}
              className="gap-1.5"
            >
              <Download className="h-4 w-4" />
              CSV ({csvData.rows} righe)
            </Button>
          )}
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
      <div className="flex-1 flex flex-col lg:flex-row gap-4 min-h-0">
        {/* LEFT PANEL: AI Chat */}
        <div className={`flex flex-col min-h-0 border rounded-lg bg-card ${showResults && apolloResults ? "w-full lg:w-[60%]" : "w-full"}`}>
          {/* Chat Header */}
          <div className="flex items-center gap-2 px-4 py-3 border-b">
            <MessageSquare className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium">
              {selectedAgentId
                ? `Prospecting — ${agents.find((a) => a.id === Number(selectedAgentId))?.name || "Agent"}`
                : "AI Prospecting Agent"}
            </span>
            {context?.isStreaming && (
              <div className="flex items-center gap-1.5 ml-auto">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                <span className="text-xs font-medium text-primary">Elaborazione...</span>
              </div>
            )}
          </div>

          {/* Messages */}
          <ScrollArea className="flex-1 px-3">
            {context?.messages.length === 0 && (
              <div className="flex items-center justify-center h-full min-h-[300px]">
                <div className="text-center text-muted-foreground px-6 max-w-md">
                  <MessageSquare className="h-10 w-10 mx-auto mb-3 opacity-30" />
                  <p className="text-base font-medium mb-2">Descrivi chi vuoi trovare</p>
                  <p className="text-sm mb-4">
                    L&apos;AI ti guida passo per passo: definizione ICP, ricerca aziende, decision maker, contatti ed export CSV.
                  </p>
                  <div className="text-xs space-y-1.5 text-left bg-muted/50 rounded-lg p-3">
                    <p className="font-medium mb-1">Esempi:</p>
                    <p>&bull; &ldquo;Trova agenzie SEO a Milano, propongo servizi white label&rdquo;</p>
                    <p>&bull; &ldquo;Cerco ristoranti stellati in Toscana per proporre forniture vino&rdquo;</p>
                    <p>&bull; &ldquo;Studi commercialisti a Roma con almeno 10 dipendenti&rdquo;</p>
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
              <div className="flex items-center gap-3 px-4 py-3 text-sm text-primary bg-primary/5 border border-primary/20 rounded-lg my-3 animate-pulse">
                <Loader2 className="h-5 w-5 animate-spin flex-shrink-0" />
                <span className="font-medium">
                  {TOOL_LABELS[context.currentToolExecution.tool] || `${context.currentToolExecution.tool}...`}
                </span>
              </div>
            )}
            {context?.isStreaming && !context?.currentToolExecution &&
              context.messages.length > 0 &&
              context.messages[context.messages.length - 1]?.role !== "assistant" && (
              <div className="flex items-center gap-3 px-4 py-3 text-sm text-muted-foreground bg-muted/50 rounded-lg my-3">
                <Loader2 className="h-5 w-5 animate-spin text-primary flex-shrink-0" />
                <span>L&apos;AI sta pensando...</span>
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
          <div className="w-full lg:w-[40%] flex flex-col min-h-0 border rounded-lg bg-card">
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
