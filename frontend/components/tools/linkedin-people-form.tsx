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

const PEOPLE_COLUMNS = [
  { key: "name", label: "Nome" },
  { key: "title", label: "Ruolo" },
  { key: "company", label: "Azienda" },
  { key: "location", label: "Luogo" },
  { key: "linkedin_url", label: "LinkedIn" },
];

interface Props {
  clientTag?: string;
}

export function LinkedInPeopleForm({ clientTag }: Props) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [results, setResults] = useState<ToolSearchResponse | null>(null);

  const [keywords, setKeywords] = useState("");
  const [company, setCompany] = useState("");
  const [location, setLocation] = useState("");
  const [maxResults, setMaxResults] = useState(10);

  const handleImport = async (items: Record<string, unknown>[]) => {
    setImporting(true);
    try {
      const res = await api.toolsImportLeads({ results: items, import_type: "people", client_tag: clientTag });
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
      a.download = res.filename || "linkedin-people.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      toast({ title: "Errore CSV", description: err?.message, variant: "destructive" });
    }
  };

  const handleSearch = async () => {
    if (!keywords.trim()) {
      toast({ title: "Inserisci un ruolo/keyword", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const data = await api.toolsLinkedInSearchPeople({
        keywords: keywords.trim(),
        company: company.trim() || undefined,
        location: location.trim() || undefined,
        max_results: maxResults,
        client_tag: clientTag,
      });
      setResults(data);
      toast({ title: `${data.total} profili trovati` });
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
          <Label className="text-xs">Ruolo / Keywords *</Label>
          <Input placeholder="CEO, Sales Director, CTO..." value={keywords} onChange={(e) => setKeywords(e.target.value)} className="mt-1" />
        </div>
        <div>
          <Label className="text-xs">Azienda</Label>
          <Input placeholder="Nome azienda..." value={company} onChange={(e) => setCompany(e.target.value)} className="mt-1" />
        </div>
        <div>
          <Label className="text-xs">Location</Label>
          <Input placeholder="Milano, Italia..." value={location} onChange={(e) => setLocation(e.target.value)} className="mt-1" />
        </div>
        <div>
          <Label className="text-xs">Max risultati</Label>
          <Input type="number" min={1} max={25} value={maxResults} onChange={(e) => setMaxResults(Number(e.target.value))} className="mt-1" />
        </div>
      </div>

      <Button onClick={handleSearch} disabled={loading} className="gap-2 w-full">
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
        Cerca su LinkedIn
      </Button>

      {results && results.results.length > 0 && (
        <div className="pt-2 border-t">
          <ToolResultsTable
            results={results.results}
            columns={PEOPLE_COLUMNS}
            onImport={(items) => handleImport(items)}
            onExportCsv={(items) => handleExportCsv(items)}
            importType="people"
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
