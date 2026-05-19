"use client";

import { useState } from "react";
import {
  Mail, Loader2, CheckCircle, XCircle, ChevronDown, ChevronRight, Star, Linkedin,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import { Company } from "@/types";

interface FoundPerson {
  id: number;
  first_name: string;
  last_name: string;
  title: string | null;
  email: string | null;
  linkedin_url: string | null;
}

interface CompanyRowState {
  company: Company;
  status: "pending" | "running" | "done" | "error";
  candidates_found: number;
  with_email: number;
  imported_count: number;
  duplicates_skipped: number;
  website?: string | null;
  website_resolved_via?: "db" | "linkedin";
  people: FoundPerson[];
  error?: string;
  expanded: boolean;
}

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  companies: Company[];
  onCompleted?: () => void;
  /** Forward company IDs with at least one DM-with-email so the parent can
   * open its PushToCampaignDialog. */
  onPushToCampaign?: (companyIds: number[]) => void;
}

export function FindymailFindDMViaLinkedInDialog({
  open, onOpenChange, companies, onCompleted, onPushToCampaign,
}: Props) {
  const [titlesInput, setTitlesInput] = useState("");
  const [maxResultsInput, setMaxResultsInput] = useState("5");
  const [rows, setRows] = useState<CompanyRowState[]>([]);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);

  const reset = () => {
    setRows([]);
    setRunning(false);
    setDone(false);
  };

  const handleOpen = (isOpen: boolean) => {
    if (!isOpen) reset();
    onOpenChange(isOpen);
  };

  const parseTitles = (s: string): string[] =>
    s.split(/[,\n;]+/).map((t) => t.trim()).filter(Boolean);

  const titlesParsed = parseTitles(titlesInput);
  const tooManyTitles = titlesParsed.length > 3;
  const maxResults = Math.max(1, Math.min(10, parseInt(maxResultsInput, 10) || 5));
  const canStart = titlesParsed.length > 0 && !tooManyTitles && companies.length > 0;

  const start = async () => {
    if (!canStart) return;
    const titles = titlesParsed.slice(0, 3);

    const initial: CompanyRowState[] = companies.map((c) => ({
      company: c,
      status: "pending",
      candidates_found: 0,
      with_email: 0,
      imported_count: 0,
      duplicates_skipped: 0,
      people: [],
      expanded: false,
    }));
    setRows(initial);
    setRunning(true);
    setDone(false);

    const updated = [...initial];
    for (let i = 0; i < companies.length; i += 1) {
      updated[i] = { ...updated[i], status: "running" };
      setRows([...updated]);
      try {
        const r = await api.findDMViaLinkedInFindymail(companies[i].id, titles, maxResults);
        updated[i] = {
          ...updated[i],
          status: "done",
          candidates_found: r.candidates_found,
          with_email: r.with_email,
          imported_count: r.imported_count,
          duplicates_skipped: r.duplicates_skipped,
          website: r.website,
          website_resolved_via: r.website_resolved_via,
          people: r.people,
          expanded: r.imported_count > 0 || r.candidates_found > 0,
        };
      } catch (e: unknown) {
        updated[i] = {
          ...updated[i],
          status: "error",
          error: e instanceof Error ? e.message : "Errore",
        };
      }
      setRows([...updated]);
    }

    setRunning(false);
    setDone(true);
    onCompleted?.();
  };

  const completedCount = rows.filter((r) => r.status === "done" || r.status === "error").length;
  const totalImported = rows.reduce((acc, r) => acc + r.imported_count, 0);
  const totalCandidates = rows.reduce((acc, r) => acc + r.candidates_found, 0);
  const totalWithEmail = rows.reduce((acc, r) => acc + r.with_email, 0);
  const progress = rows.length > 0 ? Math.round((completedCount / rows.length) * 100) : 0;
  const pushableCompanyIds = rows
    .filter((r) => r.status === "done" && r.people.some((p) => p.email && p.email.trim()))
    .map((r) => r.company.id);

  const toggleExpand = (idx: number) =>
    setRows((prev) => {
      const n = [...prev];
      n[idx] = { ...n[idx], expanded: !n[idx].expanded };
      return n;
    });

  // Rough max credits a single batch can consume. /search/employees costs 1
  // credit per profile returned (capped at maxResults), and /search/linkedin
  // costs 1 credit per email found. Worst-case: maxResults employees × 2.
  const maxCreditsPerCompany = maxResults * 2;
  const maxCreditsTotal = companies.length * maxCreditsPerCompany;

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogContent className="sm:max-w-[680px] max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Star className="h-5 w-5 text-[#E8662C]" />
            Cerca DM completi (LinkedIn + email)
            <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-[#FFE9DA] text-[#E8662C] border border-[#E8662C]/30">
              Findymail
            </span>
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4 flex-1 overflow-hidden">
          {!running && !done && (
            <div className="space-y-3">
              <div className="rounded-md border bg-muted/40 p-3 text-xs space-y-1.5 text-muted-foreground">
                <p className="font-medium text-foreground">Come funziona</p>
                <ol className="list-decimal pl-5 space-y-0.5">
                  <li>Findymail cerca i <strong>dipendenti</strong> via website aziendale + ruoli (<code className="text-[10px] px-1 rounded bg-muted">/search/employees</code>) e ritorna nome + LinkedIn URL.</li>
                  <li>Per ogni profilo trovato, recupera l&apos;email associata (<code className="text-[10px] px-1 rounded bg-muted">/search/linkedin</code>).</li>
                  <li>Salva ogni match come Person nel database (nome, email, LinkedIn URL, titolo).</li>
                </ol>
                <p className="pt-1">
                  Costo: <span className="font-medium">1 credito per profilo restituito</span> + <span className="font-medium">1 credito per email trovata</span>.
                  Massimo <span className="font-medium">{maxCreditsTotal}</span> crediti per questa operazione.
                </p>
                <p className="text-[11px] italic">
                  Differenza con &quot;Cerca DM per ruolo&quot;: questa versione ritorna anche il LinkedIn URL del DM, costa di più.
                </p>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium flex items-center justify-between">
                  <span>Job title / ruoli <span className="text-muted-foreground">(separati da virgola, max 3)</span></span>
                  <span className={`tabular-nums ${tooManyTitles ? "text-red-600" : "text-muted-foreground"}`}>
                    {titlesParsed.length}/3
                  </span>
                </label>
                <Input
                  value={titlesInput}
                  onChange={(e) => setTitlesInput(e.target.value)}
                  placeholder="es. CEO, Sales Director, Procurement Manager"
                  className={`text-sm ${tooManyTitles ? "border-red-500 focus-visible:ring-red-500" : ""}`}
                  autoFocus
                />
                {tooManyTitles && (
                  <p className="text-[11px] text-red-600">
                    Findymail accetta massimo 3 ruoli per ricerca. Riduci la lista o lancia ricerche separate.
                  </p>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-medium flex items-center justify-between">
                  <span>Max profili per azienda <span className="text-muted-foreground">(1–10)</span></span>
                  <span className="tabular-nums text-muted-foreground">{maxResults}</span>
                </label>
                <Input
                  type="number"
                  min={1}
                  max={10}
                  value={maxResultsInput}
                  onChange={(e) => setMaxResultsInput(e.target.value)}
                  className="text-sm w-24"
                />
              </div>

              <div className="rounded-md border bg-card p-3 text-sm">
                <p>
                  <span className="font-medium">{companies.length}</span> aziend{companies.length === 1 ? "a" : "e"} verr
                  {companies.length === 1 ? "à" : "anno"} processat{companies.length === 1 ? "a" : "e"}.
                </p>
                <p className="text-muted-foreground text-xs mt-0.5">
                  Aziende senza website (e senza LinkedIn URL aziendale che ne permetta il lookup) verranno saltate.
                </p>
              </div>

              {companies.length === 0 ? (
                <p className="text-sm text-muted-foreground italic">Nessuna azienda selezionata.</p>
              ) : (
                <Button
                  onClick={start}
                  disabled={!canStart}
                  className="gap-2 bg-[#E8662C] hover:bg-[#E8662C]/90 text-white"
                >
                  <Star className="h-4 w-4" />
                  Cerca via Findymail ({companies.length})
                </Button>
              )}
            </div>
          )}

          {(running || done) && rows.length > 0 && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>
                  {completedCount} / {rows.length} aziende — {totalImported} salvati, {totalWithEmail}/{totalCandidates} con email
                </span>
                <span>{progress}%</span>
              </div>
              <Progress value={progress} className="h-1.5" />
            </div>
          )}

          {rows.length > 0 && (
            <div className="flex-1 overflow-y-auto space-y-1 pr-1">
              {rows.map((row, idx) => (
                <div key={row.company.id} className="rounded-md border text-sm">
                  <button
                    className="flex items-center gap-2 w-full px-3 py-2 text-left hover:bg-accent/50 rounded-md"
                    onClick={() => toggleExpand(idx)}
                  >
                    <StatusIcon status={row.status} />
                    <span className="flex-1 font-medium truncate">{row.company.name}</span>
                    {row.status === "done" && (
                      <>
                        <Badge variant="secondary" className="text-[10px] tabular-nums">
                          {row.candidates_found} profili / {row.with_email} email
                        </Badge>
                        {row.imported_count > 0 && (
                          <Badge variant="secondary" className="text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200/60">
                            +{row.imported_count}
                          </Badge>
                        )}
                      </>
                    )}
                    {row.status === "done" || row.status === "error"
                      ? row.expanded
                        ? <ChevronDown className="h-3.5 w-3.5 shrink-0" />
                        : <ChevronRight className="h-3.5 w-3.5 shrink-0" />
                      : null}
                  </button>

                  {row.expanded && (
                    <div className="px-3 pb-3 space-y-2 border-t pt-2">
                      {row.status === "error" && (
                        <p className="text-xs text-red-600 dark:text-red-400">{row.error}</p>
                      )}
                      {row.status === "done" && row.website && (
                        <p className="text-[10px] text-muted-foreground">
                          Website cercato: <code className="px-1 rounded bg-muted">{row.website}</code>
                          {row.website_resolved_via === "linkedin" && (
                            <span className="ml-1.5 inline-flex items-center gap-0.5 px-1 rounded bg-[#0A66C2]/10 text-[#0A66C2] text-[9px]">
                              <Linkedin className="h-2 w-2" /> dedotto da LinkedIn
                            </span>
                          )}
                        </p>
                      )}
                      {row.status === "done" && row.people.length === 0 && (
                        <p className="text-xs text-muted-foreground italic">
                          {row.candidates_found === 0
                            ? "Findymail non ha trovato profili per i ruoli indicati."
                            : `${row.candidates_found} profili trovati ma tutti già presenti (duplicati).`}
                        </p>
                      )}
                      {row.people.map((p) => (
                        <div key={p.id} className="flex items-start gap-2 text-xs">
                          <Mail className="h-3 w-3 text-[#E8662C] shrink-0 mt-0.5" />
                          <div className="flex-1 min-w-0">
                            <p className="font-medium truncate">
                              {p.first_name} {p.last_name}
                              {p.title && <span className="text-muted-foreground font-normal"> — {p.title}</span>}
                            </p>
                            {p.email && (
                              <a
                                href={`mailto:${p.email}`}
                                className="text-[#E8662C] hover:underline truncate block text-[10px]"
                                onClick={(e) => e.stopPropagation()}
                              >
                                {p.email}
                              </a>
                            )}
                            {p.linkedin_url && (
                              <a
                                href={p.linkedin_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-[#0A66C2] hover:underline truncate block text-[10px] flex items-center gap-1"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <Linkedin className="h-2.5 w-2.5" /> {p.linkedin_url}
                              </a>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {done && (
            <div className="border-t pt-3 flex items-center justify-between gap-3 shrink-0">
              <p className="text-sm text-muted-foreground">
                {totalImported > 0
                  ? `${totalImported} decision maker salvat${totalImported === 1 ? "o" : "i"}.`
                  : "Nessun nuovo decision maker salvato."}
              </p>
              <div className="flex items-center gap-2">
                {onPushToCampaign && pushableCompanyIds.length > 0 && (
                  <Button
                    size="sm"
                    className="gap-1.5"
                    onClick={() => {
                      onPushToCampaign(pushableCompanyIds);
                      handleOpen(false);
                    }}
                  >
                    <Star className="h-3.5 w-3.5" />
                    Aggiungi DM a campagna ({pushableCompanyIds.length})
                  </Button>
                )}
                <Button variant="outline" size="sm" onClick={() => handleOpen(false)}>Chiudi</Button>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function StatusIcon({ status }: { status: CompanyRowState["status"] }) {
  switch (status) {
    case "pending":
      return <div className="h-3.5 w-3.5 rounded-full border-2 border-muted shrink-0" />;
    case "running":
      return <Loader2 className="h-3.5 w-3.5 animate-spin text-[#E8662C] shrink-0" />;
    case "done":
      return <CheckCircle className="h-3.5 w-3.5 text-emerald-500 shrink-0" />;
    case "error":
      return <XCircle className="h-3.5 w-3.5 text-red-500 shrink-0" />;
  }
}
