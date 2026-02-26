"use client";

import { useState } from "react";
import { Download, Users, Building2, Loader2, ExternalLink, Sparkles, Mail, MailX, AlertTriangle, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { api } from "@/lib/api";
import { ApolloPersonResult, ApolloCompanyResult, ApolloSearchResponse } from "@/types";

function downloadCSV(data: ApolloSearchResponse) {
  const isPeople = data.search_type === "people";
  const rows = data.results as (ApolloPersonResult | ApolloCompanyResult)[];

  const headers = isPeople
    ? ["First Name", "Last Name", "Location", "Title", "Company", "Email", "LinkedIn", "Website", "Industry"]
    : ["Name", "Industry", "Size", "Website", "LinkedIn", "Location", "Email"];

  const lines = rows.map((r) => {
    if (isPeople) {
      const p = r as ApolloPersonResult;
      return [p.first_name, p.last_name, p.location, p.title, p.company, p.email, p.linkedin_url, p.website, p.industry];
    } else {
      const c = r as ApolloCompanyResult;
      return [c.name, c.industry, c.size, c.website, c.linkedin_url, c.location, c.email];
    }
  });

  const csvContent = [headers, ...lines]
    .map((row) =>
      row.map((cell) => `"${String(cell ?? "").replace(/"/g, '""')}"`).join(",")
    )
    .join("\n");

  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `apollo-${data.search_type}-${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

interface Props {
  data: ApolloSearchResponse;
  clientTag?: string;
  autoEnrich?: boolean;
  onImported?: (target: "people" | "companies", count: number) => void;
}

export function ApolloPreviewCard({ data, clientTag, autoEnrich, onImported }: Props) {
  const [importing, setImporting] = useState<"people" | "companies" | null>(null);
  const [importResult, setImportResult] = useState<string | null>(null);
  const [enriching, setEnriching] = useState(false);
  const [enrichResult, setEnrichResult] = useState<string | null>(null);
  const [creditsExhausted, setCreditsExhausted] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  // Local copy of results so we can merge enriched data
  const [localResults, setLocalResults] = useState<(ApolloPersonResult | ApolloCompanyResult)[]>(
    data.results as (ApolloPersonResult | ApolloCompanyResult)[]
  );

  const isPeople = data.search_type === "people";
  const results = localResults;

  // Count un-enriched people for display
  const unenrichedCount = isPeople
    ? (results as ApolloPersonResult[]).filter((p) => !p.is_enriched).length
    : 0;

  const selectedCount = selectedIds.size;
  const allSelected = isPeople && results.length > 0 && selectedIds.size === results.length;

  const toggleSelect = (idx: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(results.map((_, i) => i)));
    }
  };

  const mergeEnrichedData = (res: import("@/types").ApolloEnrichResponse) => {
    setLocalResults((prev) => {
      const updated = [...prev];
      for (const idx of Array.from(selectedIds)) {
        const person = updated[idx] as ApolloPersonResult;
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

  const handleEnrichSelected = async (source: "apollo" | "apify" = "apollo") => {
    if (selectedCount === 0) return;
    setEnriching(true);
    setEnrichResult(null);
    setCreditsExhausted(false);
    try {
      const people = Array.from(selectedIds).map((idx) => {
        const p = results[idx] as ApolloPersonResult;
        return {
          id: p.apollo_id,
          first_name: p.first_name,
          last_name: p.last_name,
          organization_name: p.company,
        };
      });
      const res = await api.apolloEnrichPeople(people, source);

      // Check if Apollo credits are exhausted
      if (res.error === "credits_exhausted") {
        setCreditsExhausted(true);
        setEnrichResult(res.message || "Crediti Apollo esauriti.");
        return;
      }

      mergeEnrichedData(res);

      const sourceLabel = res.source === "apify" ? "Apify" : "Apollo";
      const costInfo = res.source === "apify" && res.apify_cost_usd
        ? ` (~$${res.apify_cost_usd.toFixed(3)})`
        : ` (${res.credits_consumed} credits)`;
      setEnrichResult(`${sourceLabel}: Enriched ${res.enriched_count} people${costInfo}`);
      setSelectedIds(new Set());
      setCreditsExhausted(false);
    } catch (err) {
      setEnrichResult(`Enrichment failed: ${err instanceof Error ? err.message : "unknown error"}`);
    } finally {
      setEnriching(false);
    }
  };

  const handleImport = async (target: "people" | "companies") => {
    setImporting(target);
    setImportResult(null);
    try {
      const res = await api.apolloImport(
        results as unknown as Record<string, unknown>[],
        target,
        clientTag,
        target === "companies" ? autoEnrich : undefined
      );
      const msg = `Imported ${res.imported}${res.duplicates_skipped ? `, ${res.duplicates_skipped} duplicates skipped` : ""}${res.errors ? `, ${res.errors} errors` : ""}`;
      setImportResult(msg);
      onImported?.(target, res.imported);
    } catch (err) {
      setImportResult(`Import failed: ${err instanceof Error ? err.message : "unknown error"}`);
    } finally {
      setImporting(null);
    }
  };

  return (
    <div className="rounded-xl border bg-card shadow-sm overflow-hidden my-2">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-muted/40">
        <div className="flex items-center gap-2">
          {isPeople ? (
            <Users className="h-4 w-4 text-blue-500" />
          ) : (
            <Building2 className="h-4 w-4 text-violet-500" />
          )}
          <span className="text-sm font-semibold">
            Apollo Preview — {data.returned} {isPeople ? "people" : "companies"}
            {data.total > data.returned && (
              <span className="text-muted-foreground font-normal">
                {" "}of {data.total.toLocaleString()} total
              </span>
            )}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* Enrich Selected button - only for people with unenriched results */}
          {isPeople && unenrichedCount > 0 && (
            <Button
              variant="default"
              size="sm"
              className="h-7 gap-1.5 text-xs"
              disabled={enriching || selectedCount === 0}
              onClick={() => handleEnrichSelected("apollo")}
            >
              {enriching ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Sparkles className="h-3 w-3" />
              )}
              {enriching
                ? "Enriching…"
                : selectedCount > 0
                  ? `Enrich ${selectedCount} (${selectedCount} credits)`
                  : "Select to Enrich"}
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            className="h-7 gap-1.5 text-xs"
            onClick={() => downloadCSV({ ...data, results: localResults as ApolloPersonResult[] | ApolloCompanyResult[] })}
          >
            <Download className="h-3 w-3" />
            CSV
          </Button>
        </div>
      </div>

      {/* Usage Stats */}
      {(data.usage || data.credits_consumed !== undefined) && (
        <div className="flex items-center gap-6 px-4 py-2 border-b bg-muted/5 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">Apollo Credits:</span>
            <span className="font-mono font-semibold text-blue-600">
              {data.usage?.apollo_credits ?? data.credits_consumed ?? 0}
            </span>
          </div>

          {data.usage?.claude_tokens && (
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">Claude Tokens:</span>
              <span className="font-mono font-semibold text-violet-600">
                {data.usage.claude_tokens.total_tokens.toLocaleString()}
              </span>
              <span className="text-muted-foreground text-[10px]">
                ({data.usage.claude_tokens.input_tokens.toLocaleString()} in / {data.usage.claude_tokens.output_tokens.toLocaleString()} out)
              </span>
            </div>
          )}

          {data.usage?.estimated_cost_usd && (
            <div className="flex items-center gap-2 ml-auto">
              <span className="text-muted-foreground">Est. Cost:</span>
              <span className="font-mono font-semibold text-green-600">
                ${data.usage.estimated_cost_usd.total_usd.toFixed(4)}
              </span>
              <span className="text-muted-foreground text-[10px]">
                (A: ${data.usage.estimated_cost_usd.apollo_usd.toFixed(2)} + C: ${data.usage.estimated_cost_usd.claude_usd.toFixed(4)})
              </span>
            </div>
          )}
        </div>
      )}

      {/* Credits exhausted banner with Apify fallback */}
      {creditsExhausted && (
        <div className="flex items-center gap-2 px-4 py-2 border-b bg-amber-50 text-xs text-amber-800">
          <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
          <span className="flex-1">Crediti Apollo esauriti. Arricchisci con Apify (~$0.005/lead)?</span>
          <Button
            variant="default"
            size="sm"
            className="h-6 gap-1 text-xs bg-amber-600 hover:bg-amber-700"
            disabled={enriching || selectedCount === 0}
            onClick={() => handleEnrichSelected("apify")}
          >
            {enriching ? <Loader2 className="h-3 w-3 animate-spin" /> : <Zap className="h-3 w-3" />}
            Usa Apify ({selectedCount})
          </Button>
        </div>
      )}

      {/* Enrichment result banner */}
      {enrichResult && !creditsExhausted && (
        <div className="px-4 py-2 border-b bg-blue-50 text-xs text-blue-700">
          {enrichResult}
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b bg-muted/20">
              {isPeople && (
                <th className="px-3 py-2 w-8">
                  <Checkbox
                    checked={allSelected}
                    onCheckedChange={toggleSelectAll}
                    aria-label="Select all"
                  />
                </th>
              )}
              {isPeople ? (
                <>
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">Name</th>
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">Location</th>
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">Title</th>
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">Company</th>
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">Industry</th>
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">Email</th>
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">LinkedIn</th>
                </>
              ) : (
                <>
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">Name</th>
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">Industry</th>
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">Size</th>
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">Location</th>
                  <th className="text-left px-3 py-2 font-medium text-muted-foreground">Website</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {results.map((row, i) => (
              <tr key={i} className="border-b last:border-0 hover:bg-muted/20 transition-colors">
                {isPeople && (
                  <td className="px-3 py-2">
                    <Checkbox
                      checked={selectedIds.has(i)}
                      onCheckedChange={() => toggleSelect(i)}
                      aria-label={`Select ${(row as ApolloPersonResult).first_name}`}
                    />
                  </td>
                )}
                {isPeople ? (
                  <>
                    <td className="px-3 py-2 font-medium">
                      {(row as ApolloPersonResult).first_name} {(row as ApolloPersonResult).last_name}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">{(row as ApolloPersonResult).location ?? "—"}</td>
                    <td className="px-3 py-2 text-muted-foreground">{(row as ApolloPersonResult).title ?? "—"}</td>
                    <td className="px-3 py-2">{(row as ApolloPersonResult).company ?? "—"}</td>
                    <td className="px-3 py-2 text-muted-foreground">{(row as ApolloPersonResult).industry ?? "—"}</td>
                    <td className="px-3 py-2 text-xs">
                      {(row as ApolloPersonResult).email ? (
                        <span className="flex items-center gap-1 text-green-600">
                          <Mail className="h-3 w-3" />
                          {(row as ApolloPersonResult).email}
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-muted-foreground/50">
                          <MailX className="h-3 w-3" />
                          No email
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      {(row as ApolloPersonResult).linkedin_url ? (
                        <a
                          href={(row as ApolloPersonResult).linkedin_url!}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-500 hover:underline flex items-center gap-0.5"
                        >
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      ) : (
                        "—"
                      )}
                    </td>
                  </>
                ) : (
                  <>
                    <td className="px-3 py-2 font-medium">{(row as ApolloCompanyResult).name}</td>
                    <td className="px-3 py-2 text-muted-foreground">{(row as ApolloCompanyResult).industry ?? "—"}</td>
                    <td className="px-3 py-2">{(row as ApolloCompanyResult).size ?? "—"}</td>
                    <td className="px-3 py-2 text-muted-foreground">{(row as ApolloCompanyResult).location ?? "—"}</td>
                    <td className="px-3 py-2">
                      {(row as ApolloCompanyResult).website ? (
                        <a
                          href={(row as ApolloCompanyResult).website!}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-500 hover:underline flex items-center gap-0.5"
                        >
                          <ExternalLink className="h-3 w-3" />
                          <span className="truncate max-w-[100px]">
                            {(row as ApolloCompanyResult).website!.replace(/https?:\/\//, "")}
                          </span>
                        </a>
                      ) : (
                        "—"
                      )}
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer actions */}
      <div className="flex items-center gap-2 px-4 py-3 border-t bg-muted/10 flex-wrap">
        <span className="text-xs text-muted-foreground mr-auto">Import to:</span>
        <Button
          size="sm"
          variant="outline"
          className="h-7 gap-1.5 text-xs"
          disabled={importing !== null}
          onClick={() => handleImport("people")}
        >
          {importing === "people" ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Users className="h-3 w-3" />
          )}
          People
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="h-7 gap-1.5 text-xs"
          disabled={importing !== null}
          onClick={() => handleImport("companies")}
        >
          {importing === "companies" ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Building2 className="h-3 w-3" />
          )}
          Companies
        </Button>
        {importResult && (
          <span className="text-xs text-muted-foreground w-full pt-1">{importResult}</span>
        )}
      </div>
    </div>
  );
}
