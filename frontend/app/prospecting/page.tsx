"use client";

import { useState, useEffect } from "react";
import { Search, Users, Building2, Zap, MapPin, Globe, Bot, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ToolCard } from "@/components/tools/tool-card";
import { ApolloPeopleForm } from "@/components/tools/apollo-people-form";
import { ApolloCompaniesForm } from "@/components/tools/apollo-companies-form";
import { ApolloEnrichForm } from "@/components/tools/apollo-enrich-form";
import { GoogleMapsForm } from "@/components/tools/google-maps-form";
import { WebsiteScraperForm } from "@/components/tools/website-scraper-form";
import { ClaudePanel } from "@/components/tools/claude-panel";
import { AIAgent } from "@/types";
import { api } from "@/lib/api";

type ToolId = "apollo-people" | "apollo-companies" | "apollo-enrich" | "google-maps" | "website-scraper";

const TOOLS: { id: ToolId; name: string; description: string; icon: typeof Search; cost: string }[] = [
  {
    id: "apollo-people",
    name: "Apollo Search People",
    description: "Cerca decision maker per titolo, location, seniority. Trova email dirette.",
    icon: Users,
    cost: "1 credito / contatto",
  },
  {
    id: "apollo-companies",
    name: "Apollo Search Companies",
    description: "Cerca aziende per settore, dimensione, tecnologie usate, location.",
    icon: Building2,
    cost: "0 crediti (solo ricerca)",
  },
  {
    id: "apollo-enrich",
    name: "Apollo Enrich",
    description: "Arricchisci lead gia' importate con email, telefono e LinkedIn.",
    icon: Zap,
    cost: "1 credito / contatto",
  },
  {
    id: "google-maps",
    name: "Google Maps Search",
    description: "Cerca attivita' locali: ristoranti, negozi, studi, servizi.",
    icon: MapPin,
    cost: "Incluso (Apify)",
  },
  {
    id: "website-scraper",
    name: "Website Scraper",
    description: "Estrai email, telefoni e social dai siti web aziendali.",
    icon: Globe,
    cost: "Incluso (scraping)",
  },
];

export default function ProspectingPage() {
  const [agents, setAgents] = useState<AIAgent[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>("");
  const [agentsLoading, setAgentsLoading] = useState(true);

  const [activeTool, setActiveTool] = useState<ToolId | null>(null);
  const [claudeOpen, setClaudeOpen] = useState(false);

  // Load agents
  useEffect(() => {
    api.getAIAgents({ is_active: true })
      .then((data) => setAgents(data.agents || []))
      .catch((err) => console.error("Failed to load agents:", err))
      .finally(() => setAgentsLoading(false));
  }, []);

  const clientTag = agents.find((a) => a.id === Number(selectedAgentId))?.client_tag;
  const agentId = selectedAgentId ? Number(selectedAgentId) : undefined;

  const renderToolForm = () => {
    switch (activeTool) {
      case "apollo-people":
        return <ApolloPeopleForm clientTag={clientTag} />;
      case "apollo-companies":
        return <ApolloCompaniesForm clientTag={clientTag} />;
      case "apollo-enrich":
        return <ApolloEnrichForm clientTag={clientTag} />;
      case "google-maps":
        return <GoogleMapsForm clientTag={clientTag} />;
      case "website-scraper":
        return <WebsiteScraperForm clientTag={clientTag} />;
      default:
        return null;
    }
  };

  const activeToolMeta = TOOLS.find((t) => t.id === activeTool);

  return (
    <div className="flex flex-col h-[calc(100vh-48px)]">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between px-1 pb-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Search className="h-6 w-6" />
            Prospecting Tools
          </h1>
          <p className="text-sm text-muted-foreground">
            Cerca lead, arricchisci dati, importa contatti
          </p>
        </div>
        <div className="flex items-center gap-2">
          {!agentsLoading && agents.length > 0 && (
            <Select value={selectedAgentId} onValueChange={setSelectedAgentId}>
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
          <Button
            variant="outline"
            size="sm"
            onClick={() => setClaudeOpen(true)}
            className="gap-1.5"
          >
            <MessageSquare className="h-4 w-4" />
            Chiedi a Claude
          </Button>
        </div>
      </div>

      {/* Tool Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 px-1">
        {TOOLS.map((tool) => (
          <ToolCard
            key={tool.id}
            name={tool.name}
            description={tool.description}
            icon={tool.icon}
            cost={tool.cost}
            onClick={() => setActiveTool(tool.id)}
          />
        ))}
      </div>

      {/* Tool Drawer (right side) */}
      <Sheet open={!!activeTool} onOpenChange={(open) => !open && setActiveTool(null)}>
        <SheetContent side="right" className="w-[500px] sm:w-[600px] p-0 flex flex-col">
          <SheetHeader className="p-4 border-b">
            <SheetTitle className="text-sm flex items-center gap-2">
              {activeToolMeta && <activeToolMeta.icon className="h-4 w-4" />}
              {activeToolMeta?.name}
            </SheetTitle>
          </SheetHeader>
          <div className="flex-1 overflow-y-auto p-4">
            {renderToolForm()}
          </div>
        </SheetContent>
      </Sheet>

      {/* Claude Chat Panel (left side) */}
      <ClaudePanel open={claudeOpen} onOpenChange={setClaudeOpen} agentId={agentId} />
    </div>
  );
}
