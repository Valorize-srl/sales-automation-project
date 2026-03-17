"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Search } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { ToolResultsTable } from "./tool-results-table";
import type { ToolSearchResponse } from "@/types";

const COMPANY_COLUMNS = [
  { key: "name", label: "Azienda" },
  { key: "industry", label: "Settore" },
  { key: "employee_count", label: "Dipendenti" },
  { key: "headquarters", label: "Sede" },
  { key: "website", label: "Sito Web" },
];

interface Props {
  clientTag?: string;
}

export function LinkedInCompaniesForm({ clientTag }: Props) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [results, setResults] = useState<ToolSearchResponse | null>(null);

  const [namesText, setNamesText] = useState("");
  const [urlsText, setUrlsText] = useState("");

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
      a.download = res.filename || "linkedin-companies.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      toast({ title: "Errore CSV", description: err?.message, variant: "destructive" });
    }
  };

  const handleSearch = async () => {
    const names = namesText.split("\n").map((n) => n.trim()).filter(Boolean);
    const urls = urlsText.split("\n").map((u) => u.trim()).filter((u) => u.startsWith("http"));

    if (names.length === 0 && urls.length === 0) {
      toast({ title: "Inserisci nomi azienda o URL LinkedIn", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const data = await api.toolsLinkedInSearchCompanies({
        company_names: names.length > 0 ? names : undefined,
        company_urls: urls.length > 0 ? urls : undefined,
        client_tag: clientTag,
      });
      setResults(data);
      toast({ title: `${data.total} profili aziendali trovati` });
    } catch (err: any) {
      toast({ title: "Errore", description: err?.message || "Ricerca fallita", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <Label className="text-xs">Nomi aziende (uno per riga)</Label>
        <Textarea
          placeholder={"Acme Srl\nTech Corp\n..."}
          value={namesText}
          onChange={(e) => setNamesText(e.target.value)}
          className="mt-1 min-h-[80px] font-mono text-xs"
        />
      </div>
      <div>
        <Label className="text-xs">Oppure URL LinkedIn (uno per riga)</Label>
        <Textarea
          placeholder={"https://www.linkedin.com/company/acme\n..."}
          value={urlsText}
          onChange={(e) => setUrlsText(e.target.value)}
          className="mt-1 min-h-[80px] font-mono text-xs"
        />
      </div>

      <Button onClick={handleSearch} disabled={loading} className="gap-2 w-full">
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
        Cerca su LinkedIn
      </Button>

      {results && results.results.length > 0 && (
        <div className="pt-2 border-t">
          <ToolResultsTable
            results={results.results}
            columns={COMPANY_COLUMNS}
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
