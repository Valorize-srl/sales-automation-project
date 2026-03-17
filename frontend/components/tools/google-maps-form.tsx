"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, Search } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { ToolResultsTable } from "./tool-results-table";
import type { ToolSearchResponse } from "@/types";

const MAPS_COLUMNS = [
  { key: "name", label: "Nome" },
  { key: "category", label: "Categoria" },
  { key: "address", label: "Indirizzo" },
  { key: "phone", label: "Telefono" },
  { key: "website", label: "Sito Web" },
  { key: "rating", label: "Rating" },
];

interface Props {
  clientTag?: string;
}

export function GoogleMapsForm({ clientTag }: Props) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [results, setResults] = useState<ToolSearchResponse | null>(null);

  const handleImport = async (items: Record<string, unknown>[]) => {
    setImporting(true);
    try {
      const res = await api.toolsImportLeads({ results: items, import_type: "companies", client_tag: clientTag });
      toast({ title: "Importazione completata", description: res.message });
    } catch (err: any) {
      toast({ title: "Errore", description: err?.message || "Import fallito", variant: "destructive" });
    } finally {
      setImporting(false);
    }
  };

  const handleExportCsv = async (items: Record<string, unknown>[]) => {
    try {
      const res = await api.toolsGenerateCsv({ results: items });
      const raw = atob(res.content_base64);
      const blob = new Blob([raw], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = res.filename || "google-maps.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      toast({ title: "Errore CSV", description: err?.message, variant: "destructive" });
    }
  };

  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [maxResults, setMaxResults] = useState(20);

  const handleSearch = async () => {
    if (!query.trim()) {
      toast({ title: "Inserisci una query", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const data = await api.toolsGoogleMapsSearch({
        query: query.trim(),
        location: location.trim() || undefined,
        max_results: maxResults,
        client_tag: clientTag,
      });
      setResults(data);
      toast({ title: `${data.total} attivita' trovate` });
    } catch (err: any) {
      toast({ title: "Errore", description: err?.message || "Ricerca fallita", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2">
          <Label className="text-xs">Cosa cerchi?</Label>
          <Input placeholder="Ristoranti, studi commercialisti, hotel..." value={query} onChange={(e) => setQuery(e.target.value)} className="mt-1" />
        </div>
        <div>
          <Label className="text-xs">Dove?</Label>
          <Input placeholder="Milano, Roma..." value={location} onChange={(e) => setLocation(e.target.value)} className="mt-1" />
        </div>
        <div>
          <Label className="text-xs">Max risultati</Label>
          <Input type="number" min={1} max={100} value={maxResults} onChange={(e) => setMaxResults(Number(e.target.value))} className="mt-1" />
        </div>
      </div>

      <Button onClick={handleSearch} disabled={loading} className="gap-2 w-full">
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
        Cerca su Google Maps
      </Button>

      {results && results.results.length > 0 && (
        <div className="pt-2 border-t">
          <ToolResultsTable
            results={results.results}
            columns={MAPS_COLUMNS}
            onImport={(items) => handleImport(items)}
            onExportCsv={(items) => handleExportCsv(items)}
            importType="companies"
            importing={importing}
          />
          {results.cost_usd > 0 && (
            <p className="text-xs text-muted-foreground mt-2">Costo: ${results.cost_usd.toFixed(3)}</p>
          )}
        </div>
      )}
    </div>
  );
}
