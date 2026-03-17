"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Globe } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { ToolResultsTable } from "./tool-results-table";
import type { ToolSearchResponse } from "@/types";

const SCRAPE_COLUMNS = [
  { key: "domain", label: "Dominio" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Telefono" },
];

interface Props {
  clientTag?: string;
}

export function WebsiteScraperForm({ clientTag }: Props) {
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
      a.download = res.filename || "scraper-results.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      toast({ title: "Errore CSV", description: err?.message, variant: "destructive" });
    }
  };
  const [urlsText, setUrlsText] = useState("");

  const handleScrape = async () => {
    const urls = urlsText
      .split("\n")
      .map((u) => u.trim())
      .filter((u) => u.startsWith("http"));
    if (urls.length === 0) {
      toast({ title: "Inserisci almeno un URL", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const data = await api.toolsScrapeWebsites({ urls, client_tag: clientTag });
      setResults(data);
      toast({ title: `Trovati contatti da ${data.total} domini` });
    } catch (err: any) {
      toast({ title: "Errore", description: err?.message || "Scraping fallito", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <Label className="text-xs">URLs (uno per riga)</Label>
        <Textarea
          placeholder={"https://www.example.com\nhttps://www.acme.it\n..."}
          value={urlsText}
          onChange={(e) => setUrlsText(e.target.value)}
          className="mt-1 min-h-[120px] font-mono text-xs"
        />
        <p className="text-xs text-muted-foreground mt-1">Max 50 URL per volta</p>
      </div>

      <Button onClick={handleScrape} disabled={loading} className="gap-2 w-full">
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Globe className="h-4 w-4" />}
        Estrai Contatti
      </Button>

      {results && results.results.length > 0 && (
        <div className="pt-2 border-t">
          <ToolResultsTable
            results={results.results}
            columns={SCRAPE_COLUMNS}
            onImport={(items) => handleImport(items)}
            onExportCsv={(items) => handleExportCsv(items)}
            importType="companies"
            importing={importing}
          />
        </div>
      )}
    </div>
  );
}
