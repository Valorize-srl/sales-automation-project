"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Upload, Sparkles, Trash2, Tag, Tag as TagIcon } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ClayCompaniesTable } from "@/components/leads/clay-companies-table";
import { CompaniesCSVDialog } from "@/components/leads/companies-csv-dialog";
import { ScoreCompaniesDialog } from "@/components/leads/score-companies-dialog";
import { CompanyDetailDialog } from "@/components/leads/company-detail-dialog";
import { PersonDetailDialog } from "@/components/leads/person-detail-dialog";
import { LeadListsSidebar } from "@/components/leads/lead-lists-sidebar";
import { FilterPanel } from "@/components/leads/filter-panel";
import { PaginationControls } from "@/components/ui/pagination-controls";
import { api } from "@/lib/api";
import { Campaign, Company, CompanyFilters, LeadList, Person } from "@/types";

const DEFAULT_DM_TITLES = ["CEO", "Founder", "Co-Founder", "Owner", "Managing Director", "Director", "VP", "Head"];
const DEFAULT_DM_SENIORITIES = ["c_suite", "vp", "director", "owner", "founder"];

export default function LeadsPage() {
  // Data
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [customFieldKeys, setCustomFieldKeys] = useState<string[]>([]);
  const [industries, setIndustries] = useState<string[]>([]);
  const [allLists, setAllLists] = useState<LeadList[]>([]);
  const [listsRefreshKey, setListsRefreshKey] = useState(0);

  // Filters
  const [filters, setFilters] = useState<CompanyFilters>({});
  const [search, setSearch] = useState("");

  // Selection + dialogs
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [selectAllMatching, setSelectAllMatching] = useState(false);
  const [csvOpen, setCsvOpen] = useState(false);
  const [scoreOpen, setScoreOpen] = useState(false);
  const [scoreSingleId, setScoreSingleId] = useState<number | null>(null);
  const [detailCompany, setDetailCompany] = useState<Company | null>(null);
  const [companyDetailOpen, setCompanyDetailOpen] = useState(false);
  const [detailPerson, setDetailPerson] = useState<Person | null>(null);
  const [personDetailOpen, setPersonDetailOpen] = useState(false);
  const [addToListMenuOpen, setAddToListMenuOpen] = useState(false);
  const [pushToCampaignTarget, setPushToCampaignTarget] = useState<{
    mode: "single" | "bulk";
    companyIds: number[];
  } | null>(null);
  const [allCampaigns, setAllCampaigns] = useState<Campaign[]>([]);

  // Toast-style flash
  const [flash, setFlash] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const showFlash = (kind: "ok" | "err", text: string) => {
    setFlash({ kind, text });
    setTimeout(() => setFlash(null), 4500);
  };

  const effectiveFilters: CompanyFilters = useMemo(() => ({ ...filters, search: search || undefined }), [filters, search]);

  const loadCompanies = useCallback(
    async (p: number = 1, f: CompanyFilters = effectiveFilters) => {
      setLoading(true);
      try {
        const data = await api.getCompaniesFiltered({ ...f, page: p, page_size: 50 });
        setCompanies(data.companies);
        setTotal(data.total);
        setTotalPages(data.total_pages);
        setPage(p);
      } catch (e) {
        console.error("Failed to load companies", e);
      } finally {
        setLoading(false);
      }
    },
    [effectiveFilters],
  );

  const loadAux = useCallback(async () => {
    try {
      const [keys, inds, lists, camps] = await Promise.all([
        api.listCustomFieldKeys(),
        api.getCompanyIndustries(),
        api.listLeadLists(),
        api.getCampaigns().catch(() => ({ campaigns: [], total: 0 })),
      ]);
      setCustomFieldKeys(keys);
      setIndustries(inds);
      setAllLists(lists.lists || []);
      setAllCampaigns(("campaigns" in camps ? camps.campaigns : []) as Campaign[]);
    } catch (e) {
      console.error("Failed to load aux data", e);
    }
  }, []);

  useEffect(() => { loadAux(); }, [loadAux]);

  // Reload table when filters/search change (debounced for search).
  // Cross-page selection is also reset because the matching set changed.
  useEffect(() => {
    setSelectAllMatching(false);
    const t = setTimeout(() => loadCompanies(1, effectiveFilters), 250);
    return () => clearTimeout(t);
  }, [effectiveFilters, loadCompanies]);

  /**
   * Resolve the "live" set of IDs for a bulk action: when selectAllMatching is
   * active, fetch every ID matching the current filters from the server;
   * otherwise return the manually selected ones.
   */
  const resolveSelectedIds = useCallback(async (): Promise<number[]> => {
    if (selectAllMatching) {
      try {
        return await api.getCompanyIdsFiltered(effectiveFilters);
      } catch (e) {
        console.error("Failed to resolve all-matching IDs", e);
        showFlash("err", "Errore nel recupero degli ID — provo solo con la selezione visibile");
        return Array.from(selectedIds);
      }
    }
    return Array.from(selectedIds);
  }, [selectAllMatching, effectiveFilters, selectedIds]);

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
    setDetailCompany(c); setCompanyDetailOpen(true);
  };
  const handleDetailCompanyPersonClick = async (personId: number) => {
    setCompanyDetailOpen(false);
    try {
      const p = await api.getPerson(personId);
      setDetailPerson(p); setPersonDetailOpen(true);
    } catch (e) { console.error(e); }
  };
  const handleDetailPersonCompanyClick = async (companyId: number) => {
    setPersonDetailOpen(false);
    try {
      const c = companies.find((x) => x.id === companyId) ?? await api.getCompany(companyId);
      setDetailCompany(c); setCompanyDetailOpen(true);
    } catch (e) { console.error(e); }
  };

  const handleAction = async (
    companyId: number,
    action: "find_dm" | "enrich" | "score" | "delete",
  ) => {
    if (action === "find_dm") {
      try {
        const r = await api.findAndImportDecisionMakers(companyId, {
          titles: DEFAULT_DM_TITLES, seniorities: DEFAULT_DM_SENIORITIES, per_page: 25,
        });
        showFlash("ok", `${r.imported_count} decision makers importati (su ${r.candidates} trovati)`);
        loadCompanies(page);
      } catch (e) {
        showFlash("err", `Find people fallita: ${e instanceof Error ? e.message : e}`);
      }
    } else if (action === "enrich") {
      try {
        await api.enrichCompany(companyId);
        showFlash("ok", "Enrichment avviato — rinfresca tra qualche secondo");
        setTimeout(() => loadCompanies(page), 3000);
      } catch (e) {
        showFlash("err", `Enrichment fallito: ${e instanceof Error ? e.message : e}`);
      }
    } else if (action === "score") {
      setScoreSingleId(companyId); setScoreOpen(true);
    } else if (action === "push_to_campaign") {
      setPushToCampaignTarget({ mode: "single", companyIds: [companyId] });
    } else if (action === "delete") {
      if (!confirm("Eliminare questa azienda?")) return;
      try {
        await api.deleteCompany(companyId);
        loadCompanies(page);
      } catch (e) {
        showFlash("err", `Eliminazione fallita: ${e instanceof Error ? e.message : e}`);
      }
    }
  };

  const handleBulkDelete = async () => {
    const ids = await resolveSelectedIds();
    if (ids.length === 0) return;
    if (!confirm(`Eliminare ${ids.length} aziende?`)) return;
    for (const id of ids) {
      try { await api.deleteCompany(id); } catch (e) { console.error(e); }
    }
    setSelectedIds(new Set());
    setSelectAllMatching(false);
    loadCompanies(page);
  };

  const handlePushToCampaign = async (campaignId: number) => {
    if (!pushToCampaignTarget) return;
    const ids = pushToCampaignTarget.mode === "bulk"
      ? await resolveSelectedIds()
      : pushToCampaignTarget.companyIds;
    setPushToCampaignTarget(null);
    if (ids.length === 0) return;
    let totalUploaded = 0;
    let failures = 0;
    for (const cid of ids) {
      try {
        const r = await api.pushCompanyDecisionMakersToCampaign(cid, campaignId);
        totalUploaded += r.uploaded;
      } catch (e) {
        failures += 1;
        console.error("push failed for company", cid, e);
      }
    }
    showFlash(failures === 0 ? "ok" : "err",
      `${totalUploaded} decision makers spinti su Instantly` +
      (failures ? ` (${failures} aziende fallite)` : ""));
  };

  const handleAddToList = async (listId: number, createNew?: string) => {
    setAddToListMenuOpen(false);
    let targetId = listId;
    if (createNew) {
      try {
        const ll = await api.createLeadList({ name: createNew });
        targetId = ll.id;
        setListsRefreshKey((k) => k + 1);
        loadAux();
      } catch (e) {
        showFlash("err", `Creazione lista fallita: ${e instanceof Error ? e.message : e}`);
        return;
      }
    }
    const ids = await resolveSelectedIds();
    if (ids.length === 0) return;
    try {
      const res = await api.addCompaniesToList(targetId, ids);
      showFlash("ok", `${res.companies_affected} aziende aggiunte alla lista`);
      setListsRefreshKey((k) => k + 1);
      loadCompanies(page);
    } catch (e) {
      showFlash("err", `Aggiunta lista fallita: ${e instanceof Error ? e.message : e}`);
    }
  };

  const handleCustomFieldSave = async (companyId: number, key: string, value: string) => {
    try {
      const updated = await api.upsertCompanyCustomField(companyId, key, value);
      setCompanies((cs) => cs.map((c) => (c.id === companyId ? updated : c)));
      if (!customFieldKeys.includes(key)) setCustomFieldKeys((ks) => [...ks, key].sort());
    } catch (e) {
      showFlash("err", `Save fallito: ${e instanceof Error ? e.message : e}`);
    }
  };

  const handleAddCustomFieldKey = () => {
    const key = prompt("Nome della nuova colonna (es. \"Note CEO\", \"Status follow-up\")")?.trim();
    if (!key) return;
    if (customFieldKeys.includes(key)) { showFlash("err", "Colonna già esistente"); return; }
    setCustomFieldKeys((ks) => [...ks, key].sort());
    showFlash("ok", `Colonna "${key}" aggiunta. Click su una cella per inserire un valore.`);
  };

  const onSelectList = (listId: number | null) => {
    setFilters((f) => ({ ...f, list_id: listId ?? undefined }));
    setSelectedIds(new Set());
    setPage(1);
  };

  return (
    <div className="flex h-[calc(100vh-0px)]">
      <LeadListsSidebar
        selectedListId={filters.list_id ?? null}
        onSelectList={onSelectList}
        refreshKey={listsRefreshKey}
      />

      <div className="flex-1 overflow-auto">
        <div className="container mx-auto py-4 px-4 max-w-[1600px] space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold">Leads</h1>
              <p className="text-sm text-muted-foreground mt-0.5">
                {filters.list_id
                  ? `Filtro lista: ${allLists.find((l) => l.id === filters.list_id)?.name ?? `#${filters.list_id}`}`
                  : "Dashboard aziende — scoring, decision maker, enrichment, custom fields."}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" className="gap-1.5" onClick={() => setCsvOpen(true)}>
                <Upload className="h-3.5 w-3.5" /> Import CSV
              </Button>
              <Button size="sm" className="gap-1.5" disabled={total === 0}
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

          <FilterPanel
            filters={filters}
            onFiltersChange={(f) => { setFilters(f); setPage(1); }}
            industries={industries}
            customFieldKeys={customFieldKeys}
          />

          {(selectedIds.size > 0 || selectAllMatching) && (
            <div className="flex items-center gap-3 p-2.5 bg-primary/5 rounded-md border border-primary/20">
              <span className="text-sm font-medium">
                {selectAllMatching
                  ? `${total.toLocaleString("it-IT")} (tutte le matching)`
                  : `${selectedIds.size} selected`}
              </span>
              <div className="h-4 w-px bg-border" />
              <div className="relative">
                <Button size="sm" variant="outline" className="gap-1.5"
                  onClick={() => setAddToListMenuOpen(!addToListMenuOpen)}>
                  <Tag className="h-3.5 w-3.5" /> Aggiungi a lista…
                </Button>
                {addToListMenuOpen && (
                  <>
                    <div className="fixed inset-0 z-30" onClick={() => setAddToListMenuOpen(false)} />
                    <div className="absolute left-0 top-9 z-40 w-64 rounded-md border bg-popover shadow-md py-1 max-h-80 overflow-y-auto">
                      <button
                        className="flex items-center gap-2 px-3 py-1.5 text-sm w-full text-left hover:bg-accent border-b"
                        onClick={() => {
                          const name = prompt("Nome della nuova lista:")?.trim();
                          if (name) handleAddToList(0, name);
                        }}
                      >
                        + Crea nuova lista…
                      </button>
                      {allLists.length === 0 ? (
                        <p className="px-3 py-2 text-xs text-muted-foreground italic">Nessuna lista esistente.</p>
                      ) : (
                        allLists.map((ll) => (
                          <button key={ll.id}
                            className="flex items-center gap-2 px-3 py-1.5 text-sm w-full text-left hover:bg-accent"
                            onClick={() => handleAddToList(ll.id)}>
                            <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ backgroundColor: ll.color || "#9ca3af" }} />
                            <span className="flex-1 truncate">{ll.name}</span>
                            <span className="text-[10px] text-muted-foreground tabular-nums">{ll.companies_count}</span>
                          </button>
                        ))
                      )}
                    </div>
                  </>
                )}
              </div>
              <Button size="sm" variant="outline" className="gap-1.5"
                onClick={() => { setScoreSingleId(null); setScoreOpen(true); }}>
                <Sparkles className="h-3.5 w-3.5" /> Score
              </Button>
              <Button size="sm" variant="outline" className="gap-1.5"
                onClick={async () => {
                  const ids = await resolveSelectedIds();
                  setPushToCampaignTarget({ mode: "bulk", companyIds: ids });
                }}>
                <Tag className="h-3.5 w-3.5" /> Aggiungi DM a campagna…
              </Button>
              <Button size="sm" variant="outline" className="gap-1.5 text-destructive" onClick={handleBulkDelete}>
                <Trash2 className="h-3.5 w-3.5" /> Delete
              </Button>
              <Button size="sm" variant="ghost" className="ml-auto"
                onClick={() => { setSelectedIds(new Set()); setSelectAllMatching(false); }}>
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
            onToggleSelect={(id) => { setSelectAllMatching(false); toggleSelect(id); }}
            onToggleSelectAll={toggleSelectAllOnPage}
            customFieldKeys={customFieldKeys}
            onCompanyClick={handleCompanyClick}
            onPersonClick={handleDetailCompanyPersonClick}
            onAction={handleAction}
            onCustomFieldSave={handleCustomFieldSave}
            onAddCustomFieldKey={handleAddCustomFieldKey}
            rowsPerPage={50}
            pageIndex={page - 1}
            total={total}
            allLists={allLists}
            selectAllMatching={selectAllMatching}
            onSelectAllMatching={setSelectAllMatching}
          />

          {totalPages > 1 && (
            <PaginationControls
              page={page} totalPages={totalPages} total={total} pageSize={50}
              onPageChange={(p) => loadCompanies(p)}
            />
          )}

          <CompaniesCSVDialog
            open={csvOpen}
            onOpenChange={setCsvOpen}
            onImportComplete={() => { loadCompanies(1); loadAux(); }}
          />

          <ScoreCompaniesDialog
            open={scoreOpen}
            onOpenChange={(o) => { setScoreOpen(o); if (!o) setScoreSingleId(null); }}
            selectedCompanyIds={
              scoreSingleId !== null ? [scoreSingleId] : (selectedIds.size > 0 ? Array.from(selectedIds) : [])
            }
            totalCompanyCount={total}
            onCompleted={() => loadCompanies(page)}
          />

          <CompanyDetailDialog
            company={detailCompany}
            open={companyDetailOpen}
            onOpenChange={setCompanyDetailOpen}
            onPersonClick={handleDetailCompanyPersonClick}
            onUpdated={() => loadCompanies(page)}
          />

          <PersonDetailDialog
            person={detailPerson}
            open={personDetailOpen}
            onOpenChange={setPersonDetailOpen}
            onCompanyClick={handleDetailPersonCompanyClick}
            onUpdated={() => loadCompanies(page)}
          />

          {pushToCampaignTarget && (
            <PushToCampaignDialog
              open={true}
              onOpenChange={(open) => { if (!open) setPushToCampaignTarget(null); }}
              campaigns={allCampaigns}
              targetCount={pushToCampaignTarget.companyIds.length}
              onPick={handlePushToCampaign}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// Inline dialog component — picks an Instantly-synced campaign from a list
function PushToCampaignDialog({
  open, onOpenChange, campaigns, targetCount, onPick,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  campaigns: Campaign[];
  targetCount: number;
  onPick: (campaignId: number) => void;
}) {
  // Only campaigns synced to Instantly can accept leads
  const syncedCampaigns = campaigns.filter((c) => c.instantly_campaign_id);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <TagIcon className="h-5 w-5 text-primary" />
            Aggiungi decision makers a campagna
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-2 py-2">
          <p className="text-sm text-muted-foreground">
            Verranno spinti su Instantly tutti i decision maker (con email) di {targetCount} {targetCount === 1 ? "azienda" : "aziende"}.
          </p>
          {syncedCampaigns.length === 0 ? (
            <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-2">
              Nessuna campagna synced con Instantly. Crea/sync prima una campagna.
            </p>
          ) : (
            <div className="space-y-1 max-h-[300px] overflow-y-auto">
              {syncedCampaigns.map((c) => (
                <button
                  key={c.id}
                  className="flex items-center gap-2 px-3 py-2 rounded-md border w-full text-left text-sm hover:bg-accent"
                  onClick={() => onPick(c.id)}
                >
                  <span className="flex-1 truncate font-medium">{c.name}</span>
                  <span className="text-[10px] text-muted-foreground">{c.status}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Annulla</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
