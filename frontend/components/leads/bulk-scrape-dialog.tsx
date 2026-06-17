"use client";

import { useMemo, useRef, useState } from "react";
import {
  Globe, Loader2, Mail, Linkedin, CheckCircle, AlertCircle,
  Save, XCircle, ChevronDown, ChevronRight, Square,
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
  /** Preview mode (manual save per row). Used for hand-picked small selections. */
  companies?: Company[];
  /** Bulk mode (server-side enrich-batch, auto-saved to DB). Used when the
   *  user picked "Select all matching" on a large filtered set. */
  companyIds?: number[];
  onCompleted?: () => void;
}

// Server-side bulk enrichment runs in chunks; the backend's enrich-batch is
// already async-concurrent inside each chunk (max_concurrent=15).
// In-flight chunks paralleli (PARALLEL_CHUNKS=2) raddoppiano il throughput
// senza saturare i pool HTTP outbound del backend: 2 × 15 = 30 outbound
// contemporanei al picco.
const BULK_CHUNK_SIZE = 50;
const BULK_MAX_CONCURRENT = 15;
const PARALLEL_CHUNKS = 2;

interface BulkProgress {
  processed: number;
  enriched: number;
  failed: number;
  skipped: number;
  total: number;
}

export function BulkScrapeDialog({ open, onOpenChange, companies, companyIds, onCompleted }: BulkScrapeDialogProps) {
  // Bulk mode is selected when companyIds is provided. companies prop is
  // the small-selection preview path.
  const mode: "bulk" | "preview" = companyIds && companyIds.length > 0 ? "bulk" : "preview";
  const companiesProp = useMemo(() => companies ?? [], [companies]);
  const withWebsite = companiesProp.filter((c) => c.website);
  const withoutWebsite = companiesProp.filter((c) => !c.website);

  // Preview mode state
  const [rows, setRows] = useState<CompanyScrapeState[]>([]);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const [savingAll, setSavingAll] = useState(false);

  // Bulk mode state
  const [bulk, setBulk] = useState<BulkProgress>({ processed: 0, enriched: 0, failed: 0, skipped: 0, total: 0 });
  const stopRequestedRef = useRef(false);

  const resetState = () => {
    setRows([]);
    setRunning(false);
    setDone(false);
    setSavingAll(false);
    setBulk({ processed: 0, enriched: 0, failed: 0, skipped: 0, total: 0 });
    stopRequestedRef.current = false;
  };

  const handleOpen = (isOpen: boolean) => {
    if (!isOpen) resetState();
    onOpenChange(isOpen);
  };

  /** Bulk mode: send chunks of ids to the server-side enricher. Each call
   *  writes results directly to the DB, so closing the dialog mid-run still
   *  preserves all progress already made. Rilanciando lo stesso filtro le
   *  aziende già completate vengono skippate dal backend (auto-resume).
   *
   *  Chunks vengono lanciati a wave: PARALLEL_CHUNKS chunk in volo
   *  contemporaneamente. setBulk((prev) => ...) è race-safe in React 18:
   *  ogni callback vede la latest committed state, niente lost updates. */
  const runOneChunk = async (chunk: number[]) => {
    try {
      const resp = await api.enrichCompaniesBatch(chunk, false, BULK_MAX_CONCURRENT);
      setBulk((prev) => ({
        ...prev,
        processed: prev.processed + chunk.length,
        enriched: prev.enriched + (resp.enriched ?? 0),
        failed: prev.failed + (resp.failed ?? 0),
        skipped: prev.skipped + (resp.skipped ?? 0),
      }));
    } catch {
      // Whole chunk failed (network/server error). Count the chunk as
      // failed and keep going.
      setBulk((prev) => ({
        ...prev,
        processed: prev.processed + chunk.length,
        failed: prev.failed + chunk.length,
      }));
    }
  };

  const startBulkEnrichment = async () => {
    if (!companyIds || companyIds.length === 0) return;
    stopRequestedRef.current = false;
    setRunning(true);
    setDone(false);
    setBulk({ processed: 0, enriched: 0, failed: 0, skipped: 0, total: companyIds.length });

    // Precompute all chunks once.
    const chunks: number[][] = [];
    for (let i = 0; i < companyIds.length; i += BULK_CHUNK_SIZE) {
      chunks.push(companyIds.slice(i, i + BULK_CHUNK_SIZE));
    }

    // Process PARALLEL_CHUNKS wave at a time.
    for (let i = 0; i < chunks.length; i += PARALLEL_CHUNKS) {
      if (stopRequestedRef.current) break;
      const wave = chunks.slice(i, i + PARALLEL_CHUNKS);
      await Promise.all(wave.map(runOneChunk));
    }

    setRunning(false);
    setDone(true);
    onCompleted?.();
  };

  const requestStop = () => {
    stopRequestedRef.current = true;
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
    // Send everything the scraper found — the backend decides what to merge:
    // every email goes into generic_emails (dedup), the canonical LinkedIn
    // /company/ URL replaces a non-canonical one, etc.
    if (row.result.emails.length === 0 && !row.result.linkedin_url) return;
    await api.saveScrapedDataToCompany(row.company.id, {
      emails: row.result.emails,
      linkedin_url: row.result.linkedin_url ?? null,
    });
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
    // Considered "savable" whenever the scraper returned any data: the backend
    // takes care of dedup + best-canonical-LinkedIn picking.
    return row.result.emails.length > 0 || !!row.result.linkedin_url;
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

  // Bulk-mode UI: no per-row preview, just counters + progress bar.
  // The backend writes results directly to DB so we don't need to render
  // emails/linkedin for every row.
  if (mode === "bulk") {
    const total = companyIds!.length;
    const pct = total > 0 ? Math.round((bulk.processed / total) * 100) : 0;
    return (
      <Dialog open={open} onOpenChange={handleOpen}>
        <DialogContent className="sm:max-w-[560px] max-h-[85vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Globe className="h-5 w-5 text-primary" />
              Scraping in batch — {total.toLocaleString("it-IT")} aziende
            </DialogTitle>
          </DialogHeader>

          <div className="flex flex-col gap-4 flex-1 overflow-hidden">
            {!running && !done && (
              <div className="space-y-3">
                <div className="rounded-md border bg-muted/40 p-3 text-sm space-y-1.5">
                  <p>
                    Verranno arricchite fino a <span className="font-medium">{total.toLocaleString("it-IT")}</span> aziende.
                  </p>
                  <p className="text-muted-foreground text-xs">
                    Lo scraping gira lato server in chunk da {BULK_CHUNK_SIZE}.
                    Le email e i profili LinkedIn trovati vengono salvati direttamente in
                    DB. Puoi chiudere il dialog: i dati già scrapati restano salvati e
                    rilanciando lo stesso filtro le aziende completate vengono saltate
                    automaticamente (auto-resume).
                  </p>
                </div>
                <Button onClick={startBulkEnrichment} className="gap-2">
                  <Globe className="h-4 w-4" />
                  Avvia scraping ({total.toLocaleString("it-IT")} aziende)
                </Button>
              </div>
            )}

            {(running || done) && (
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>
                      {bulk.processed.toLocaleString("it-IT")} / {total.toLocaleString("it-IT")} processate
                    </span>
                    <span>{pct}%</span>
                  </div>
                  <Progress value={pct} className="h-2" />
                </div>

                <div className="grid grid-cols-3 gap-2 text-center text-xs">
                  <div
                    className="rounded-md border bg-emerald-50 dark:bg-emerald-950/30 p-2"
                    title="Aziende processate dallo scraper in questa sessione. Quelle che avevano email pubbliche sul sito sono state salvate in DB; le altre hanno completato il tentativo ma non avevano email visibili."
                  >
                    <p className="text-emerald-700 dark:text-emerald-300 font-bold text-lg">
                      {bulk.enriched.toLocaleString("it-IT")}
                    </p>
                    <p className="text-emerald-700 dark:text-emerald-400">arricchite</p>
                  </div>
                  <div
                    className="rounded-md border bg-amber-50 dark:bg-amber-950/30 p-2"
                    title="Aziende già scrapate con email salvate negli ultimi 7 giorni — niente da rifare, ci risparmiamo il tempo."
                  >
                    <p className="text-amber-700 dark:text-amber-300 font-bold text-lg">
                      {bulk.skipped.toLocaleString("it-IT")}
                    </p>
                    <p className="text-amber-700 dark:text-amber-400">saltate</p>
                  </div>
                  <div
                    className="rounded-md border bg-red-50 dark:bg-red-950/30 p-2"
                    title="Aziende dove lo scraper ha avuto un errore: sito irraggiungibile, timeout, certificato SSL invalido, 403 da WAF, ecc."
                  >
                    <p className="text-red-700 dark:text-red-300 font-bold text-lg">
                      {bulk.failed.toLocaleString("it-IT")}
                    </p>
                    <p className="text-red-700 dark:text-red-400">fallite</p>
                  </div>
                </div>
                <p className="text-[10px] text-muted-foreground leading-snug">
                  <strong>Saltate</strong> = già scrapate con email negli ultimi 7 giorni (auto-resume).
                  Le <strong>fallite</strong> verranno ritentate al prossimo Avvia.
                </p>

                {running && (
                  <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Scraping in corso…
                    <Button size="sm" variant="ghost" className="h-7 gap-1.5 text-xs ml-2" onClick={requestStop}>
                      <Square className="h-3 w-3" /> Stop
                    </Button>
                  </div>
                )}
                {done && (
                  <p className="text-sm text-center text-emerald-600 dark:text-emerald-400 flex items-center justify-center gap-1.5">
                    <CheckCircle className="h-4 w-4" />
                    Scraping completato.
                  </p>
                )}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    );
  }

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
