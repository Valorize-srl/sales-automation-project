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

const SENIORITY_OPTIONS = ["entry", "senior", "manager", "director", "vp", "c_suite"];

interface Props {
  clientTag?: string;
}

const PEOPLE_COLUMNS = [
  { key: "first_name", label: "Nome" },
  { key: "last_name", label: "Cognome" },
  { key: "title", label: "Ruolo" },
  { key: "company", label: "Azienda" },
  { key: "email", label: "Email" },
  { key: "location", label: "Luogo" },
];

export function ApolloPeopleForm({ clientTag }: Props) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [results, setResults] = useState<ToolSearchResponse | null>(null);

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
      a.download = res.filename || "apollo-people.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      toast({ title: "Errore CSV", description: err?.message, variant: "destructive" });
    }
  };

  const [titles, setTitles] = useState("");
  const [locations, setLocations] = useState("");
  const [seniorities, setSeniorities] = useState<string[]>([]);
  const [orgKeywords, setOrgKeywords] = useState("");
  const [orgSizes, setOrgSizes] = useState("");
  const [keywords, setKeywords] = useState("");
  const [perPage, setPerPage] = useState(25);

  const handleSearch = async () => {
    setLoading(true);
    try {
      const data = await api.toolsSearchPeople({
        person_titles: titles ? titles.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
        person_locations: locations ? locations.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
        person_seniorities: seniorities.length ? seniorities : undefined,
        organization_keywords: orgKeywords ? orgKeywords.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
        organization_sizes: orgSizes ? orgSizes.split(",").map((s) => s.trim()).filter(Boolean) : undefined,
        keywords: keywords || undefined,
        per_page: perPage,
        client_tag: clientTag,
      });
      setResults(data);
      toast({ title: `${data.total} risultati trovati`, description: `Mostrati ${data.results.length}` });
    } catch (err: any) {
      toast({ title: "Errore", description: err?.message || "Ricerca fallita", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const toggleSeniority = (s: string) => {
    setSeniorities((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label className="text-xs">Job Titles (separati da virgola)</Label>
          <Input placeholder="CEO, CTO, Direttore..." value={titles} onChange={(e) => setTitles(e.target.value)} className="mt-1" />
        </div>
        <div>
          <Label className="text-xs">Locations (separati da virgola)</Label>
          <Input placeholder="Italy, Milan..." value={locations} onChange={(e) => setLocations(e.target.value)} className="mt-1" />
        </div>
        <div>
          <Label className="text-xs">Keywords azienda</Label>
          <Input placeholder="software, fintech..." value={orgKeywords} onChange={(e) => setOrgKeywords(e.target.value)} className="mt-1" />
        </div>
        <div>
          <Label className="text-xs">Dimensione azienda</Label>
          <Input placeholder="1-10, 11-50, 51-200..." value={orgSizes} onChange={(e) => setOrgSizes(e.target.value)} className="mt-1" />
        </div>
        <div className="col-span-2">
          <Label className="text-xs">Keywords generali</Label>
          <Input placeholder="Parole chiave..." value={keywords} onChange={(e) => setKeywords(e.target.value)} className="mt-1" />
        </div>
      </div>

      <div>
        <Label className="text-xs">Seniority</Label>
        <div className="flex flex-wrap gap-1.5 mt-1">
          {SENIORITY_OPTIONS.map((s) => (
            <button
              key={s}
              onClick={() => toggleSeniority(s)}
              className={`px-2 py-1 rounded text-xs border transition-colors ${
                seniorities.includes(s) ? "bg-primary text-primary-foreground border-primary" : "bg-background hover:bg-muted"
              }`}
            >
              {s.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <Label className="text-xs whitespace-nowrap">Risultati:</Label>
          <Input
            type="number"
            min={1}
            max={100}
            value={perPage}
            onChange={(e) => setPerPage(Number(e.target.value))}
            className="w-16 h-8"
          />
        </div>
        <Button onClick={handleSearch} disabled={loading} className="gap-2 flex-1">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          Cerca su Apollo
        </Button>
      </div>

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
          {results.credits_used > 0 && (
            <p className="text-xs text-muted-foreground mt-2">
              Crediti usati: {results.credits_used} (${results.cost_usd.toFixed(2)})
            </p>
          )}
        </div>
      )}
    </div>
  );
}
