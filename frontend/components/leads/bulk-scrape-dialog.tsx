"use client";

import { useState } from "react";
import {
  Globe, Loader2, Mail, Linkedin, CheckCircle, AlertCircle,
  Save, XCircle, ChevronDown, ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import { Company, WebsiteScrapeResult } from "@/types";

interface CompanyScrapeState {
  company: Company;
  status: "pending" | "scraping" | "done" | "error" | "saved";
  result?: WebsiteScrapeResult;
  error?: string;
  expanded: boolean;
}

interface BulkScrapeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  companies: Company[];
  onCompleted?: () => void;
}

export function BulkScrapeDialog({ open, onOpenChange, companies, onCompleted }: BulkScrapeDialogProps) {
  const withWebsite = companies.filter((c) => c.website);
  const withoutWebsite = companies.filter((c) => !c.website);

  const [rows, setRows] = useState<CompanyScrapeState[]>([]);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const [savingAll, setSavingAll] = useState(false);

  const resetState = () => {
    setRows([]);
    setRunning(false);
    setDone(false);
    setSavingAll(false);
  };

  const handleOpen = (isOpen: boolean) => {
    if (!isOpen) resetState();
    onOpenChange(isOpen);
  };

  const startScraping = async () => {
    const initial: CompanyScrapeState[] = withWebsite.map((c) => ({
      company: c,
      status: "pending",
      expanded: false,
    }));
    setRows(initial);
    setRunning(true);
    setDone(false);

    // Process in batches of 5 to show live progress
    const BATCH = 5;
    const updated = [...initial];

    for (let i = 0; i < withWebsite.length; i += BATCH) {
      const batch = withWebsite.slice(i, i + BATCH);

      // Mark batch as scraping
      batch.forEach((_, bi) => {
        updated[i + bi] = { ...updated[i + bi], status: "scraping" };
      });
      setRows([...updated]);

      try {
        const results = await api.scrapeWebsitesBulk(
          batch.map((c) => c.website!),
          5,
        );
        results.forEach((res, bi) => {
          const idx = i + bi;
          if (res.error) {
            updated[idx] = { ...updated[idx], status: "error", error: res.error };
          } else {
            updated[idx] = { ...updated[idx], status: "done", result: res };
          }
        });
      } catch (e: unknown) {
        batch.forEach((_, bi) => {
          updated[i + bi] = {
            ...updated[i + bi],
            status: "error",
            error: e instanceof Error ? e.message : "Errore",
          };
        });
      }
      setRows([...updated]);
    }

    setRunning(false);
    setDone(true);
  };

  const saveRow = async (idx: number) => {
    const row = rows[idx];
    if (!row.result) return;
    const updates: Record<string, string | null> = {};
    if (row.result.emails.length > 0 && !row.company.email) {
      updates.email = row.result.emails[0];
    }
    if (row.result.linkedin_url && !row.company.linkedin_url) {
      updates.linkedin_url = row.result.linkedin_url;
    }
    if (Object.keys(updates).length === 0) return;
    await api.updateCompany(row.company.id, updates);
    setRows((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], status: "saved" };
      return next;
    });
  };

  const saveAll = async () => {
    setSavingAll(true);
    const toSave = rows
      .map((r, i) => ({ ...r, idx: i }))
      .filter((r) => r.status === "done" && hasNewData(r));
    await Promise.all(toSave.map((r) => saveRow(r.idx)));
    setSavingAll(false);
    onCompleted?.();
  };

  const hasNewData = (row: CompanyScrapeState) => {
    if (!row.result) return false;
    return (
      (row.result.emails.length > 0 && !row.company.email) ||
      (!!row.result.linkedin_url && !row.company.linkedin_url)
    );
  };

  const completedCount = rows.filter((r) => r.status === "done" || r.status === "saved" || r.status === "error").length;
  const savableCount = rows.filter((r) => r.status === "done" && hasNewData(r)).length;
  const progress = rows.length > 0 ? Math.round((completedCount / rows.length) * 100) : 0;

  const toggleExpand = (idx: number) => {
    setRows((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], expanded: !next[idx].expanded };
      return next;
    });
  };

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogContent className="sm:max-w-[680px] max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5 text-primary" />
            Scraping siti web aziende
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4 flex-1 overflow-hidden">
          {/* Info pre-start */}
          {!running && !done && (
            <div className="space-y-3">
              <div className="rounded-md border bg-muted/40 p-3 text-sm space-y-1">
                <p>
                  <span className="font-medium">{withWebsite.length}</span> aziende con sito web verranno analizzate.
                </p>
                {withoutWebsite.length > 0 && (
                  <p className="text-muted-foreground">
                    {withoutWebsite.length} aziende senza sito web verranno saltate.
                  </p>
                )}
                <p className="text-muted-foreground text-xs">
                  Lo scraper naviga fino a 8 pagine per sito cercando email e pagina LinkedIn aziendale.
                </p>
              </div>
              {withWebsite.length === 0 ? (
                <p className="text-sm text-muted-foreground italic">Nessuna azienda selezionata ha un sito web.</p>
              ) : (
                <Button onClick={startScraping} className="gap-2">
                  <Globe className="h-4 w-4" />
                  Avvia scraping ({withWebsite.length} siti)
                </Button>
              )}
            </div>
          )}

          {/* Progress bar */}
          {(running || done) && rows.length > 0 && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{completedCount} / {rows.length} analizzati</span>
                <span>{progress}%</span>
              </div>
              <Progress value={progress} className="h-1.5" />
            </div>
          )}

          {/* Results list */}
          {rows.length > 0 && (
            <div className="flex-1 overflow-y-auto space-y-1 pr-1">
              {rows.map((row, idx) => (
                <div key={row.company.id} className="rounded-md border text-sm">
                  {/* Row header */}
                  <button
                    className="flex items-center gap-2 w-full px-3 py-2 text-left hover:bg-accent/50 rounded-md"
                    onClick={() => toggleExpand(idx)}
                  >
                    <StatusIcon status={row.status} />
                    <span className="flex-1 font-medium truncate">{row.company.name}</span>
                    <span className="text-xs text-muted-foreground truncate max-w-[180px]">
                      {row.company.website}
                    </span>
                    {row.result && (
                      <div className="flex items-center gap-1.5 shrink-0">
                        {row.result.emails.length > 0 && (
                          <Badge variant="secondary" className="text-[10px] gap-0.5">
                            <Mail className="h-2.5 w-2.5" />
                            {row.result.emails.length}
                          </Badge>
                        )}
                        {row.result.linkedin_url && (
                          <Badge variant="secondary" className="text-[10px]">
                            <Linkedin className="h-2.5 w-2.5" />
                          </Badge>
                        )}
                      </div>
                    )}
                    {row.status === "done" || row.status === "saved" || row.status === "error"
                      ? (row.expanded ? <ChevronDown className="h-3.5 w-3.5 shrink-0" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0" />)
                      : null}
                  </button>

                  {/* Expanded detail */}
                  {row.expanded && (
                    <div className="px-3 pb-3 space-y-2 border-t pt-2">
                      {row.status === "error" && (
                        <p className="text-xs text-red-600 dark:text-red-400">{row.error}</p>
                      )}
                      {row.result && (
                        <>
                          {row.result.emails.length > 0 ? (
                            <div className="space-y-1">
                              <p className="text-xs font-medium flex items-center gap-1">
                                <Mail className="h-3 w-3 text-blue-500" /> Email trovate
                              </p>
                              <div className="flex flex-wrap gap-1">
                                {row.result.emails.map((e) => (
                                  <Badge key={e} variant="outline" className="text-[10px]">{e}</Badge>
                                ))}
                              </div>
                            </div>
                          ) : (
                            <p className="text-xs text-muted-foreground flex items-center gap-1">
                              <Mail className="h-3 w-3" /> Nessuna email trovata
                            </p>
                          )}
                          {row.result.linkedin_url ? (
                            <p className="text-xs flex items-center gap-1">
                              <Linkedin className="h-3 w-3 text-[#0A66C2]" />
                              <a
                                href={row.result.linkedin_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-[#0A66C2] hover:underline truncate"
                              >
                                {row.result.linkedin_url}
                              </a>
                            </p>
                          ) : (
                            <p className="text-xs text-muted-foreground flex items-center gap-1">
                              <Linkedin className="h-3 w-3" /> LinkedIn non trovato
                            </p>
                          )}
                          <p className="text-[10px] text-muted-foreground">
                            {row.result.pages_visited} pagine visitate
                          </p>
                          {row.status === "saved" ? (
                            <p className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
                              <CheckCircle className="h-3 w-3" /> Salvato
                            </p>
                          ) : hasNewData(row) ? (
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-6 text-xs gap-1"
                              onClick={() => saveRow(idx)}
                            >
                              <Save className="h-3 w-3" /> Salva
                            </Button>
                          ) : (
                            <p className="text-[10px] text-muted-foreground italic">Nessun dato nuovo da salvare</p>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Footer actions */}
          {done && savableCount > 0 && (
            <div className="border-t pt-3 flex items-center justify-between gap-3 shrink-0">
              <p className="text-sm text-muted-foreground">
                {savableCount} aziend{savableCount === 1 ? "a" : "e"} con dati nuovi da salvare
              </p>
              <Button onClick={saveAll} disabled={savingAll} className="gap-2">
                {savingAll ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Salva tutto
              </Button>
            </div>
          )}
          {done && savableCount === 0 && rows.length > 0 && (
            <p className="text-sm text-muted-foreground text-center shrink-0">
              Nessun dato nuovo da salvare.
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function StatusIcon({ status }: { status: CompanyScrapeState["status"] }) {
  switch (status) {
    case "pending":
      return <div className="h-3.5 w-3.5 rounded-full border-2 border-muted shrink-0" />;
    case "scraping":
      return <Loader2 className="h-3.5 w-3.5 animate-spin text-primary shrink-0" />;
    case "done":
      return <CheckCircle className="h-3.5 w-3.5 text-emerald-500 shrink-0" />;
    case "saved":
      return <CheckCircle className="h-3.5 w-3.5 text-blue-500 shrink-0" />;
    case "error":
      return <XCircle className="h-3.5 w-3.5 text-red-500 shrink-0" />;
  }
}
