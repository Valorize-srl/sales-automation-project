"use client";

import { useEffect, useState } from "react";
import { Sparkles, Loader2 } from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { CompanyScoreResponse, ICP } from "@/types";

interface ScoreCompaniesDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedCompanyIds?: number[];
  totalCompanyCount: number;
  onCompleted?: (result: CompanyScoreResponse) => void;
}

export function ScoreCompaniesDialog({
  open, onOpenChange, selectedCompanyIds, totalCompanyCount, onCompleted,
}: ScoreCompaniesDialogProps) {
  const [icps, setIcps] = useState<ICP[]>([]);
  const [loadingIcps, setLoadingIcps] = useState(false);
  const [selectedIcpId, setSelectedIcpId] = useState<string>("");
  const [scoring, setScoring] = useState(false);
  const [result, setResult] = useState<CompanyScoreResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setResult(null);
      setError(null);
      return;
    }
    setLoadingIcps(true);
    api.getICPs()
      .then((data) => setIcps(data.icps || []))
      .catch((e) => setError(`Failed to load ICPs: ${e.message ?? e}`))
      .finally(() => setLoadingIcps(false));
  }, [open]);

  const targetCount = selectedCompanyIds && selectedCompanyIds.length > 0
    ? selectedCompanyIds.length
    : totalCompanyCount;

  const targetLabel = selectedCompanyIds && selectedCompanyIds.length > 0
    ? `${selectedCompanyIds.length} aziende selezionate`
    : `tutte le ${totalCompanyCount} aziende`;

  const onRun = async () => {
    if (!selectedIcpId) return;
    setScoring(true);
    setError(null);
    try {
      const r = await api.scoreCompanies(
        parseInt(selectedIcpId, 10),
        selectedCompanyIds && selectedCompanyIds.length > 0 ? selectedCompanyIds : undefined,
      );
      setResult(r);
      onCompleted?.(r);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(`Scoring failed: ${msg}`);
    } finally {
      setScoring(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            Score companies con ICP
          </DialogTitle>
        </DialogHeader>

        {!result ? (
          <div className="space-y-4 py-2">
            <div>
              <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Target
              </label>
              <p className="text-sm pt-1">{targetLabel} verranno scoreggiate.</p>
            </div>

            <div>
              <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                ICP
              </label>
              {loadingIcps ? (
                <p className="text-sm text-muted-foreground py-2">Caricamento ICP…</p>
              ) : icps.length === 0 ? (
                <p className="text-sm text-muted-foreground py-2">
                  Nessun ICP esistente. Creane uno dalla pagina Chat.
                </p>
              ) : (
                <Select value={selectedIcpId} onValueChange={setSelectedIcpId}>
                  <SelectTrigger className="mt-1">
                    <SelectValue placeholder="Scegli un ICP…" />
                  </SelectTrigger>
                  <SelectContent>
                    {icps.map((icp) => (
                      <SelectItem key={icp.id} value={String(icp.id)}>
                        {icp.name}{icp.industry ? ` — ${icp.industry}` : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            <div className="rounded-md bg-muted/50 p-3 text-xs text-muted-foreground">
              <strong>Cosa succede</strong>: Claude valuta ogni azienda in base all&apos;ICP, assegna
              <span className="font-medium"> tier A/B/C</span> e <span className="font-medium">score 0–100</span>,
              e crea task di enrichment per i tier A/B. Costo stimato ~ <span className="font-medium">€0,01–0,05</span> ogni 100 aziende.
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>
        ) : (
          <div className="space-y-3 py-2">
            <div className="rounded-md border p-4 bg-emerald-50 border-emerald-200">
              <p className="text-sm font-semibold text-emerald-900">Score completato</p>
              <p className="text-xs text-emerald-700 mt-1">
                {result.scored_count} aziende scoreggiate, {result.enrichment_tasks_created} task di enrichment create.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">Tier A</p>
                <p className="text-2xl font-bold text-emerald-600">{result.tier_a}</p>
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">Tier B</p>
                <p className="text-2xl font-bold text-amber-600">{result.tier_b}</p>
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">Tier C</p>
                <p className="text-2xl font-bold text-muted-foreground">{result.tier_c}</p>
              </div>
            </div>
            <div className="text-xs text-muted-foreground space-y-0.5">
              <p>Token in: {result.input_tokens.toLocaleString()} · out: {result.output_tokens.toLocaleString()}</p>
              <p>Costo: ${result.cost_usd.toFixed(4)}</p>
            </div>
          </div>
        )}

        <DialogFooter>
          {!result ? (
            <>
              <Button variant="outline" onClick={() => onOpenChange(false)} disabled={scoring}>
                Annulla
              </Button>
              <Button onClick={onRun} disabled={!selectedIcpId || scoring || icps.length === 0}>
                {scoring ? (
                  <><Loader2 className="h-3 w-3 mr-1 animate-spin" /> Scoring in corso…</>
                ) : (
                  <><Sparkles className="h-3 w-3 mr-1" /> Avvia scoring</>
                )}
              </Button>
            </>
          ) : (
            <Button onClick={() => onOpenChange(false)}>Chiudi</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
