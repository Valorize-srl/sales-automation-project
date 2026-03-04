"use client";

import { useState } from "react";
import { Search, Sparkles, Download, Loader2, ExternalLink, UserPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api";
import { Company, ApolloPersonResult, ApolloEnrichResponse } from "@/types";

const SENIORITY_OPTIONS = [
  { value: "entry", label: "Entry" },
  { value: "senior", label: "Senior" },
  { value: "manager", label: "Manager" },
  { value: "director", label: "Director" },
  { value: "vp", label: "VP" },
  { value: "c_suite", label: "C-Suite" },
];

interface FindPeopleDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  company: Company | null;
  onImported?: () => void;
}

export function FindPeopleDialog({ open, onOpenChange, company, onImported }: FindPeopleDialogProps) {
  const [titles, setTitles] = useState("");
  const [seniority, setSeniority] = useState<string>("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<ApolloPersonResult[]>([]);
  const [total, setTotal] = useState(0);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [enriching, setEnriching] = useState(false);
  const [enrichResult, setEnrichResult] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setTitles("");
    setSeniority("");
    setSearching(false);
    setResults([]);
    setTotal(0);
    setSelectedIds(new Set());
    setEnriching(false);
    setEnrichResult(null);
    setImporting(false);
    setImportResult(null);
    setError(null);
  };

  const handleOpenChange = (v: boolean) => {
    if (!v) reset();
    onOpenChange(v);
  };

  const handleSearch = async () => {
    if (!company) return;
    setSearching(true);
    setError(null);
    setResults([]);
    setSelectedIds(new Set());
    setEnrichResult(null);
    setImportResult(null);
    try {
      const params: { titles?: string[]; seniorities?: string[]; per_page?: number } = { per_page: 25 };
      if (titles.trim()) params.titles = titles.split(",").map((t) => t.trim()).filter(Boolean);
      if (seniority) params.seniorities = [seniority];
      const res = await api.findPeopleAtCompany(company.id, params);
      setResults(res.results as unknown as ApolloPersonResult[]);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setSearching(false);
    }
  };

  const toggleSelect = (idx: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === results.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(results.map((_, i) => i)));
    }
  };

  const selectedCount = selectedIds.size;
  const allSelected = results.length > 0 && selectedIds.size === results.length;

  const mergeEnrichedData = (res: ApolloEnrichResponse) => {
    setResults((prev) => {
      const updated = [...prev];
      for (const idx of Array.from(selectedIds)) {
        const person = updated[idx];
        const enriched = person.apollo_id ? res.enriched[person.apollo_id] : null;
        if (enriched) {
          const locationParts = [enriched.city, enriched.state, enriched.country].filter(Boolean);
          updated[idx] = {
            ...person,
            first_name: enriched.first_name || person.first_name,
            last_name: enriched.last_name || person.last_name,
            email: enriched.email || person.email,
            phone: enriched.phone || enriched.direct_phone || person.phone,
            linkedin_url: enriched.linkedin_url || person.linkedin_url,
            location: locationParts.length > 0 ? locationParts.join(", ") : person.location,
            is_enriched: true,
          };
        }
      }
      return updated;
    });
  };

  const handleEnrich = async () => {
    if (selectedCount === 0) return;
    setEnriching(true);
    setEnrichResult(null);
    try {
      const people = Array.from(selectedIds).map((idx) => {
        const p = results[idx];
        return {
          id: p.apollo_id,
          first_name: p.first_name,
          last_name: p.last_name,
          organization_name: p.company,
        };
      });
      const res = await api.apolloEnrichPeople(people);
      mergeEnrichedData(res);
      setEnrichResult(`Enriched ${res.enriched_count} people (${res.credits_consumed} credits)`);
      setSelectedIds(new Set());
    } catch (err) {
      setEnrichResult(`Enrichment failed: ${err instanceof Error ? err.message : "unknown error"}`);
    } finally {
      setEnriching(false);
    }
  };

  const handleImport = async () => {
    const toImport = selectedCount > 0
      ? Array.from(selectedIds).map((idx) => results[idx])
      : results;

    const enriched = toImport.filter((p) => p.is_enriched);
    if (enriched.length === 0) {
      setImportResult("Enrich at least one person before importing.");
      return;
    }

    setImporting(true);
    setImportResult(null);
    try {
      const res = await api.apolloImport(
        enriched as unknown as Record<string, unknown>[],
        "people",
        company?.client_tag || undefined,
      );
      setImportResult(`Imported ${res.imported}${res.duplicates_skipped ? `, ${res.duplicates_skipped} duplicates skipped` : ""}`);
      onImported?.();
    } catch (err) {
      setImportResult(`Import failed: ${err instanceof Error ? err.message : "unknown error"}`);
    } finally {
      setImporting(false);
    }
  };

  const enrichedCount = results.filter((r) => r.is_enriched).length;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[720px] max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Find People at {company?.name || "Company"}</DialogTitle>
        </DialogHeader>
        <Separator />

        {/* Search form */}
        <div className="flex items-center gap-2 pt-1">
          <Input
            placeholder="Job titles (comma-separated)..."
            value={titles}
            onChange={(e) => setTitles(e.target.value)}
            className="h-8 text-sm flex-1"
            onKeyDown={(e) => { if (e.key === "Enter") handleSearch(); }}
          />
          <Select value={seniority || undefined} onValueChange={(v) => setSeniority(v === "__all__" ? "" : v)}>
            <SelectTrigger className="w-[120px] h-8 text-xs">
              <SelectValue placeholder="Seniority" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All levels</SelectItem>
              {SENIORITY_OPTIONS.map((s) => (
                <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button size="sm" onClick={handleSearch} disabled={searching} className="gap-1 h-8">
            {searching ? <Loader2 className="h-3 w-3 animate-spin" /> : <Search className="h-3 w-3" />}
            Search
          </Button>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        {/* Results */}
        {results.length > 0 && (
          <div className="flex flex-col flex-1 min-h-0">
            <div className="flex items-center justify-between py-1">
              <span className="text-xs text-muted-foreground">
                {results.length} of {total} people found
                {enrichedCount > 0 && ` \u00b7 ${enrichedCount} enriched`}
              </span>
              <div className="flex items-center gap-1.5">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 gap-1 text-xs"
                  disabled={selectedCount === 0 || enriching}
                  onClick={handleEnrich}
                >
                  {enriching ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
                  {enriching ? "Enriching..." : selectedCount > 0 ? `Enrich ${selectedCount} (${selectedCount} credits)` : "Select to Enrich"}
                </Button>
                <Button
                  size="sm"
                  variant="default"
                  className="h-7 gap-1 text-xs"
                  disabled={enrichedCount === 0 || importing}
                  onClick={handleImport}
                >
                  {importing ? <Loader2 className="h-3 w-3 animate-spin" /> : <UserPlus className="h-3 w-3" />}
                  {importing ? "Importing..." : `Import${enrichedCount > 0 ? ` (${enrichedCount})` : ""}`}
                </Button>
              </div>
            </div>

            {enrichResult && (
              <p className="text-xs text-blue-600 py-1">{enrichResult}</p>
            )}
            {importResult && (
              <p className="text-xs text-green-600 py-1">{importResult}</p>
            )}

            <div className="overflow-auto flex-1 rounded border">
              <table className="w-full text-xs">
                <thead className="bg-muted sticky top-0">
                  <tr>
                    <th className="px-2 py-1.5 w-8">
                      <Checkbox checked={allSelected} onCheckedChange={toggleSelectAll} />
                    </th>
                    <th className="px-2 py-1.5 text-left font-medium">Name</th>
                    <th className="px-2 py-1.5 text-left font-medium">Title</th>
                    <th className="px-2 py-1.5 text-left font-medium">Email</th>
                    <th className="px-2 py-1.5 text-left font-medium">Location</th>
                    <th className="px-2 py-1.5 text-left font-medium">LinkedIn</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((p, i) => (
                    <tr key={i} className={`border-t ${p.is_enriched ? "bg-green-50/50" : ""}`}>
                      <td className="px-2 py-1.5">
                        <Checkbox checked={selectedIds.has(i)} onCheckedChange={() => toggleSelect(i)} />
                      </td>
                      <td className="px-2 py-1.5 font-medium whitespace-nowrap">
                        {p.first_name} {p.last_name}
                      </td>
                      <td className="px-2 py-1.5 truncate max-w-[160px]" title={p.title || ""}>
                        {p.title || "—"}
                      </td>
                      <td className="px-2 py-1.5">
                        {p.email ? (
                          <span className="text-green-600">{p.email}</span>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="px-2 py-1.5 truncate max-w-[120px]">{p.location || "—"}</td>
                      <td className="px-2 py-1.5">
                        {p.linkedin_url ? (
                          <a href={p.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline flex items-center gap-0.5">
                            <ExternalLink className="h-3 w-3" /> Link
                          </a>
                        ) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {results.length === 0 && !searching && !error && (
          <p className="text-sm text-muted-foreground text-center py-6">
            Search Apollo for people at this company. Free search, 1 credit per enrichment.
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}
