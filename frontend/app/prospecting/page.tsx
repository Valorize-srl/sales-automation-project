"use client";

import { useState } from "react";
import { Search, Users, Building2, Zap, MapPin, Globe, Linkedin } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ToolCard } from "@/components/tools/tool-card";
import { ApolloPeopleForm } from "@/components/tools/apollo-people-form";
import { ApolloCompaniesForm } from "@/components/tools/apollo-companies-form";
import { ApolloEnrichForm } from "@/components/tools/apollo-enrich-form";
import { GoogleMapsForm } from "@/components/tools/google-maps-form";
import { WebsiteScraperForm } from "@/components/tools/website-scraper-form";
import { LinkedInPeopleForm } from "@/components/tools/linkedin-people-form";
import { LinkedInCompaniesForm } from "@/components/tools/linkedin-companies-form";

type ToolId =
  | "apollo-people"
  | "apollo-companies"
  | "apollo-enrich"
  | "google-maps"
  | "website-scraper"
  | "linkedin-people"
  | "linkedin-companies";

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
    id: "linkedin-people",
    name: "LinkedIn Search People",
    description: "Cerca decision maker su LinkedIn per ruolo, azienda, location.",
    icon: Linkedin,
    cost: "~$0.01 / profilo (Apify)",
  },
  {
    id: "linkedin-companies",
    name: "LinkedIn Search Companies",
    description: "Scraping profili aziendali LinkedIn: dipendenti, settore, specialties.",
    icon: Linkedin,
    cost: "~$0.01 / profilo (Apify)",
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
  const [activeTool, setActiveTool] = useState<ToolId | null>(null);

  const renderToolForm = () => {
    switch (activeTool) {
      case "apollo-people":
        return <ApolloPeopleForm />;
      case "apollo-companies":
        return <ApolloCompaniesForm />;
      case "apollo-enrich":
        return <ApolloEnrichForm />;
      case "google-maps":
        return <GoogleMapsForm />;
      case "website-scraper":
        return <WebsiteScraperForm />;
      case "linkedin-people":
        return <LinkedInPeopleForm />;
      case "linkedin-companies":
        return <LinkedInCompaniesForm />;
      default:
        return null;
    }
  };

  const activeToolMeta = TOOLS.find((t) => t.id === activeTool);

  return (
    <div className="flex flex-col h-[calc(100vh-48px)]">
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
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 px-1">
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
    </div>
  );
}
