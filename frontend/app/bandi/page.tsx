"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Landmark,
  RefreshCw,
  Loader2,
  ExternalLink,
  Clock,
  Archive,
  Building2,
  Search,
  ChevronDown,
  ChevronUp,
  Tag,
  MapPin,
  Banknote,
  Brain,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import type { Bando, BandoStats, BandoMatch } from "@/types";

const SOURCE_LABELS: Record<string, string> = {
  mimit: "MIMIT",
  invitalia: "Invitalia",
  mase: "MASE",
  fasi: "FASI",
  unioncamere: "Unioncamere",
  incentivi_gov: "Incentivi.gov",
};

const SOURCE_COLORS: Record<string, string> = {
  mimit: "bg-blue-100 text-blue-800",
  invitalia: "bg-green-100 text-green-800",
  mase: "bg-emerald-100 text-emerald-800",
  fasi: "bg-purple-100 text-purple-800",
  unioncamere: "bg-orange-100 text-orange-800",
  incentivi_gov: "bg-teal-100 text-teal-800",
};

const STATUS_COLORS: Record<string, string> = {
  new: "bg-yellow-100 text-yellow-800",
  analyzed: "bg-blue-100 text-blue-800",
  expired: "bg-red-100 text-red-700",
  archived: "bg-gray-100 text-gray-400",
};

const STATUS_LABELS: Record<string, string> = {
  new: "Nuovo",
  analyzed: "Analizzato",
  expired: "Scaduto",
  archived: "Archiviato",
};

