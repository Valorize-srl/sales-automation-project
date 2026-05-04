"use client";

import { useCallback, useEffect, useState } from "react";
import { Upload, Sparkles, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ClayCompaniesTable } from "@/components/leads/clay-companies-table";
import { CompaniesCSVDialog } from "@/components/leads/companies-csv-dialog";
import { ScoreCompaniesDialog } from "@/components/leads/score-companies-dialog";
import { CompanyDetailDialog } from "@/components/leads/company-detail-dialog";
import { PersonDetailDialog } from "@/components/leads/person-detail-dialog";
import { PaginationControls } from "@/components/ui/pagination-controls";
import { api } from "@/lib/api";
import { Company, Person } from "@/types";

const DEFAULT_DM_TITLES = ["CEO", "Founder", "Co-Founder", "Owner", "Managing Director", "Director", "VP", "Head"];
const DEFAULT_DM_SENIORITIES = ["c_suite", "vp", "director", "owner", "founder"];

export default function LeadsPage() {
  // Data
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [search, setSearch] = useState("");
  const [customFieldKeys, setCustomFieldKeys] = useState<string[]>([]);

  // Selection
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Dialogs
  const [csvOpen, setCsvOpen] = useState(false);
  const [scoreOpen, setScoreOpen] = useState(false);
  const [scoreSingleId, setScoreSingleId] = useState<number | null>(null);
  const [detailCompany, setDetailCompany] = useState<Company | null>(null);
  const [companyDetailOpen, setCompanyDetailOpen] = useState(false);
  const [detailPerson, setDetailPerson] = useState<Person | null>(null);
  const [personDetailOpen, setPersonDetailOpen] = useState(false);

  // Toast-style flash message
  const [flash, setFlash] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const loadCompanies = useCallback(async (q?: string, p: number = 1) => {
    setLoading(true);
    try {
      const data = await api.getCompanies({ search: q, skip: (p - 1) * 50, limit: 50 });
      setCompanies(data.companies);
      setTotal(data.total);
      setTotalPages(data.total_pages);
      setPage(p);
    } catch (e) {
      console.error("Failed to load companies", e);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCustomKeys = useCallback(async () => {
    try {
      const keys = await api.listCustomFieldKeys();
      setCustomFieldKeys(keys);
    } catch (e) {
      console.error("Failed to load custom field keys", e);
    }
  }, []);

  useEffect(() => { loadCompanies(); loadCustomKeys(); }, [loadCompanies, loadCustomKeys]);

  // Reload when search changes (debounced via key effect)
  useEffect(() => {
    const t = setTimeout(() => loadCompanies(search, 1), 300);
    return () => clearTimeout(t);
  }, [search, loadCompanies]);

  const showFlash = (kind: "ok" | "err", text: string) => {
    setFlash({ kind, text });
    setTimeout(() => setFlash(null), 4500);
  };

  // --- Selection ---
  const toggleSelect = (id: number) =>
    setSelectedIds((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });

  const toggleSelectAllOnPage = () => {
    if (companies.every((c) => selectedIds.has(c.id))) {
      setSelectedIds((prev) => {
        const n = new Set(prev);
        companies.forEach((c) => n.delete(c.id));
        return n;
      });
    } else {
      setSelectedIds((prev) => {
        const n = new Set(prev);
        companies.forEach((c) => n.add(c.id));
        return n;
      });
    }
  };

  // --- Actions ---
  const handleCompanyClick = (c: Company) => {
    setDetailCompany(c);
    setCompanyDetailOpen(true);
  };

  const handleDetailCompanyPersonClick = async (personId: number) => {
    setCompanyDetailOpen(false);
    try {
      const p = await api.getPerson(personId);
      setDetailPerson(p);
      setPersonDetailOpen(true);
    } catch (e) {
      console.error(e);
    }
  };

  const handleDetailPersonCompanyClick = async (companyId: number) => {
    setPersonDetailOpen(false);
    try {
      const c = companies.find((x) => x.id === companyId) ?? await api.getCompany(companyId);
      setDetailCompany(c);
      setCompanyDetailOpen(true);
    } catch (e) {
      console.error(e);
    }
  };

  const handleAction = async (
    companyId: number,
    action: "find_dm" | "enrich" | "score" | "delete",
  ) => {
    if (action === "find_dm") {
      try {
        const r = await api.findAndImportDecisionMakers(companyId, {
          titles: DEFAULT_DM_TITLES,
          seniorities: DEFAULT_DM_SENIORITIES,
          per_page: 25,
        });
        showFlash("ok", `${r.imported_count} decision makers importati (su ${r.candidates} trovati)`);
        loadCompanies(search, page);
      } catch (e) {
        showFlash("err", `Find people fallita: ${e instanceof Error ? e.message : e}`);
      }
    } else if (action === "enrich") {
      try {
        await api.enrichCompany(companyId);
        showFlash("ok", "Enrichment avviato — rinfresca tra qualche secondo");
        setTimeout(() => loadCompanies(search, page), 3000);
      } catch (e) {
        showFlash("err", `Enrichment fallito: ${e instanceof Error ? e.message : e}`);
      }
    } else if (action === "score") {
      setScoreSingleId(companyId);
      setScoreOpen(true);
    } else if (action === "delete") {
      if (!confirm("Eliminare questa azienda?")) return;
      try {
        await api.deleteCompany(companyId);
        loadCompanies(search, page);
      } catch (e) {
        showFlash("err", `Eliminazione fallita: ${e instanceof Error ? e.message : e}`);
      }
    }
  };

  const handleBulkDelete = async () => {
    if (!confirm(`Eliminare ${selectedIds.size} aziende?`)) return;
    try {
      for (const id of selectedIds) {
        await api.deleteCompany(id);
      }
      setSelectedIds(new Set());
      loadCompanies(search, page);
    } catch (e) {
      showFlash("err", `Bulk delete failed: ${e instanceof Error ? e.message : e}`);
    }
  };

  const handleCustomFieldSave = async (companyId: number, key: string, value: string) => {
    try {
      const updated = await api.upsertCompanyCustomField(companyId, key, value);
      // Optimistic local update
      setCompanies((cs) => cs.map((c) => (c.id === companyId ? updated : c)));
      // refresh keys (might be a new one)
      if (!customFieldKeys.includes(key)) {
        setCustomFieldKeys((ks) => [...ks, key].sort());
      }
    } catch (e) {
      showFlash("err", `Save fallito: ${e instanceof Error ? e.message : e}`);
    }
  };

  const handleAddCustomFieldKey = () => {
    const key = prompt("Nome della nuova colonna (es. \"Note CEO\", \"Status follow-up\")")?.trim();
    if (!key) return;
    if (customFieldKeys.includes(key)) {
      showFlash("err", "Colonna già esistente");
      return;
    }
    setCustomFieldKeys((ks) => [...ks, key].sort());
    showFlash("ok", `Colonna "${key}" aggiunta. Click su una cella per inserire un valore.`);
  };

  return (
    <div className="container mx-auto py-6 px-4 max-w-[1600px] space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Leads</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Dashboard aziende — scoring, decision maker, enrichment, custom fields.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="gap-1.5" onClick={() => setCsvOpen(true)}>
            <Upload className="h-3.5 w-3.5" /> Import CSV
          </Button>
          <Button size="sm" className="gap-1.5"
            disabled={total === 0}
            onClick={() => { setScoreSingleId(null); setScoreOpen(true); }}>
            <Sparkles className="h-3.5 w-3.5" />
            Score {selectedIds.size > 0 ? `${selectedIds.size} selezionate` : `tutte (${total})`}
          </Button>
        </div>
      </div>

      {flash && (
        <div className={`rounded-md border px-3 py-2 text-sm ${flash.kind === "ok" ? "bg-emerald-50 border-emerald-200 text-emerald-900" : "bg-red-50 border-red-200 text-red-900"}`}>
          {flash.text}
        </div>
      )}

      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 p-2.5 bg-primary/5 rounded-md border border-primary/20">
          <span className="text-sm font-medium">{selectedIds.size} selected</span>
          <div className="h-4 w-px bg-border" />
          <Button size="sm" variant="outline" className="gap-1.5"
            onClick={() => { setScoreSingleId(null); setScoreOpen(true); }}>
            <Sparkles className="h-3.5 w-3.5" /> Score with ICP
          </Button>
          <Button size="sm" variant="outline" className="gap-1.5 text-destructive"
            onClick={handleBulkDelete}>
            <Trash2 className="h-3.5 w-3.5" /> Delete
          </Button>
          <Button size="sm" variant="ghost" className="ml-auto"
            onClick={() => setSelectedIds(new Set())}>
            Clear
          </Button>
        </div>
      )}

      <ClayCompaniesTable
        companies={companies}
        loading={loading}
        search={search}
        onSearchChange={setSearch}
        selectedIds={selectedIds}
        onToggleSelect={toggleSelect}
        onToggleSelectAll={toggleSelectAllOnPage}
        customFieldKeys={customFieldKeys}
        onCompanyClick={handleCompanyClick}
        onAction={handleAction}
        onCustomFieldSave={handleCustomFieldSave}
        onAddCustomFieldKey={handleAddCustomFieldKey}
        rowsPerPage={50}
        pageIndex={page - 1}
        total={total}
      />

      {totalPages > 1 && (
        <PaginationControls
          page={page}
          totalPages={totalPages}
          total={total}
          pageSize={50}
          onPageChange={(p) => loadCompanies(search, p)}
        />
      )}

      <CompaniesCSVDialog
        open={csvOpen}
        onOpenChange={setCsvOpen}
        onImportComplete={() => { loadCompanies(search, 1); loadCustomKeys(); }}
      />

      <ScoreCompaniesDialog
        open={scoreOpen}
        onOpenChange={(o) => { setScoreOpen(o); if (!o) setScoreSingleId(null); }}
        selectedCompanyIds={
          scoreSingleId !== null
            ? [scoreSingleId]
            : (selectedIds.size > 0 ? Array.from(selectedIds) : [])
        }
        totalCompanyCount={total}
        onCompleted={() => loadCompanies(search, page)}
      />

      <CompanyDetailDialog
        company={detailCompany}
        open={companyDetailOpen}
        onOpenChange={setCompanyDetailOpen}
        onPersonClick={handleDetailCompanyPersonClick}
        onUpdated={() => loadCompanies(search, page)}
      />

      <PersonDetailDialog
        person={detailPerson}
        open={personDetailOpen}
        onOpenChange={setPersonDetailOpen}
        onCompanyClick={handleDetailPersonCompanyClick}
        onUpdated={() => loadCompanies(search, page)}
      />
    </div>
  );
}
