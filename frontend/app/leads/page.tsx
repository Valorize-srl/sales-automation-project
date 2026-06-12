"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Upload, Sparkles, Trash2, Tag, Tag as TagIcon, Download, Plus } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ClayCompaniesTable } from "@/components/leads/clay-companies-table";
import { CompaniesCSVDialog } from "@/components/leads/companies-csv-dialog";
import { CompanyDetailDialog } from "@/components/leads/company-detail-dialog";
import { PersonDetailDialog } from "@/components/leads/person-detail-dialog";
import { BulkScrapeDialog } from "@/components/leads/bulk-scrape-dialog";
import { LinkedInFindDMDialog } from "@/components/leads/linkedin-find-dm-dialog";
import { FindymailEnrichDialog } from "@/components/leads/findymail-enrich-dialog";
import { FindymailFindDMDialog } from "@/components/leads/findymail-find-dm-dialog";
import { FindymailFindDMViaLinkedInDialog } from "@/components/leads/findymail-find-dm-via-linkedin-dialog";
import { FindymailFindCompanyInfoDialog } from "@/components/leads/findymail-find-company-info-dialog";
import { ApolloSearchPeopleDialog } from "@/components/leads/apollo-search-people-dialog";
import { EnrichmentDrawer } from "@/components/leads/enrichment-drawer";
import { AddCompanyDialog } from "@/components/leads/add-company-dialog";
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
  const [addCompanyOpen, setAddCompanyOpen] = useState(false);
  const [detailCompany, setDetailCompany] = useState<Company | null>(null);
  const [companyDetailOpen, setCompanyDetailOpen] = useState(false);
  const [detailPerson, setDetailPerson] = useState<Person | null>(null);
  const [personDetailOpen, setPersonDetailOpen] = useState(false);
  const [addToListMenuOpen, setAddToListMenuOpen] = useState(false);
  const [bulkScrapeOpen, setBulkScrapeOpen] = useState(false);
  const [bulkScrapeCompanies, setBulkScrapeCompanies] = useState<Company[]>([]);
  const [bulkScrapePreparing, setBulkScrapePreparing] = useState(false);
  const [linkedInDMOpen, setLinkedInDMOpen] = useState(false);
  const [linkedInDMCompanies, setLinkedInDMCompanies] = useState<Company[]>([]);
  const [linkedInDMPreparing, setLinkedInDMPreparing] = useState(false);
  const [findymailOpen, setFindymailOpen] = useState(false);
  const [findymailCompanies, setFindymailCompanies] = useState<Company[]>([]);
  const [findymailPreparing, setFindymailPreparing] = useState(false);
  const [findymailFindOpen, setFindymailFindOpen] = useState(false);
  const [findymailFindCompanies, setFindymailFindCompanies] = useState<Company[]>([]);
  const [findymailFindPreparing, setFindymailFindPreparing] = useState(false);
  const [findymailLiOpen, setFindymailLiOpen] = useState(false);
  const [findymailLiCompanies, setFindymailLiCompanies] = useState<Company[]>([]);
  const [findymailLiPreparing, setFindymailLiPreparing] = useState(false);
  const [apolloPeopleOpen, setApolloPeopleOpen] = useState(false);
  const [enrichmentDrawerOpen, setEnrichmentDrawerOpen] = useState(false);
  const [listsSidebarCollapsed, setListsSidebarCollapsed] = useState(false);
  const [findymailCoOpen, setFindymailCoOpen] = useState(false);
  const [findymailCoCompanies, setFindymailCoCompanies] = useState<Company[]>([]);
  const [findymailCoPreparing, setFindymailCoPreparing] = useState(false);
  // (enrichMenuOpen rimosso: il dropdown è stato sostituito da EnrichmentDrawer.)
  const [exportingCsv, setExportingCsv] = useState(false);
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

  // Keep latest filters in a ref so loadCompanies stays stable across renders.
  // Without this, loadCompanies is re-created whenever effectiveFilters changes,
  // and the filter-watcher useEffect (which depends on loadCompanies) would
  // re-fire and reset the page to 1 — breaking pagination on filtered views.
  const filtersRef = useRef(effectiveFilters);
  filtersRef.current = effectiveFilters;

  // Monotonic request ID. Each loadCompanies bumps it; only the latest in-flight
  // request applies its result. Prevents a stale debounced page-1 fetch from
  // overwriting state after the user has already clicked "next page".
  const loadReqIdRef = useRef(0);

  const loadCompanies = useCallback(
    async (p: number = 1, f?: CompanyFilters) => {
      const filtersToUse = f ?? filtersRef.current;
      const myReqId = ++loadReqIdRef.current;
      setLoading(true);
      try {
        const data = await api.getCompaniesFiltered({ ...filtersToUse, page: p, page_size: 50 });
        if (myReqId !== loadReqIdRef.current) return; // a newer load is in flight
        setCompanies(data.companies);
        setTotal(data.total);
        setTotalPages(data.total_pages);
        setPage(p);
      } catch (e) {
        if (myReqId !== loadReqIdRef.current) return;
        console.error("Failed to load companies", e);
      } finally {
        if (myReqId === loadReqIdRef.current) setLoading(false);
      }
    },
    [],
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

  // Reload table when discrete filters change (sidebar list, FilterPanel selects,
  // etc.) — fires immediately, no debounce. Cross-page selection is reset because
  // the matching set changed. loadCompanies is stable thanks to filtersRef.
  useEffect(() => {
    setSelectAllMatching(false);
    loadCompanies(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  // Search changes are debounced separately so the user can type without
  // hammering the backend. Skip the very first run (initial mount handled by
  // the [filters] effect above).
  const isFirstSearchRun = useRef(true);
  useEffect(() => {
    if (isFirstSearchRun.current) { isFirstSearchRun.current = false; return; }
    const t = setTimeout(() => loadCompanies(1), 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

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

  /**
   * Resolve the full set of Company objects for the bulk-scrape dialog.
   * - selectAllMatching: paginate through every matching company on the server
   *   (page_size=200) so the scraper sees all of them, not just the visible page.
   * - manual selection: filter the already-loaded current page by selectedIds.
   * - no selection: scrape just the current page.
   */
  const openBulkScrape = async () => {

    if (selectAllMatching) {
      setBulkScrapePreparing(true);
      try {
        const PAGE_SIZE = 200;
        const acc: Company[] = [];
        let p = 1;
        // First page tells us total_pages
        const first = await api.getCompaniesFiltered({ ...effectiveFilters, page: p, page_size: PAGE_SIZE });
        acc.push(...first.companies);
        while (p < first.total_pages) {
          p += 1;
          const next = await api.getCompaniesFiltered({ ...effectiveFilters, page: p, page_size: PAGE_SIZE });
          acc.push(...next.companies);
        }
        setBulkScrapeCompanies(acc);
        setBulkScrapeOpen(true);
      } catch (e) {
        showFlash("err", `Recupero aziende fallito: ${e instanceof Error ? e.message : e}`);
      } finally {
        setBulkScrapePreparing(false);
      }
      return;
    }
    if (selectedIds.size > 0) {
      setBulkScrapeCompanies(companies.filter((c) => selectedIds.has(c.id)));
    } else {
      setBulkScrapeCompanies(companies);
    }
    setBulkScrapeOpen(true);
  };

  /**
   * Resolve the full set of companies for the LinkedIn-find-DM dialog. Same
   * pattern as openBulkScrape: selectAllMatching paginates through the server.
   */
  const openLinkedInDM = async () => {

    if (selectAllMatching) {
      setLinkedInDMPreparing(true);
      try {
        const PAGE_SIZE = 200;
        const acc: Company[] = [];
        let p = 1;
        const first = await api.getCompaniesFiltered({ ...effectiveFilters, page: p, page_size: PAGE_SIZE });
        acc.push(...first.companies);
        while (p < first.total_pages) {
          p += 1;
          const next = await api.getCompaniesFiltered({ ...effectiveFilters, page: p, page_size: PAGE_SIZE });
          acc.push(...next.companies);
        }
        setLinkedInDMCompanies(acc);
        setLinkedInDMOpen(true);
      } catch (e) {
        showFlash("err", `Recupero aziende fallito: ${e instanceof Error ? e.message : e}`);
      } finally {
        setLinkedInDMPreparing(false);
      }
      return;
    }
    if (selectedIds.size > 0) {
      setLinkedInDMCompanies(companies.filter((c) => selectedIds.has(c.id)));
    } else {
      setLinkedInDMCompanies(companies);
    }
    setLinkedInDMOpen(true);
  };

  /** Findymail email enrichment — same selection resolution pattern. */
  const openFindymail = async () => {

    if (selectAllMatching) {
      setFindymailPreparing(true);
      try {
        const PAGE_SIZE = 200;
        const acc: Company[] = [];
        let p = 1;
        const first = await api.getCompaniesFiltered({ ...effectiveFilters, page: p, page_size: PAGE_SIZE });
        acc.push(...first.companies);
        while (p < first.total_pages) {
          p += 1;
          const next = await api.getCompaniesFiltered({ ...effectiveFilters, page: p, page_size: PAGE_SIZE });
          acc.push(...next.companies);
        }
        setFindymailCompanies(acc);
        setFindymailOpen(true);
      } catch (e) {
        showFlash("err", `Recupero aziende fallito: ${e instanceof Error ? e.message : e}`);
      } finally {
        setFindymailPreparing(false);
      }
      return;
    }
    if (selectedIds.size > 0) {
      setFindymailCompanies(companies.filter((c) => selectedIds.has(c.id)));
    } else {
      setFindymailCompanies(companies);
    }
    setFindymailOpen(true);
  };

  /** Findymail company-info lookup — fills missing linkedin_url, industry,
   * location, email_domain. Same selection logic. */
  const openFindymailCompanyInfo = async () => {

    if (selectAllMatching) {
      setFindymailCoPreparing(true);
      try {
        const PAGE_SIZE = 200;
        const acc: Company[] = [];
        let p = 1;
        const first = await api.getCompaniesFiltered({ ...effectiveFilters, page: p, page_size: PAGE_SIZE });
        acc.push(...first.companies);
        while (p < first.total_pages) {
          p += 1;
          const next = await api.getCompaniesFiltered({ ...effectiveFilters, page: p, page_size: PAGE_SIZE });
          acc.push(...next.companies);
        }
        setFindymailCoCompanies(acc);
        setFindymailCoOpen(true);
      } catch (e) {
        showFlash("err", `Recupero aziende fallito: ${e instanceof Error ? e.message : e}`);
      } finally {
        setFindymailCoPreparing(false);
      }
      return;
    }
    if (selectedIds.size > 0) {
      setFindymailCoCompanies(companies.filter((c) => selectedIds.has(c.id)));
    } else {
      setFindymailCoCompanies(companies);
    }
    setFindymailCoOpen(true);
  };

  /** Findymail find-by-role — finds DMs matching given titles (1 round-trip
   * per company, returns name+email directly). Same selection logic. */
  const openFindymailFindDM = async () => {

    if (selectAllMatching) {
      setFindymailFindPreparing(true);
      try {
        const PAGE_SIZE = 200;
        const acc: Company[] = [];
        let p = 1;
        const first = await api.getCompaniesFiltered({ ...effectiveFilters, page: p, page_size: PAGE_SIZE });
        acc.push(...first.companies);
        while (p < first.total_pages) {
          p += 1;
          const next = await api.getCompaniesFiltered({ ...effectiveFilters, page: p, page_size: PAGE_SIZE });
          acc.push(...next.companies);
        }
        setFindymailFindCompanies(acc);
        setFindymailFindOpen(true);
      } catch (e) {
        showFlash("err", `Recupero aziende fallito: ${e instanceof Error ? e.message : e}`);
      } finally {
        setFindymailFindPreparing(false);
      }
      return;
    }
    if (selectedIds.size > 0) {
      setFindymailFindCompanies(companies.filter((c) => selectedIds.has(c.id)));
    } else {
      setFindymailFindCompanies(companies);
    }
    setFindymailFindOpen(true);
  };

  /** Findymail "find DM via LinkedIn" — chains /search/employees → /search/linkedin
   * to return name + LinkedIn URL + email in one shot. Same selection logic. */
  const openFindymailFindDMViaLinkedIn = async () => {

    if (selectAllMatching) {
      setFindymailLiPreparing(true);
      try {
        const PAGE_SIZE = 200;
        const acc: Company[] = [];
        let p = 1;
        const first = await api.getCompaniesFiltered({ ...effectiveFilters, page: p, page_size: PAGE_SIZE });
        acc.push(...first.companies);
        while (p < first.total_pages) {
          p += 1;
          const next = await api.getCompaniesFiltered({ ...effectiveFilters, page: p, page_size: PAGE_SIZE });
          acc.push(...next.companies);
        }
        setFindymailLiCompanies(acc);
        setFindymailLiOpen(true);
      } catch (e) {
        showFlash("err", `Recupero aziende fallito: ${e instanceof Error ? e.message : e}`);
      } finally {
        setFindymailLiPreparing(false);
      }
      return;
    }
    if (selectedIds.size > 0) {
      setFindymailLiCompanies(companies.filter((c) => selectedIds.has(c.id)));
    } else {
      setFindymailLiCompanies(companies);
    }
    setFindymailLiOpen(true);
  };

  /**
   * Export current selection (or all matching, or current page) as CSV.
   * Backend emits one row per company with all Clay-table columns + DMs +
   * lists + custom fields.
   */
  const exportCsv = async () => {
    setExportingCsv(true);
    try {
      let ids: number[];
      if (selectAllMatching) {
        ids = await api.getCompanyIdsFiltered(effectiveFilters);
      } else if (selectedIds.size > 0) {
        ids = Array.from(selectedIds);
      } else {
        ids = companies.map((c) => c.id);
      }
      if (ids.length === 0) {
        showFlash("err", "Niente da esportare");
        return;
      }
      const blob = await api.bulkExportCompanies(ids);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const stamp = new Date().toISOString().slice(0, 10);
      a.download = `miriade_companies_${stamp}_${ids.length}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showFlash("ok", `Esportate ${ids.length} aziende`);
    } catch (e) {
      showFlash("err", `Export fallito: ${e instanceof Error ? e.message : e}`);
    } finally {
      setExportingCsv(false);
    }
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
    action: "find_dm" | "enrich" | "push_to_campaign" | "delete",
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

  /** Inline edit of a top-level Company field from the Clay table cells. */
  const handleCompanyFieldSave = async (
    companyId: number,
    field: "name" | "website" | "linkedin_url" | "industry" | "province" | "location" | "revenue" | "employee_count",
    value: string | number | null,
  ) => {
    try {
      const updated = await api.updateCompany(companyId, { [field]: value });
      setCompanies((cs) => cs.map((c) => (c.id === companyId ? updated : c)));
    } catch (e) {
      showFlash("err", `Save fallito: ${e instanceof Error ? e.message : e}`);
    }
  };

  /** Replace a company's email + generic_emails list (Email Aziendali popover). */
  const handleCompanyEmailsSave = async (
    companyId: number,
    primary: string | null,
    generic: string[],
  ) => {
    try {
      const updated = await api.updateCompany(companyId, {
        email: primary,
        generic_emails: generic,
      });
      setCompanies((cs) => cs.map((c) => (c.id === companyId ? updated : c)));
    } catch (e) {
      showFlash("err", `Save email fallito: ${e instanceof Error ? e.message : e}`);
    }
  };

  /** Quick-create a Person linked to a company (Decision Makers "+ DM"). */
  const handleCreateCompanyPerson = async (
    companyId: number,
    payload: { first_name: string; last_name: string; email?: string | null; title?: string | null; linkedin_url?: string | null },
  ) => {
    try {
      await api.createCompanyPerson(companyId, payload);
      showFlash("ok", `Decision maker "${payload.first_name} ${payload.last_name}" creato`);
      // Reload current page so the new chip + work_emails column update.
      loadCompanies(page);
    } catch (e) {
      showFlash("err", `Creazione DM fallita: ${e instanceof Error ? e.message : e}`);
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
        collapsed={listsSidebarCollapsed}
        onToggleCollapsed={() => setListsSidebarCollapsed((v) => !v)}
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
              <Button variant="outline" size="sm" className="gap-1.5" onClick={() => setAddCompanyOpen(true)}>
                <Plus className="h-3.5 w-3.5" /> Aggiungi azienda
              </Button>
              <Button variant="outline" size="sm" className="gap-1.5" onClick={() => setCsvOpen(true)}>
                <Upload className="h-3.5 w-3.5" /> Import CSV
              </Button>
              <Button variant="outline" size="sm" className="gap-1.5"
                disabled={total === 0 || exportingCsv}
                onClick={exportCsv}
                title={
                  selectAllMatching
                    ? `Esporta ${total} aziende matching`
                    : selectedIds.size > 0
                    ? `Esporta ${selectedIds.size} selezionate`
                    : `Esporta pagina (${companies.length})`
                }>
                <Download className="h-3.5 w-3.5" />
                {exportingCsv ? "Esporto…" : "Export CSV"}
              </Button>
              <Button size="sm" className="gap-1.5"
                onClick={() => setEnrichmentDrawerOpen(true)}>
                <Sparkles className="h-3.5 w-3.5" />
                Arricchisci
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
                onClick={async () => {
                  const ids = await resolveSelectedIds();
                  setPushToCampaignTarget({ mode: "bulk", companyIds: ids });
                }}>
                <Tag className="h-3.5 w-3.5" /> Aggiungi DM a campagna…
              </Button>
              <Button size="sm" variant="outline" className="gap-1.5 text-destructive" onClick={handleBulkDelete}>
                <Trash2 className="h-3.5 w-3.5" /> Delete
              </Button>
              <Button size="sm" variant="ghost"
                onClick={() => { setSelectedIds(new Set()); setSelectAllMatching(false); }}>
                Clear
              </Button>
              <Button size="sm" className="ml-auto gap-1.5"
                disabled={bulkScrapePreparing || linkedInDMPreparing || findymailPreparing || findymailFindPreparing || findymailLiPreparing || findymailCoPreparing}
                onClick={() => setEnrichmentDrawerOpen(true)}>
                <Sparkles className="h-3.5 w-3.5" />
                {bulkScrapePreparing || linkedInDMPreparing || findymailPreparing || findymailFindPreparing || findymailLiPreparing || findymailCoPreparing
                  ? "Preparo…"
                  : "Arricchisci"}
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
            onCompanyFieldSave={handleCompanyFieldSave}
            onCompanyEmailsSave={handleCompanyEmailsSave}
            onCreateCompanyPerson={handleCreateCompanyPerson}
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

          <AddCompanyDialog
            open={addCompanyOpen}
            onOpenChange={setAddCompanyOpen}
            onCompleted={() => { loadCompanies(1); setListsRefreshKey((k) => k + 1); }}
          />

          <BulkScrapeDialog
            open={bulkScrapeOpen}
            onOpenChange={setBulkScrapeOpen}
            companies={bulkScrapeCompanies}
            onCompleted={() => loadCompanies(page)}
          />

          <LinkedInFindDMDialog
            open={linkedInDMOpen}
            onOpenChange={setLinkedInDMOpen}
            companies={linkedInDMCompanies}
            onCompleted={() => loadCompanies(page)}
          />

          <FindymailEnrichDialog
            open={findymailOpen}
            onOpenChange={setFindymailOpen}
            companies={findymailCompanies}
            onCompleted={() => { loadCompanies(page); setListsRefreshKey((k) => k + 1); }}
            onPushToCampaign={(ids) => setPushToCampaignTarget({ mode: "bulk", companyIds: ids })}
          />

          <FindymailFindDMDialog
            open={findymailFindOpen}
            onOpenChange={setFindymailFindOpen}
            companies={findymailFindCompanies}
            onCompleted={() => { loadCompanies(page); setListsRefreshKey((k) => k + 1); }}
            onPushToCampaign={(ids) => setPushToCampaignTarget({ mode: "bulk", companyIds: ids })}
          />

          <FindymailFindDMViaLinkedInDialog
            open={findymailLiOpen}
            onOpenChange={setFindymailLiOpen}
            companies={findymailLiCompanies}
            onCompleted={() => { loadCompanies(page); setListsRefreshKey((k) => k + 1); }}
            onPushToCampaign={(ids) => setPushToCampaignTarget({ mode: "bulk", companyIds: ids })}
          />

          <ApolloSearchPeopleDialog
            open={apolloPeopleOpen}
            onOpenChange={setApolloPeopleOpen}
            onCompleted={() => { loadCompanies(page); setListsRefreshKey((k) => k + 1); }}
          />

          <EnrichmentDrawer
            open={enrichmentDrawerOpen}
            onOpenChange={setEnrichmentDrawerOpen}
            hasSelection={selectAllMatching || selectedIds.size > 0}
            selectionLabel={
              selectAllMatching
                ? `${total.toLocaleString("it-IT")} matching`
                : selectedIds.size > 0
                ? `${selectedIds.size} selezionate`
                : ""
            }
            onApolloSearchPeople={() => setApolloPeopleOpen(true)}
            onBulkScrape={openBulkScrape}
            onFindymailCompanyInfo={openFindymailCompanyInfo}
            onLinkedInDM={openLinkedInDM}
            onFindymailFindDM={openFindymailFindDM}
            onFindymailFindDMViaLinkedIn={openFindymailFindDMViaLinkedIn}
            onFindymail={openFindymail}
          />

          <FindymailFindCompanyInfoDialog
            open={findymailCoOpen}
            onOpenChange={setFindymailCoOpen}
            companies={findymailCoCompanies}
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
