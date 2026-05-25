"use client";

import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { Sparkles, Globe, Linkedin, Mail, Users } from "lucide-react";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Whether the user has companies selected (or "all matching"). Enrichment
   * actions require a selection; sourcing actions (Apollo Search People) do not. */
  hasSelection: boolean;
  selectionLabel: string; // e.g. "12 selected" / "all 230 matching"

  onApolloSearchPeople: () => void;
  onBulkScrape: () => void;
  onFindymailCompanyInfo: () => void;
  onLinkedInDM: () => void;
  onFindymailFindDM: () => void;
  onFindymailFindDMViaLinkedIn: () => void;
  onFindymail: () => void;
}

/** Side drawer with all enrichment + sourcing tools. Replaces the inline
 * "Arricchisci" dropdown on /leads. Sourcing tools (Apollo) work without a
 * selection; enrichment tools require at least one company selected. */
export function EnrichmentDrawer({
  open, onOpenChange, hasSelection, selectionLabel,
  onApolloSearchPeople,
  onBulkScrape,
  onFindymailCompanyInfo,
  onLinkedInDM,
  onFindymailFindDM,
  onFindymailFindDMViaLinkedIn,
  onFindymail,
}: Props) {
  const close = () => onOpenChange(false);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-md flex flex-col p-0">
        <SheetHeader className="px-5 py-4 border-b">
          <SheetTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            Arricchisci lead
          </SheetTitle>
          <SheetDescription className="text-xs">
            {hasSelection
              ? `Le azioni di enrichment lavorano su: ${selectionLabel}`
              : "Seleziona aziende per abilitare gli strumenti di enrichment. Le ricerche Apollo sono sempre disponibili."}
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto">
          {/* Sourcing — always available */}
          <SectionLabel>🔍 Sourcing</SectionLabel>
          <DrawerItem
            icon={<Users className="h-4 w-4 text-purple-600" />}
            title="Cerca nuove persone"
            badge={{ label: "Apollo", className: "bg-purple-100 text-purple-800 border-purple-200" }}
            description="Cerca DM per ruolo / location / seniority. Importa nella lista scelta."
            onClick={() => { onApolloSearchPeople(); close(); }}
          />

          {/* Enrichment — require selection */}
          <SectionLabel className="border-t mt-1">✨ Enrichment</SectionLabel>
          <DrawerItem
            icon={<Globe className="h-4 w-4 text-emerald-600" />}
            title="Scrapa siti web"
            description="Estrai email + LinkedIn dalle pagine del sito aziendale"
            disabled={!hasSelection}
            onClick={() => { onBulkScrape(); close(); }}
          />
          <DrawerItem
            icon={<Linkedin className="h-4 w-4 text-[#E8662C]" />}
            title="Trova LinkedIn azienda"
            badge={{ label: "Findymail", className: "bg-[#FFE9DA] text-[#E8662C] border-[#E8662C]/30" }}
            description="Cerca pagina LinkedIn aziendale + settore + dominio email (gratis)"
            disabled={!hasSelection}
            onClick={() => { onFindymailCompanyInfo(); close(); }}
          />
          <DrawerItem
            icon={<Linkedin className="h-4 w-4 text-[#0A66C2]" />}
            title="Trova DM via LinkedIn"
            description="Cerca decision maker su Google + LinkedIn — niente login"
            disabled={!hasSelection}
            onClick={() => { onLinkedInDM(); close(); }}
          />
          <DrawerItem
            icon={<Sparkles className="h-4 w-4 text-[#E8662C]" />}
            title="Cerca DM per ruolo"
            badge={{ label: "Findymail", className: "bg-[#FFE9DA] text-[#E8662C] border-[#E8662C]/30" }}
            description="Trova nome + email direttamente sul dominio aziendale dato un job title"
            disabled={!hasSelection}
            onClick={() => { onFindymailFindDM(); close(); }}
          />
          <DrawerItem
            icon={<Sparkles className="h-4 w-4 text-[#E8662C]" />}
            title="Cerca DM completi (LinkedIn + email)"
            badge={{ label: "Findymail", className: "bg-[#FFE9DA] text-[#E8662C] border-[#E8662C]/30" }}
            description="Trova fino a N dipendenti via LinkedIn aziendale + recupera la loro email. Output più completo, costa di più."
            disabled={!hasSelection}
            onClick={() => { onFindymailFindDMViaLinkedIn(); close(); }}
          />
          <DrawerItem
            icon={<Mail className="h-4 w-4 text-[#E8662C]" />}
            title="Trova email per DM esistenti"
            badge={{ label: "Findymail", className: "bg-[#FFE9DA] text-[#E8662C] border-[#E8662C]/30" }}
            description="Per ogni DM senza email: lookup via LinkedIn URL o nome+dominio"
            disabled={!hasSelection}
            onClick={() => { onFindymail(); close(); }}
          />
        </div>
      </SheetContent>
    </Sheet>
  );
}

function SectionLabel({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <p className={`px-4 pt-3 pb-1 text-[10px] uppercase tracking-wider text-muted-foreground font-semibold ${className}`}>
      {children}
    </p>
  );
}

function DrawerItem({
  icon, title, description, badge, disabled, onClick,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  badge?: { label: string; className: string };
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      className={`flex items-start gap-3 px-4 py-3 text-sm w-full text-left border-b last:border-b-0 transition-colors ${
        disabled ? "opacity-40 cursor-not-allowed" : "hover:bg-accent"
      }`}
    >
      <span className="shrink-0 mt-0.5">{icon}</span>
      <div className="flex-1 min-w-0">
        <p className="font-medium leading-tight flex items-center gap-1.5 flex-wrap">
          {title}
          {badge && (
            <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[9px] font-medium border ${badge.className}`}>
              {badge.label}
            </span>
          )}
        </p>
        <p className="text-[11px] text-muted-foreground leading-snug mt-0.5">
          {description}
        </p>
      </div>
    </button>
  );
}
