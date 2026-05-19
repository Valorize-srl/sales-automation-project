"use client";

import { useState } from "react";
import {
  Loader2, CheckCircle, XCircle, ChevronDown, ChevronRight, Sparkles,
  Linkedin, Building2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import { Company } from "@/types";

interface CompanyRowState {
  company: Company;
  status: "pending" | "running" | "done" | "error";
  found: boolean;
  updated_fields: string[];
  matched: {
    name: string | null;
    domain: string | null;
    linkedin_url: string | null;
    industry: string | null;
    company_size: string | null;
    city: string | null;
    region: string | null;
    country: string | null;
  } | null;
  error?: string;
  expanded: boolean;
}

interface FindymailFindCompanyInfoDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  companies: Company[];
  onCompleted?: () => void;
}

export function FindymailFindCompanyInfoDialog({
  open, onOpenChange, companies, onCompleted,
}: FindymailFindCompanyInfoDialogProps) {
  const [rows, setRows] = useState<CompanyRowState[]>([]);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);

  const reset = () => { setRows([]); setRunning(false); setDone(false); };

  const handleOpen = (isOpen: boolean) => {
    if (!isOpen) reset();
    onOpenChange(isOpen);
  };

  const start = async () => {
    if (companies.length === 0) return;
    const initial: CompanyRowState[] = companies.map((c) => ({
      company: c,
      status: "pending",
      found: false,
      updated_fields: [],
      matched: null,
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
        const r = await api.findymailFindCompanyInfo(companies[i].id);
        updated[i] = {
          ...updated[i],
          status: "done",
          found: r.found,
          updated_fields: r.updated_fields,
          matched: r.matched,
          expanded: r.updated_fields.length > 0,
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
  const totalUpdated = rows.reduce((acc, r) => acc + r.updated_fields.length, 0);
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
            <Building2 className="h-5 w-5 text-[#E8662C]" />
            Trova info azienda (LinkedIn, settore, dominio)
            <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-[#FFE9DA] text-[#E8662C] border border-[#E8662C]/30">
              Findymail
            </span>
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4 flex-1 overflow-hidden">
          {!running && !done && (
            <div className="space-y-3">
              <div className="rounded-md border bg-muted/40 p-3 text-xs space-y-1.5 text-muted-foreground">
                <p>
                  Per ogni azienda Findymail viene interrogato con il segnale più preciso che abbiamo
                  (sito web &gt; LinkedIn URL &gt; nome) e restituisce le info aziendali.
                </p>
                <p>
                  <strong>Backfill</strong> dei campi mancanti (non sovrascrive):
                </p>
                <ul className="list-disc pl-5 space-y-0.5">
                  <li><code className="text-[10px] px-1 rounded bg-muted">linkedin_url</code> canonico (`/company/...`)</li>
                  <li><code className="text-[10px] px-1 rounded bg-muted">industry</code></li>
                  <li><code className="text-[10px] px-1 rounded bg-muted">location</code> (city, region, country)</li>
                  <li><code className="text-[10px] px-1 rounded bg-muted">email_domain</code></li>
                </ul>
                <p>Costo Findymail: gratis (la lookup company non consuma crediti).</p>
              </div>

              <div className="rounded-md border bg-card p-3 text-sm">
                <p>
                  <span className="font-medium">{companies.length}</span> aziend{companies.length === 1 ? "a" : "e"} da processare.
                </p>
              </div>

              {companies.length === 0 ? (
                <p className="text-sm text-muted-foreground italic">Nessuna azienda selezionata.</p>
              ) : (
                <Button onClick={start} className="gap-2 bg-[#E8662C] hover:bg-[#E8662C]/90 text-white">
                  <Sparkles className="h-4 w-4" />
                  Avvia ({companies.length})
                </Button>
              )}
            </div>
          )}

          {(running || done) && rows.length > 0 && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>
                  {completedCount} / {rows.length} completate — {totalUpdated} campi popolati
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
                        {row.updated_fields.length > 0
                          ? `+${row.updated_fields.length} ${row.updated_fields.length === 1 ? "campo" : "campi"}`
                          : row.found
                          ? "tutto già popolato"
                          : "non trovata"}
                      </Badge>
                    )}
                    {row.status === "done" || row.status === "error"
                      ? row.expanded
                        ? <ChevronDown className="h-3.5 w-3.5 shrink-0" />
                        : <ChevronRight className="h-3.5 w-3.5 shrink-0" />
                      : null}
                  </button>

                  {row.expanded && (
                    <div className="px-3 pb-3 space-y-1.5 border-t pt-2">
                      {row.status === "error" && (
                        <p className="text-xs text-red-600 dark:text-red-400">{row.error}</p>
                      )}
                      {row.status === "done" && !row.found && (
                        <p className="text-xs text-muted-foreground italic">
                          Findymail non ha info per questa azienda.
                        </p>
                      )}
                      {row.matched && (
                        <div className="space-y-1 text-xs">
                          {row.matched.linkedin_url && (
                            <p className="flex items-center gap-1.5">
                              <Linkedin className="h-3 w-3 text-[#0A66C2] shrink-0" />
                              <a
                                href={row.matched.linkedin_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-[#0A66C2] hover:underline truncate"
                                onClick={(e) => e.stopPropagation()}
                              >
                                {row.matched.linkedin_url}
                              </a>
                              {row.updated_fields.includes("linkedin_url") && (
                                <Badge variant="outline" className="text-[9px] px-1 py-0">salvato</Badge>
                              )}
                            </p>
                          )}
                          {row.matched.industry && (
                            <p>
                              <span className="text-muted-foreground">Settore:</span> {row.matched.industry}
                              {row.updated_fields.includes("industry") && (
                                <Badge variant="outline" className="text-[9px] px-1 py-0 ml-1.5">salvato</Badge>
                              )}
                            </p>
                          )}
                          {(row.matched.city || row.matched.region || row.matched.country) && (
                            <p>
                              <span className="text-muted-foreground">Località:</span>{" "}
                              {[row.matched.city, row.matched.region, row.matched.country].filter(Boolean).join(", ")}
                              {row.updated_fields.includes("location") && (
                                <Badge variant="outline" className="text-[9px] px-1 py-0 ml-1.5">salvato</Badge>
                              )}
                            </p>
                          )}
                          {row.matched.domain && (
                            <p>
                              <span className="text-muted-foreground">Dominio email:</span> <code className="text-[10px]">{row.matched.domain}</code>
                              {row.updated_fields.includes("email_domain") && (
                                <Badge variant="outline" className="text-[9px] px-1 py-0 ml-1.5">salvato</Badge>
                              )}
                            </p>
                          )}
                          {row.matched.company_size && (
                            <p>
                              <span className="text-muted-foreground">Dimensione:</span> {row.matched.company_size} dipendenti
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {done && (
            <div className="border-t pt-3 flex items-center justify-between gap-3 shrink-0">
              <p className="text-sm text-muted-foreground">
                {totalUpdated > 0
                  ? `${totalUpdated} ${totalUpdated === 1 ? "campo popolato" : "campi popolati"} totali.`
                  : "Nessun nuovo dato da salvare."}
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
