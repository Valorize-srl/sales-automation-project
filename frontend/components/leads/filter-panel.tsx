"use client";

import { useState } from "react";
import { Filter, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { CompanyFilters } from "@/types";

interface Props {
  filters: CompanyFilters;
  onFiltersChange: (f: CompanyFilters) => void;
  industries: string[];
  customFieldKeys: string[];
}

const TIER_OPTIONS = [
  { value: "any", label: "Any" },
  { value: "A", label: "A" },
  { value: "B", label: "B" },
  { value: "C", label: "C" },
];

const STAGE_OPTIONS = [
  { value: "any", label: "Any" },
  { value: "new", label: "new" },
  { value: "enriched", label: "enriched" },
  { value: "ready_for_outreach", label: "ready_for_outreach" },
];

export function FilterPanel({ filters, onFiltersChange, industries, customFieldKeys }: Props) {
  const [open, setOpen] = useState(false);

  const set = (patch: Partial<CompanyFilters>) => onFiltersChange({ ...filters, ...patch });

  const setNum = (key: keyof CompanyFilters, v: string) => {
    const n = v === "" ? undefined : Number(v);
    set({ [key]: Number.isFinite(n as number) ? (n as number) : undefined } as Partial<CompanyFilters>);
  };

  const setBool = (key: keyof CompanyFilters, v: "any" | "yes" | "no") =>
    set({ [key]: v === "any" ? undefined : v === "yes" } as Partial<CompanyFilters>);

  const setSelect = (key: keyof CompanyFilters, v: string) =>
    set({ [key]: v === "any" || v === "" ? undefined : v } as Partial<CompanyFilters>);

  const setCf = (key: string, value: string) => {
    const cf = { ...(filters.cf || {}) };
    if (!value) {
      delete cf[key];
    } else {
      cf[key] = { contains: value };
    }
    set({ cf: Object.keys(cf).length > 0 ? cf : undefined });
  };

  const activeCount = (() => {
    const f = filters as Record<string, unknown>;
    let n = 0;
    Object.entries(f).forEach(([k, v]) => {
      if (k === "search") return;
      if (v === undefined || v === null || v === "" || v === "any") return;
      if (k === "cf") {
        n += Object.keys((v as Record<string, unknown>) || {}).length;
        return;
      }
      n += 1;
    });
    return n;
  })();

  const clearAll = () => onFiltersChange({ search: filters.search });

  if (!open) {
    return (
      <div className="flex items-center gap-2 mb-3">
        <Button variant="outline" size="sm" className="gap-1.5" onClick={() => setOpen(true)}>
          <Filter className="h-3.5 w-3.5" />
          Filters
          {activeCount > 0 && (
            <Badge variant="secondary" className="ml-1 text-[10px]">{activeCount}</Badge>
          )}
        </Button>
        {activeCount > 0 && (
          <Button variant="ghost" size="sm" className="text-xs gap-1" onClick={clearAll}>
            <X className="h-3 w-3" /> Clear
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-md border bg-card p-3 mb-3 space-y-3 text-xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Filter className="h-3.5 w-3.5" />
          <span className="font-medium">Filters</span>
          {activeCount > 0 && <Badge variant="secondary" className="text-[10px]">{activeCount} active</Badge>}
        </div>
        <div className="flex items-center gap-1">
          {activeCount > 0 && <Button variant="ghost" size="sm" className="text-xs" onClick={clearAll}>Clear all</Button>}
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setOpen(false)}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {/* Industry */}
        <div className="space-y-1">
          <label className="text-muted-foreground">Industry</label>
          <Select value={filters.industry ?? "any"} onValueChange={(v) => setSelect("industry", v)}>
            <SelectTrigger className="h-7 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Any</SelectItem>
              {industries.map((i) => (
                <SelectItem key={i} value={i}>{i}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Province */}
        <div className="space-y-1">
          <label className="text-muted-foreground">Provincia</label>
          <Input value={filters.province ?? ""} onChange={(e) => set({ province: e.target.value || undefined })}
            className="h-7 text-xs" placeholder="es. MI, RM" />
        </div>

        {/* City */}
        <div className="space-y-1">
          <label className="text-muted-foreground">Città (contiene)</label>
          <Input value={filters.location ?? ""} onChange={(e) => set({ location: e.target.value || undefined })}
            className="h-7 text-xs" placeholder="es. milano" />
        </div>

        {/* Client tag */}
        <div className="space-y-1">
          <label className="text-muted-foreground">Client tag</label>
          <Input value={filters.client_tag ?? ""} onChange={(e) => set({ client_tag: e.target.value || undefined })}
            className="h-7 text-xs" />
        </div>

        {/* Priority tier */}
        <div className="space-y-1">
          <label className="text-muted-foreground">Tier</label>
          <Select value={filters.priority_tier ?? "any"} onValueChange={(v) => setSelect("priority_tier", v)}>
            <SelectTrigger className="h-7 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              {TIER_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>

        {/* Lifecycle */}
        <div className="space-y-1">
          <label className="text-muted-foreground">Lifecycle</label>
          <Select value={filters.lifecycle_stage ?? "any"} onValueChange={(v) => setSelect("lifecycle_stage", v)}>
            <SelectTrigger className="h-7 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              {STAGE_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>

        {/* Revenue range */}
        <div className="space-y-1">
          <label className="text-muted-foreground">Fatturato (€)</label>
          <div className="flex gap-1">
            <Input value={filters.revenue_min ?? ""} onChange={(e) => setNum("revenue_min", e.target.value)}
              className="h-7 text-xs" placeholder="min" />
            <Input value={filters.revenue_max ?? ""} onChange={(e) => setNum("revenue_max", e.target.value)}
              className="h-7 text-xs" placeholder="max" />
          </div>
        </div>

        {/* Employees range */}
        <div className="space-y-1">
          <label className="text-muted-foreground">Dipendenti</label>
          <div className="flex gap-1">
            <Input value={filters.employee_count_min ?? ""} onChange={(e) => setNum("employee_count_min", e.target.value)}
              className="h-7 text-xs" placeholder="min" />
            <Input value={filters.employee_count_max ?? ""} onChange={(e) => setNum("employee_count_max", e.target.value)}
              className="h-7 text-xs" placeholder="max" />
          </div>
        </div>

        {/* Score range */}
        <div className="space-y-1">
          <label className="text-muted-foreground">Score 0-100</label>
          <div className="flex gap-1">
            <Input value={filters.score_min ?? ""} onChange={(e) => setNum("score_min", e.target.value)}
              className="h-7 text-xs" placeholder="min" />
            <Input value={filters.score_max ?? ""} onChange={(e) => setNum("score_max", e.target.value)}
              className="h-7 text-xs" placeholder="max" />
          </div>
        </div>

        {/* Presence flags */}
        {[
          { key: "has_email", label: "Has email" },
          { key: "has_phone", label: "Has phone" },
          { key: "has_linkedin", label: "Has LinkedIn" },
          { key: "has_website", label: "Has website" },
          { key: "has_score", label: "Has score" },
        ].map(({ key, label }) => (
          <div key={key} className="space-y-1">
            <label className="text-muted-foreground">{label}</label>
            <Select
              value={filters[key as keyof CompanyFilters] === undefined ? "any" : filters[key as keyof CompanyFilters] ? "yes" : "no"}
              onValueChange={(v) => setBool(key as keyof CompanyFilters, v as "any" | "yes" | "no")}
            >
              <SelectTrigger className="h-7 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="any">Any</SelectItem>
                <SelectItem value="yes">Yes</SelectItem>
                <SelectItem value="no">No</SelectItem>
              </SelectContent>
            </Select>
          </div>
        ))}
      </div>

      {/* Custom field filters */}
      {customFieldKeys.length > 0 && (
        <div className="border-t pt-3 space-y-2">
          <p className="text-muted-foreground font-medium">Custom fields (text contains)</p>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {customFieldKeys.map((k) => {
              const cur = filters.cf?.[k];
              const value =
                typeof cur === "string"
                  ? cur
                  : cur && typeof cur === "object" && "contains" in cur
                  ? String(cur.contains ?? "")
                  : "";
              return (
                <div key={k} className="space-y-1">
                  <label className="text-muted-foreground truncate" title={k}>{k}</label>
                  <Input value={value} onChange={(e) => setCf(k, e.target.value)} className="h-7 text-xs" />
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
