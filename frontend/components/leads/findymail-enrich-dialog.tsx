"use client";

import { useState } from "react";
import {
  Mail, Loader2, CheckCircle, XCircle, ChevronDown, ChevronRight, Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
  checked: number;
  enriched_count: number;
  skipped_no_email_found: number;
  people: FoundPerson[];
  error?: string;
  expanded: boolean;
}

interface FindymailEnrichDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  companies: Company[];
  onCompleted?: () => void;
}

/**
 * "Findymail" badge — small visual marker so the integration is recognisable.
 * Findymail's brand mark uses a tilted envelope; we render it as the lucide
 * Mail icon with the brand-coloured pill behind it.
 */
function FindymailBadge() {
  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-[#FFE9DA] text-[#E8662C] border border-[#E8662C]/30">
      <Mail className="h-2.5 w-2.5" />
      Findymail
    </span>
  );
}

export function FindymailEnrichDialog({
  open, onOpenChange, companies, onCompleted,
}: FindymailEnrichDialogProps) {
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

  const start = async () => {
    if (companies.length === 0) return;

    const initial: CompanyRowState[] = companies.map((c) => ({
      company: c,
      status: "pending",
      checked: 0,
      enriched_count: 0,
      skipped_no_email_found: 0,
      people: [],
      expanded: false,
    }));
    setRows(initial);
    setRunning(true);
    setDone(false);

    // Sequential — Findymail charges per match and rate-limits per second; the
    // backend already loops over Persons per company, but processing companies
    // serially keeps the UI updates smooth.
    const updated = [...initial];
    for (let i = 0; i < companies.length; i += 1) {
      updated[i] = { ...updated[i], status: "running" };
      setRows([...updated]);
      try {
        const r = await api.findymailEnrichDecisionMakers(companies[i].id);
        updated[i] = {
          ...updated[i],
          status: "done",
          checked: r.checked,
          enriched_count: r.enriched_count,
          skipped_no_email_found: r.skipped_no_email_found,
          people: r.people,
          expanded: r.enriched_count > 0,
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
  const totalEnriched = rows.reduce((acc, r) => acc + r.enriched_count, 0);
  const totalChecked = rows.reduce((acc, r) => acc + r.checked, 0);
  const progress = rows.length > 0 ? Math.round((completedCount / rows.length) * 100) : 0;

  const toggleExpand = (idx: number) =>
    setRows((prev) => {
      const n = [...prev];
      n[idx] = { ...n[idx], expanded: !n[idx].expanded };
      return n;
    });

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogContent className="sm:max-w-[680px] max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5 text-[#E8662C]" />
            Trova email decision maker
            <FindymailBadge />
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4 flex-1 overflow-hidden">
          {!running && !done && (
            <div className="space-y-3">
              <div className="rounded-md border bg-muted/40 p-3 text-xs space-y-1.5 text-muted-foreground">
                <p>
                  Per ogni decision maker collegato all&apos;azienda <strong>senza email</strong>, Findymail prova a trovarla:
                </p>
                <ol className="list-decimal pl-5 space-y-0.5">
                  <li>Cerca per <code className="text-[10px] px-1 rounded bg-muted">linkedin_url</code> se presente</li>
                  <li>Fallback su nome + dominio email aziendale</li>
                </ol>
                <p>
                  L&apos;email trovata viene salvata sulla scheda Person. Costo Findymail:{" "}
                  <span className="font-medium">~1 credito per match riuscito</span>.
                </p>
              </div>

              <div className="rounded-md border bg-card p-3 text-sm">
                <p>
                  <span className="font-medium">{companies.length}</span> aziend{companies.length === 1 ? "a" : "e"} da processare.
                </p>
                <p className="text-muted-foreground text-xs mt-0.5">
                  L&apos;arricchimento è una tantum: i contatti che hanno già un&apos;email vengono saltati.
                </p>
              </div>

              {companies.length === 0 ? (
                <p className="text-sm text-muted-foreground italic">Nessuna azienda selezionata.</p>
              ) : (
                <Button onClick={start} className="gap-2 bg-[#E8662C] hover:bg-[#E8662C]/90 text-white">
                  <Sparkles className="h-4 w-4" />
                  Avvia Findymail ({companies.length})
                </Button>
              )}
            </div>
          )}

          {(running || done) && rows.length > 0 && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>
                  {completedCount} / {rows.length} completate
                  {done ? ` — ${totalEnriched} email trovate su ${totalChecked} contatti` : ""}
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
                      <Badge variant="secondary" className="text-[10px]">
                        {row.enriched_count > 0
                          ? `+${row.enriched_count} email`
                          : row.checked > 0
                          ? `0/${row.checked} trovate`
                          : "0 candidati"}
                      </Badge>
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
                      {row.status === "done" && row.people.length === 0 && (
                        <p className="text-xs text-muted-foreground italic">
                          {row.checked === 0
                            ? "Nessun decision maker senza email da arricchire."
                            : `Findymail non ha trovato email per ${row.checked} candidat${row.checked === 1 ? "o" : "i"}.`}
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
                {totalEnriched > 0
                  ? `${totalEnriched} email salvate sui Person.`
                  : "Nessuna email trovata."}
              </p>
              <Button variant="outline" onClick={() => handleOpen(false)}>Chiudi</Button>
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