function daysUntil(dateStr: string): number {
  const deadline = new Date(dateStr);
  const now = new Date();
  return Math.ceil((deadline.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
}

function formatAmount(min: number | null, max: number | null): string {
  const fmt = (n: number) => {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
    return n.toLocaleString("it-IT");
  };
  if (min && max) return `${fmt(min)} - ${fmt(max)} \u20ac`;
  if (max) return `fino a ${fmt(max)} \u20ac`;
  if (min) return `da ${fmt(min)} \u20ac`;
  return "";
}

export default function BandiPage() {
  const [bandi, setBandi] = useState<Bando[]>([]);
  const [stats, setStats] = useState<BandoStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [total, setTotal] = useState(0);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  // Expanded bando
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Matches dialog
  const { toast } = useToast();

  const [matchesDialog, setMatchesDialog] = useState<{
    open: boolean;
    bandoId: number;
    bandoTitle: string;
    matches: BandoMatch[];
    loading: boolean;
  }>({ open: false, bandoId: 0, bandoTitle: "", matches: [], loading: false });

  const loadBandi = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (searchQuery) params.search = searchQuery;
      if (sourceFilter) params.source = sourceFilter;
      if (statusFilter) params.status = statusFilter;
      const data = await api.getBandi(params);
      setBandi(data.bandi);
      setTotal(data.total);
    } catch (err) {
      console.error("Failed to load bandi:", err);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, sourceFilter, statusFilter]);

  const loadStats = useCallback(async () => {
    try {
      const data = await api.getBandoStats();
      setStats(data);
    } catch (err) {
      console.error("Failed to load stats:", err);
    }
  }, []);

  useEffect(() => {
    loadBandi();
    loadStats();
  }, [loadBandi, loadStats]);

  // Auto-polling every 5 minutes
  useEffect(() => {
    const interval = setInterval(() => {
      loadBandi(true);
      loadStats();
    }, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [loadBandi, loadStats]);

  const handleFetch = async () => {
    setFetching(true);
    try {
      const result = await api.fetchBandi();
      toast({
        title: "Bandi aggiornati",
        description: result.message,
      });
      await loadBandi();
      await loadStats();
      // Reload again after 15s to pick up AI analysis results
      setTimeout(async () => {
        await loadBandi(true);
        await loadStats();
      }, 15000);
    } catch (err) {
      console.error("Fetch failed:", err);
      toast({
        title: "Errore",
        description: "Errore durante il recupero dei bandi",
        variant: "destructive",
      });
    } finally {
      setFetching(false);
    }
  };

  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});

  const handleArchive = async (bandoId: number) => {
    setActionLoading((prev) => ({ ...prev, [`archive-${bandoId}`]: true }));
    try {
      await api.archiveBando(bandoId);
      toast({ title: "Bando archiviato" });
      await loadBandi(true);
      await loadStats();
    } catch (err: any) {
      console.error("Archive failed:", err);
      toast({ title: "Errore", description: err?.message || "Archiviazione fallita", variant: "destructive" });
    } finally {
      setActionLoading((prev) => ({ ...prev, [`archive-${bandoId}`]: false }));
    }
  };

  const handleAnalyze = async (bandoId: number) => {
    setActionLoading((prev) => ({ ...prev, [`analyze-${bandoId}`]: true }));
    try {
      const updated = await api.analyzeBando(bandoId);
      toast({ title: "Analisi completata", description: "Il bando è stato analizzato con AI" });
      // Update the bando in-place so it doesn't disappear from current view
      setBandi((prev) => prev.map((b) => (b.id === bandoId ? updated : b)));
      await loadStats();
    } catch (err: any) {
      console.error("Analyze failed:", err);
      toast({ title: "Errore", description: err?.message || "Analisi AI fallita", variant: "destructive" });
    } finally {
      setActionLoading((prev) => ({ ...prev, [`analyze-${bandoId}`]: false }));
    }
  };

  const handleShowMatches = async (bandoId: number, title: string) => {
    setMatchesDialog({ open: true, bandoId, bandoTitle: title, matches: [], loading: true });
    try {
      const data = await api.getBandoMatches(bandoId);
      setMatchesDialog((prev) => ({ ...prev, matches: data.matches, loading: false }));
    } catch (err) {
      console.error("Failed to load matches:", err);
      setMatchesDialog((prev) => ({ ...prev, loading: false }));
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Landmark className="h-6 w-6" />
            Bandi & Agevolazioni
          </h1>
          <p className="text-sm text-muted-foreground">
            Monitoraggio bandi e incentivi pubblici con analisi AI
          </p>
        </div>
        <Button
          onClick={handleFetch}
          disabled={fetching}
          className="gap-2"
        >
          {fetching ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          {fetching ? "Aggiornamento..." : "Aggiorna Bandi"}
        </Button>
      </div>

      {/* KPI Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="border rounded-lg p-4">
            <p className="text-sm text-muted-foreground">Totale Bandi</p>
            <p className="text-2xl font-bold">{stats.total}</p>
          </div>
          <div className="border rounded-lg p-4">
            <p className="text-sm text-muted-foreground">Nuovi</p>
            <p className="text-2xl font-bold text-yellow-600">{stats.new_count}</p>
          </div>
          <div className="border rounded-lg p-4">
            <p className="text-sm text-muted-foreground">Analizzati</p>
            <p className="text-2xl font-bold text-blue-600">{stats.analyzed_count}</p>
          </div>
          <div className="border rounded-lg p-4">
            <p className="text-sm text-muted-foreground">In Scadenza (&lt;30gg)</p>
            <p className="text-2xl font-bold text-red-600">{stats.expiring_soon}</p>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Cerca bandi..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
            onKeyDown={(e) => e.key === "Enter" && loadBandi()}
          />
        </div>
        <Select value={sourceFilter} onValueChange={(v) => { setSourceFilter(v === "all" ? "" : v); }}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="Tutte le fonti" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tutte le fonti</SelectItem>
            {Object.entries(SOURCE_LABELS).map(([key, label]) => (
              <SelectItem key={key} value={key}>{label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v === "all" ? "" : v); }}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="Tutti gli stati" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tutti gli stati</SelectItem>
            <SelectItem value="new">Nuovo</SelectItem>
            <SelectItem value="analyzed">Analizzato</SelectItem>
            <SelectItem value="expired">Scaduto</SelectItem>
            <SelectItem value="archived">Archiviato</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Bandi List */}
      {loading ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : bandi.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <Landmark className="h-12 w-12 mx-auto mb-3 opacity-30" />
          <p className="text-lg font-medium">Nessun bando trovato</p>
          <p className="text-sm mt-1">
            Clicca &quot;Aggiorna Bandi&quot; per recuperare i bandi dalle fonti configurate
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {bandi.map((bando) => {
            const isExpanded = expandedId === bando.id;
            const deadlineDays = bando.deadline ? daysUntil(bando.deadline) : null;

            return (
              <div
                key={bando.id}
                className="border rounded-lg p-4 hover:bg-muted/30 transition-colors"
              >
                {/* Top row */}
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <Badge variant="outline" className={SOURCE_COLORS[bando.source] || ""}>
                        {SOURCE_LABELS[bando.source] || bando.source}
                      </Badge>
                      <Badge variant="outline" className={STATUS_COLORS[bando.status] || ""}>
                        {STATUS_LABELS[bando.status] || bando.status}
                      </Badge>
                      {bando.funding_type && (
                        <Badge variant="outline" className="bg-indigo-50 text-indigo-700">
                          <Banknote className="h-3 w-3 mr-1" />
                          {bando.funding_type}
                        </Badge>
                      )}
                      {deadlineDays !== null && deadlineDays > 0 && (
                        <Badge
                          variant="outline"
                          className={
                            deadlineDays <= 7
                              ? "bg-red-100 text-red-800"
                              : deadlineDays <= 30
                              ? "bg-orange-100 text-orange-800"
                              : "bg-green-100 text-green-800"
                          }
                        >
                          <Clock className="h-3 w-3 mr-1" />
                          {deadlineDays}gg
                        </Badge>
                      )}
                    </div>
                    <h3 className="font-medium text-sm leading-tight">
                      <a
                        href={bando.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:underline"
                      >
                        {bando.title}
                        <ExternalLink className="inline h-3 w-3 ml-1 opacity-50" />
                      </a>
                    </h3>
                    {bando.ai_summary && (
                      <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                        {bando.ai_summary}
                      </p>
                    )}
                    {/* Amount */}
                    {(bando.amount_min || bando.amount_max) && (
                      <p className="text-sm font-medium text-green-700 mt-1">
                        {formatAmount(bando.amount_min, bando.amount_max)}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    {bando.status === "analyzed" && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="gap-1 text-xs"
                        onClick={() => handleShowMatches(bando.id, bando.title)}
                      >
                        <Building2 className="h-3 w-3" />
                        Match
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setExpandedId(isExpanded ? null : bando.id)}
                    >
                      {isExpanded ? (
                        <ChevronUp className="h-4 w-4" />
                      ) : (
                        <ChevronDown className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </div>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="mt-3 pt-3 border-t space-y-3">
                    {bando.target_companies && (
                      <div>
                        <p className="text-xs font-medium text-muted-foreground mb-1">Aziende Target</p>
                        <p className="text-sm">{bando.target_companies}</p>
                      </div>
                    )}
                    {bando.ateco_codes && bando.ateco_codes.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-muted-foreground mb-1">Codici ATECO</p>
                        <div className="flex flex-wrap gap-1">
                          {bando.ateco_codes.map((code) => (
                            <Badge key={code} variant="secondary" className="text-xs">
                              <Tag className="h-3 w-3 mr-1" />
                              {code}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    {bando.regions && bando.regions.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-muted-foreground mb-1">Regioni</p>
                        <div className="flex flex-wrap gap-1">
                          {bando.regions.map((r) => (
                            <Badge key={r} variant="secondary" className="text-xs">
                              <MapPin className="h-3 w-3 mr-1" />
                              {r}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    {bando.sectors && bando.sectors.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-muted-foreground mb-1">Settori</p>
                        <div className="flex flex-wrap gap-1">
                          {bando.sectors.map((s) => (
                            <Badge key={s} variant="outline" className="text-xs">
                              {s}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    {/* Date apertura e scadenza */}
                    <div className="flex flex-wrap gap-6">
                      {bando.opening_date && (
                        <div>
                          <p className="text-xs font-medium text-muted-foreground mb-1">Data Apertura</p>
                          <p className="text-sm">
                            {new Date(bando.opening_date).toLocaleDateString("it-IT", {
                              day: "numeric",
                              month: "long",
                              year: "numeric",
                            })}
                          </p>
                        </div>
                      )}
                      {bando.deadline && (
                        <div>
                          <p className="text-xs font-medium text-muted-foreground mb-1">Scadenza</p>
                          <p className="text-sm">
                            {new Date(bando.deadline).toLocaleDateString("it-IT", {
                              day: "numeric",
                              month: "long",
                              year: "numeric",
                            })}
                          </p>
                        </div>
                      )}
                      {!bando.opening_date && !bando.deadline && (
                        <div>
                          <p className="text-xs font-medium text-muted-foreground mb-1">Date</p>
                          <p className="text-sm text-muted-foreground">Non disponibili - analizza con AI per estrarre le date</p>
                        </div>
                      )}
                    </div>
                    <div className="flex gap-2 pt-1">
                      {bando.status !== "archived" && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="gap-1 text-xs"
                          disabled={!!actionLoading[`archive-${bando.id}`]}
                          onClick={() => handleArchive(bando.id)}
                        >
                          {actionLoading[`archive-${bando.id}`] ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Archive className="h-3 w-3" />
                          )}
                          Archivia
                        </Button>
                      )}
                      {bando.status !== "archived" && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="gap-1 text-xs"
                          disabled={!!actionLoading[`analyze-${bando.id}`]}
                          onClick={() => handleAnalyze(bando.id)}
                        >
                          {actionLoading[`analyze-${bando.id}`] ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Brain className="h-3 w-3" />
                          )}
                          {bando.status === "new" ? "Analizza con AI" : "Ri-analizza con AI"}
                        </Button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          {/* Pagination info */}
          <p className="text-sm text-muted-foreground text-center pt-2">
            {bandi.length} di {total} bandi
          </p>
        </div>
      )}

      {/* Matches Dialog */}
      <Dialog
        open={matchesDialog.open}
        onOpenChange={(open) => setMatchesDialog((prev) => ({ ...prev, open }))}
      >
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle className="text-base">
              Aziende compatibili
            </DialogTitle>
            <p className="text-sm text-muted-foreground line-clamp-1">
              {matchesDialog.bandoTitle}
            </p>
          </DialogHeader>
          {matchesDialog.loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : matchesDialog.matches.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              Nessuna azienda compatibile trovata nel database
            </p>
          ) : (
            <div className="space-y-2 max-h-[400px] overflow-y-auto">
              {matchesDialog.matches.map((match) => (
                <div key={match.company_id} className="border rounded p-3">
                  <p className="font-medium text-sm">{match.name}</p>
                  {match.industry && (
                    <p className="text-xs text-muted-foreground">{match.industry}</p>
                  )}
                  <p className="text-xs text-primary mt-1">{match.match_reason}</p>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
