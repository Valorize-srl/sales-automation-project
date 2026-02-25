"use client";

import { useState } from "react";
import { Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";

const SENIORITY_OPTIONS = [
  { value: "entry", label: "Entry" },
  { value: "senior", label: "Senior" },
  { value: "manager", label: "Manager" },
  { value: "director", label: "Director" },
  { value: "vp", label: "VP" },
  { value: "c_suite", label: "C-Suite" },
];

const SIZE_OPTIONS = [
  { value: "1-10", label: "1–10" },
  { value: "11-50", label: "11–50" },
  { value: "51-200", label: "51–200" },
  { value: "201-500", label: "201–500" },
  { value: "501-1000", label: "501–1000" },
  { value: "1001-5000", label: "1001–5000" },
  { value: "5001+", label: "5001+" },
];

function MultiCheckbox({
  options,
  selected,
  onChange,
}: {
  options: { value: string; label: string }[];
  selected: string[];
  onChange: (values: string[]) => void;
}) {
  const toggle = (v: string) =>
    onChange(selected.includes(v) ? selected.filter((s) => s !== v) : [...selected, v]);

  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => toggle(o.value)}
          className={`px-2.5 py-1 rounded-full text-xs border transition-colors ${
            selected.includes(o.value)
              ? "bg-primary text-primary-foreground border-primary"
              : "border-border text-muted-foreground hover:border-primary/60"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export interface ApolloFormFilters {
  search_type: "people" | "companies";
  person_titles?: string[];
  person_locations?: string[];
  person_seniorities?: string[];
  organization_locations?: string[];
  organization_keywords?: string[];
  organization_sizes?: string[];
  technologies?: string[];
  keywords?: string;
  per_page: number;
  client_tag?: string;
  auto_enrich?: boolean;  // Auto-enrich companies with website scraping
}

interface Props {
  onSearch: (filters: ApolloFormFilters) => void;
  onClose: () => void;
  loading?: boolean;
}

function splitTags(val: string): string[] {
  return val
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function ApolloSearchForm({ onSearch, onClose, loading }: Props) {
  const [tab, setTab] = useState<"people" | "companies">("people");

  // People fields
  const [personTitles, setPersonTitles] = useState("");
  const [personLocations, setPersonLocations] = useState("");
  const [personSeniorities, setPersonSeniorities] = useState<string[]>([]);
  const [orgKeywordsPeople, setOrgKeywordsPeople] = useState("");
  const [orgSizesPeople, setOrgSizesPeople] = useState<string[]>([]);
  const [keywordsPeople, setKeywordsPeople] = useState("");
  const [perPagePeople, setPerPagePeople] = useState("25");

  // Companies fields
  const [orgLocations, setOrgLocations] = useState("");
  const [orgKeywords, setOrgKeywords] = useState("");
  const [orgSizes, setOrgSizes] = useState<string[]>([]);
  const [technologies, setTechnologies] = useState("");
  const [keywordsCompanies, setKeywordsCompanies] = useState("");
  const [perPageCompanies, setPerPageCompanies] = useState("25");

  // Shared fields
  const [clientTag, setClientTag] = useState("");
  const [autoEnrich, setAutoEnrich] = useState(false);

  const handleSubmit = () => {
    if (tab === "people") {
      onSearch({
        search_type: "people",
        person_titles: splitTags(personTitles),
        person_locations: splitTags(personLocations),
        person_seniorities: personSeniorities.length ? personSeniorities : undefined,
        organization_keywords: splitTags(orgKeywordsPeople),
        organization_sizes: orgSizesPeople.length ? orgSizesPeople : undefined,
        keywords: keywordsPeople.trim() || undefined,
        per_page: Math.min(100, Math.max(1, parseInt(perPagePeople) || 25)),
        client_tag: clientTag.trim() || undefined,
        auto_enrich: autoEnrich,
      });
    } else {
      onSearch({
        search_type: "companies",
        organization_locations: splitTags(orgLocations),
        organization_keywords: splitTags(orgKeywords),
        organization_sizes: orgSizes.length ? orgSizes : undefined,
        technologies: splitTags(technologies),
        keywords: keywordsCompanies.trim() || undefined,
        per_page: Math.min(100, Math.max(1, parseInt(perPageCompanies) || 25)),
        client_tag: clientTag.trim() || undefined,
        auto_enrich: autoEnrich,
      });
    }
  };

  return (
    <div className="rounded-xl border bg-card shadow-md p-4 w-full">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-sm">Advanced Apollo Search</h3>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b mb-4">
        {(["people", "companies"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-4 py-1.5 text-sm font-medium capitalize transition-colors ${
              tab === t
                ? "border-b-2 border-primary text-primary"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "people" ? (
        <div className="space-y-3">
          <div>
            <Label className="text-xs mb-1 block">Job Titles (comma-separated)</Label>
            <Input
              placeholder="e.g. SEO Specialist, SEO Manager"
              value={personTitles}
              onChange={(e) => setPersonTitles(e.target.value)}
              className="h-8 text-sm"
            />
          </div>
          <div>
            <Label className="text-xs mb-1 block">Location (comma-separated)</Label>
            <Input
              placeholder="e.g. Italy, Milan, Germany"
              value={personLocations}
              onChange={(e) => setPersonLocations(e.target.value)}
              className="h-8 text-sm"
            />
          </div>
          <div>
            <Label className="text-xs mb-2 block">Seniority</Label>
            <MultiCheckbox
              options={SENIORITY_OPTIONS}
              selected={personSeniorities}
              onChange={setPersonSeniorities}
            />
          </div>
          <div>
            <Label className="text-xs mb-1 block">Company Keywords (comma-separated)</Label>
            <Input
              placeholder="e.g. digital agency, ecommerce"
              value={orgKeywordsPeople}
              onChange={(e) => setOrgKeywordsPeople(e.target.value)}
              className="h-8 text-sm"
            />
          </div>
          <div>
            <Label className="text-xs mb-2 block">Company Size</Label>
            <MultiCheckbox
              options={SIZE_OPTIONS}
              selected={orgSizesPeople}
              onChange={setOrgSizesPeople}
            />
          </div>
          <div>
            <Label className="text-xs mb-1 block">General Keywords</Label>
            <Input
              placeholder="e.g. startup, SaaS"
              value={keywordsPeople}
              onChange={(e) => setKeywordsPeople(e.target.value)}
              className="h-8 text-sm"
            />
          </div>
          <div>
            <Label className="text-xs mb-1 block">Max Results</Label>
            <select
              value={perPagePeople}
              onChange={(e) => setPerPagePeople(e.target.value)}
              className="h-8 w-24 rounded-md border border-input bg-background px-2 text-sm"
            >
              {[25, 50, 100].map((n) => (
                <option key={n} value={String(n)}>
                  {n}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label className="text-xs mb-1 block">Client/Project Tag (Optional)</Label>
            <Input
              placeholder="e.g. Cliente X - Dentisti Milano"
              value={clientTag}
              onChange={(e) => setClientTag(e.target.value)}
              className="h-8 text-sm"
            />
          </div>
          <div className="flex items-center space-x-2 pt-2">
            <Checkbox
              id="auto-enrich-people"
              checked={autoEnrich}
              onCheckedChange={(checked) => setAutoEnrich(checked as boolean)}
            />
            <div>
              <Label
                htmlFor="auto-enrich-people"
                className="text-xs cursor-pointer"
              >
                Auto-enrich all results (1 credit/person)
              </Label>
              <p className="text-[10px] text-muted-foreground">
                If off, you can selectively enrich from the results table
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div>
            <Label className="text-xs mb-1 block">Location (comma-separated)</Label>
            <Input
              placeholder="e.g. Italy, Germany"
              value={orgLocations}
              onChange={(e) => setOrgLocations(e.target.value)}
              className="h-8 text-sm"
            />
          </div>
          <div>
            <Label className="text-xs mb-1 block">Industry / Keywords (comma-separated)</Label>
            <Input
              placeholder="e.g. digital agency, SaaS, ecommerce"
              value={orgKeywords}
              onChange={(e) => setOrgKeywords(e.target.value)}
              className="h-8 text-sm"
            />
          </div>
          <div>
            <Label className="text-xs mb-2 block">Company Size</Label>
            <MultiCheckbox
              options={SIZE_OPTIONS}
              selected={orgSizes}
              onChange={setOrgSizes}
            />
          </div>
          <div>
            <Label className="text-xs mb-1 block">Technologies (comma-separated)</Label>
            <Input
              placeholder="e.g. Salesforce, HubSpot, Shopify"
              value={technologies}
              onChange={(e) => setTechnologies(e.target.value)}
              className="h-8 text-sm"
            />
          </div>
          <div>
            <Label className="text-xs mb-1 block">General Keywords</Label>
            <Input
              placeholder="e.g. funding, startup"
              value={keywordsCompanies}
              onChange={(e) => setKeywordsCompanies(e.target.value)}
              className="h-8 text-sm"
            />
          </div>
          <div>
            <Label className="text-xs mb-1 block">Max Results</Label>
            <select
              value={perPageCompanies}
              onChange={(e) => setPerPageCompanies(e.target.value)}
              className="h-8 w-24 rounded-md border border-input bg-background px-2 text-sm"
            >
              {[25, 50, 100].map((n) => (
                <option key={n} value={String(n)}>
                  {n}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label className="text-xs mb-1 block">Client/Project Tag (Optional)</Label>
            <Input
              placeholder="e.g. Cliente X - Dentisti Milano"
              value={clientTag}
              onChange={(e) => setClientTag(e.target.value)}
              className="h-8 text-sm"
            />
          </div>
          <div className="flex items-center space-x-2 pt-2">
            <Checkbox
              id="auto-enrich"
              checked={autoEnrich}
              onCheckedChange={(checked) => setAutoEnrich(checked as boolean)}
            />
            <Label
              htmlFor="auto-enrich"
              className="text-xs cursor-pointer"
            >
              Auto-enrich companies with website emails
            </Label>
          </div>
        </div>
      )}

      <div className="flex justify-end gap-2 mt-4">
        <Button variant="outline" size="sm" onClick={onClose} disabled={loading}>
          Cancel
        </Button>
        <Button size="sm" onClick={handleSubmit} disabled={loading} className="gap-1.5">
          <Search className="h-3.5 w-3.5" />
          {loading ? "Searching…" : "Search Apollo"}
        </Button>
      </div>
    </div>
  );
}
