"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { Upload, Search, X, ListPlus, Send, Sparkles, Loader2, Filter, Trash2, Download, List } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PeopleTable } from "@/components/leads/people-table";
import { CompaniesTable } from "@/components/leads/companies-table";
import { PeopleCSVDialog } from "@/components/leads/people-csv-dialog";
import { CompaniesCSVDialog } from "@/components/leads/companies-csv-dialog";
import { EditPersonDialog } from "@/components/leads/edit-person-dialog";
import { CompanyDetailDialog } from "@/components/leads/company-detail-dialog";
import { PersonDetailDialog } from "@/components/leads/person-detail-dialog";
import { CreateListDialog } from "@/components/leads/create-list-dialog";
import { AddListToCampaignDialog } from "@/components/leads/add-list-to-campaign-dialog";
import { FindPeopleDialog } from "@/components/leads/find-people-dialog";
import { PaginationControls } from "@/components/ui/pagination-controls";
import { api } from "@/lib/api";
import {
  Person,
  Company,
  LeadList,
  PersonListResponse,
  CompanyListResponse,
} from "@/types";

type Tab = "people" | "companies" | "lists";

export default function LeadsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("people");

  // --- People state ---
  const [people, setPeople] = useState<Person[]>([]);
  const [peopleLoading, setPeopleLoading] = useState(false);
  const [peopleSearch, setPeopleSearch] = useState("");
  const [filterCompanyId, setFilterCompanyId] = useState<number | null>(null);
  const [peopleIndustry, setPeopleIndustry] = useState<string>("");
  const [peopleIndustries, setPeopleIndustries] = useState<string[]>([]);
  const [peopleClientTag, setPeopleClientTag] = useState<string>("");
  const [peopleCSVOpen, setPeopleCSVOpen] = useState(false);
  const [peoplePage, setPeoplePage] = useState(1);
  const [peopleTotal, setPeopleTotal] = useState(0);
  const [peopleTotalPages, setPeopleTotalPages] = useState(1);

  // --- People selection ---
  const [selectedPeopleIds, setSelectedPeopleIds] = useState<Set<number>>(new Set());
  const [createListOpen, setCreateListOpen] = useState(false);
  const [addToCampaignOpen, setAddToCampaignOpen] = useState(false);
  const [lastCreatedListId, setLastCreatedListId] = useState<number | null>(null);
  const [editingPerson, setEditingPerson] = useState<Person | null>(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);

  // --- Companies state ---
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companiesLoading, setCompaniesLoading] = useState(false);
  const [companiesSearch, setCompaniesSearch] = useState("");
  const [companiesIndustry, setCompaniesIndustry] = useState<string>("");
  const [companiesIndustries, setCompaniesIndustries] = useState<string[]>([]);
  const [companiesClientTag, setCompaniesClientTag] = useState<string>("");
  const [companiesCSVOpen, setCompaniesCSVOpen] = useState(false);
  const [companiesPage, setCompaniesPage] = useState(1);
  const [companiesTotal, setCompaniesTotal] = useState(0);
  const [companiesTotalPages, setCompaniesTotalPages] = useState(1);

  // --- Companies selection ---
  const [selectedCompanyIds, setSelectedCompanyIds] = useState<Set<number>>(new Set());

  // --- People enrichment ---
  const [enriching, setEnriching] = useState(false);
  const [enrichResult, setEnrichResult] = useState<{ enriched_count: number; credits_consumed: number; message: string } | null>(null);

  // --- Detail dialogs ---
  const [detailCompany, setDetailCompany] = useState<Company | null>(null);
  const [companyDetailOpen, setCompanyDetailOpen] = useState(false);
  const [detailPerson, setDetailPerson] = useState<Person | null>(null);
  const [personDetailOpen, setPersonDetailOpen] = useState(false);

  // --- Find People dialog ---
  const [findPeopleCompany, setFindPeopleCompany] = useState<Company | null>(null);
  const [findPeopleOpen, setFindPeopleOpen] = useState(false);

  // --- Lists state ---
  const [lists, setLists] = useState<LeadList[]>([]);
  const [listsLoading, setListsLoading] = useState(false);
  const [addListToCampaignListId, setAddListToCampaignListId] = useState<number | null>(null);

  // --- Presence filters ---
  type PresenceFilters = Record<string, boolean | undefined>;
  const [peoplePresence, setPeoplePresence] = useState<PresenceFilters>({});
  const [companiesPresence, setCompaniesPresence] = useState<PresenceFilters>({});
  const peoplePresenceRef = useRef<PresenceFilters>({});
  const companiesPresenceRef = useRef<PresenceFilters>({});
  peoplePresenceRef.current = peoplePresence;
  companiesPresenceRef.current = companiesPresence;

  const peoplePresenceCount = Object.values(peoplePresence).filter((v) => v !== undefined).length;
  const companiesPresenceCount = Object.values(companiesPresence).filter((v) => v !== undefined).length;

  // Load data and industries on mount
  useEffect(() => {
    loadPeople();
    loadCompanies();
    loadLists();
    loadPeopleIndustries();
    loadCompaniesIndustries();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Clear selection when data changes
  useEffect(() => {
    setSelectedPeopleIds(new Set());
  }, [people]);

  useEffect(() => {
    setSelectedCompanyIds(new Set());
  }, [companies]);

  // --- People ---
  const loadPeopleIndustries = useCallback(async () => {
    try {
      const data = await api.get<string[]>("/people/industries");
      setPeopleIndustries(data);
    } catch (err) {
      console.error("Failed to load people industries:", err);
    }
  }, []);

  const loadPeople = useCallback(async (search?: string, companyId?: number | null, industry?: string, clientTag?: string, page: number = 1) => {
    setPeopleLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", "50");
      if (search) params.set("search", search);
      if (companyId != null) params.set("company_id", String(companyId));
      if (industry) params.set("industry", industry);
      if (clientTag) params.set("client_tag", clientTag);
      // Presence filters from ref
      for (const [k, v] of Object.entries(peoplePresenceRef.current)) {
        if (v !== undefined) params.set(k, String(v));
      }
      const qs = params.toString();
      const data = await api.get<PersonListResponse>(`/people${qs ? `?${qs}` : ""}`);
      setPeople(data.people);
      setPeoplePage(data.page);
      setPeopleTotal(data.total);
      setPeopleTotalPages(data.total_pages);
    } catch (err) {
      console.error("Failed to load people:", err);
    } finally {
      setPeopleLoading(false);
    }
  }, []);

  const handlePeopleSearch = (value: string) => {
    setPeopleSearch(value);
    loadPeople(value, filterCompanyId, peopleIndustry, peopleClientTag);
  };

  const handlePeopleIndustryChange = (value: string) => {
    setPeopleIndustry(value);
    loadPeople(peopleSearch, filterCompanyId, value, peopleClientTag);
  };

  const handlePeopleClientTagChange = (value: string) => {
    setPeopleClientTag(value);
    loadPeople(peopleSearch, filterCompanyId, peopleIndustry, value);
  };

  const handleDeletePerson = async (id: number) => {
    if (!confirm("Delete this person?")) return;
    try {
      await api.delete(`/people/${id}`);
      setPeople((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      console.error("Failed to delete person:", err);
    }
  };

  const handleEditPerson = (person: Person) => {
    setEditingPerson(person);
    setEditDialogOpen(true);
  };

  const handleToggleConverted = async (person: Person) => {
    try {
      const updated = await api.updatePerson(person.id, {
        converted: !person.converted_at,
      });
      setPeople((prev) => prev.map((p) => (p.id === person.id ? updated : p)));
    } catch (err) {
      console.error("Failed to toggle converted:", err);
    }
  };

  const handlePeopleCompanyClick = (_companyId: number) => {
    setActiveTab("companies");
  };

  // --- People selection ---
  const handleToggleSelect = (id: number) => {
    setSelectedPeopleIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleToggleSelectAll = () => {
    if (people.every((p) => selectedPeopleIds.has(p.id))) {
      setSelectedPeopleIds(new Set());
    } else {
      setSelectedPeopleIds(new Set(people.map((p) => p.id)));
    }
  };

  const handleListCreated = (listId: number) => {
    setLastCreatedListId(listId);
    setAddListToCampaignListId(listId);
    setCreateListOpen(false);
    setAddToCampaignOpen(true);
    loadLists();
  };

  const handleBulkEnrich = async () => {
    if (selectedPeopleIds.size === 0) return;
    setEnriching(true);
    setEnrichResult(null);
    try {
      const result = await api.bulkEnrichPeople(Array.from(selectedPeopleIds));
      setEnrichResult(result);
      setSelectedPeopleIds(new Set());
      loadPeople(peopleSearch, filterCompanyId, peopleIndustry, peopleClientTag);
    } catch (err) {
      console.error("Bulk enrich failed:", err);
    } finally {
      setEnriching(false);
    }
  };

  // --- Companies selection ---
  const handleToggleCompanySelect = (id: number) => {
    setSelectedCompanyIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleToggleCompanySelectAll = () => {
    if (companies.every((c) => selectedCompanyIds.has(c.id))) {
      setSelectedCompanyIds(new Set());
    } else {
      setSelectedCompanyIds(new Set(companies.map((c) => c.id)));
    }
  };

  const handleCompanyDetailClick = (company: Company) => {
    setDetailCompany(company);
    setCompanyDetailOpen(true);
  };

  const handlePersonDetailClick = (person: Person) => {
    setDetailPerson(person);
    setPersonDetailOpen(true);
  };

  const handleDetailPersonCompanyClick = (companyId: number) => {
    setPersonDetailOpen(false);
    const company = companies.find((c) => c.id === companyId);
    if (company) {
      setDetailCompany(company);
      setCompanyDetailOpen(true);
    }
  };

  const handleDetailCompanyPersonClick = (personId: number) => {
    setCompanyDetailOpen(false);
    const person = people.find((p) => p.id === personId);
    if (person) {
      setDetailPerson(person);
      setPersonDetailOpen(true);
    }
  };

  const handleFindPeople = (company: Company) => {
    setFindPeopleCompany(company);
    setFindPeopleOpen(true);
  };

  // --- Presence filter handlers ---
  const handlePeoplePresenceChange = (key: string, val: boolean | undefined) => {
    const next = { ...peoplePresence };
    if (val === undefined) delete next[key];
    else next[key] = val;
    setPeoplePresence(next);
    peoplePresenceRef.current = next;
    loadPeople(peopleSearch, filterCompanyId, peopleIndustry, peopleClientTag);
  };

  const handleCompaniesPresenceChange = (key: string, val: boolean | undefined) => {
    const next = { ...companiesPresence };
    if (val === undefined) delete next[key];
    else next[key] = val;
    setCompaniesPresence(next);
    companiesPresenceRef.current = next;
    loadCompanies(companiesSearch, companiesIndustry, companiesClientTag);
  };

  // --- Lists ---
  const loadLists = useCallback(async () => {
    setListsLoading(true);
    try {
      const data = await api.getLeadLists();
      setLists(data.lists);
    } catch (err) {
      console.error("Failed to load lists:", err);
    } finally {
      setListsLoading(false);
    }
  }, []);

  const handleDeleteList = async (id: number) => {
    if (!confirm("Delete this list?")) return;
    try {
      await api.deleteLeadList(id);
      setLists((prev) => prev.filter((l) => l.id !== id));
    } catch (err) {
      console.error("Failed to delete list:", err);
    }
  };

  const handleExportList = async (id: number) => {
    try {
      const blob = await api.exportLeadList(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `lead-list-${id}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to export list:", err);
    }
  };

  const handleAddListToCampaign = (listId: number) => {
    setAddListToCampaignListId(listId);
    setAddToCampaignOpen(true);
  };

  // --- Companies ---
  const loadCompaniesIndustries = useCallback(async () => {
    try {
      const data = await api.get<string[]>("/companies/industries");
      setCompaniesIndustries(data);
    } catch (err) {
      console.error("Failed to load companies industries:", err);
    }
  }, []);

  const loadCompanies = useCallback(async (search?: string, industry?: string, clientTag?: string, page: number = 1) => {
    setCompaniesLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", "50");
      if (search) params.set("search", search);
      if (industry) params.set("industry", industry);
      if (clientTag) params.set("client_tag", clientTag);
      // Presence filters from ref
      for (const [k, v] of Object.entries(companiesPresenceRef.current)) {
        if (v !== undefined) params.set(k, String(v));
      }
      const qs = params.toString();
      const data = await api.get<CompanyListResponse>(`/companies${qs ? `?${qs}` : ""}`);
      setCompanies(data.companies);
      setCompaniesPage(data.page);
      setCompaniesTotal(data.total);
      setCompaniesTotalPages(data.total_pages);
    } catch (err) {
      console.error("Failed to load companies:", err);
    } finally {
      setCompaniesLoading(false);
    }
  }, []);

  const handleCompaniesSearch = (value: string) => {
    setCompaniesSearch(value);
    loadCompanies(value, companiesIndustry, companiesClientTag);
  };

  const handleCompaniesIndustryChange = (value: string) => {
    setCompaniesIndustry(value);
    loadCompanies(companiesSearch, value, companiesClientTag);
  };

  const handleCompaniesClientTagChange = (value: string) => {
    setCompaniesClientTag(value);
    loadCompanies(companiesSearch, companiesIndustry, value);
  };

  const handleDeleteCompany = async (id: number) => {
    if (!confirm("Delete this company? People linked to it will be unlinked.")) return;
    try {
      await api.delete(`/companies/${id}`);
      setCompanies((prev) => prev.filter((c) => c.id !== id));
      loadPeople(peopleSearch, filterCompanyId, peopleIndustry, peopleClientTag);
    } catch (err) {
      console.error("Failed to delete company:", err);
    }
  };

  const handlePeopleClick = (companyId: number) => {
    setFilterCompanyId(companyId);
    setActiveTab("people");
    loadPeople(peopleSearch, companyId, peopleIndustry, peopleClientTag);
  };

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: "people", label: "People", count: peopleTotal },
    { key: "companies", label: "Companies", count: companiesTotal },
    { key: "lists", label: "Lists", count: lists.length },
  ];

  return (
    <div>
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Leads</h1>
          <p className="text-sm text-muted-foreground">
            {activeTab === "people" && `${peopleTotal} people${filterCompanyId ? " (filtered by company)" : ""}${peopleIndustry ? ` in ${peopleIndustry}` : ""}${peopleClientTag ? ` \u00b7 tag: ${peopleClientTag}` : ""}`}
            {activeTab === "companies" && `${companiesTotal} companies${companiesIndustry ? ` in ${companiesIndustry}` : ""}${companiesClientTag ? ` \u00b7 tag: ${companiesClientTag}` : ""}`}
            {activeTab === "lists" && `${lists.length} lead lists`}
          </p>
        </div>

        {/* Tab-specific actions */}
        <div className="flex flex-wrap items-center gap-3">
          {activeTab === "people" && (
            <>
              {filterCompanyId && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => { setFilterCompanyId(null); loadPeople(peopleSearch, null, peopleIndustry, peopleClientTag); }}
                >
                  Clear company filter
                </Button>
              )}
              {peopleIndustry && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => { setPeopleIndustry(""); loadPeople(peopleSearch, filterCompanyId, "", peopleClientTag); }}
                >
                  <X className="h-3 w-3 mr-1" /> Clear industry
                </Button>
              )}
              {peopleClientTag && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => { setPeopleClientTag(""); loadPeople(peopleSearch, filterCompanyId, peopleIndustry, ""); }}
                >
                  <X className="h-3 w-3 mr-1" /> Clear client tag
                </Button>
              )}
              <Select value={peopleIndustry || undefined} onValueChange={handlePeopleIndustryChange}>
                <SelectTrigger className="w-[160px]">
                  <SelectValue placeholder="All Industries" />
                </SelectTrigger>
                <SelectContent>
                  {peopleIndustries?.filter((v) => v && v.trim()).map((industry) => (
                    <SelectItem key={industry} value={industry}>
                      {industry}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div className="relative">
                <input
                  type="text"
                  placeholder="Client tag..."
                  value={peopleClientTag}
                  onChange={(e) => handlePeopleClientTagChange(e.target.value)}
                  className="px-3 py-1.5 text-sm border border-input rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring w-[140px]"
                />
              </div>
              <div className="relative">
                <Search className="absolute left-2 top-2 h-4 w-4 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search people..."
                  value={peopleSearch}
                  onChange={(e) => handlePeopleSearch(e.target.value)}
                  className="pl-8 pr-3 py-1.5 text-sm border border-input rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring w-[180px]"
                />
              </div>
              <Button onClick={() => setPeopleCSVOpen(true)} className="gap-1">
                <Upload className="h-4 w-4" /> Import CSV
              </Button>
            </>
          )}
          {activeTab === "companies" && (
            <>
              {companiesIndustry && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => { setCompaniesIndustry(""); loadCompanies(companiesSearch, "", companiesClientTag); }}
                >
                  <X className="h-3 w-3 mr-1" /> Clear industry
                </Button>
              )}
              {companiesClientTag && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => { setCompaniesClientTag(""); loadCompanies(companiesSearch, companiesIndustry, ""); }}
                >
                  <X className="h-3 w-3 mr-1" /> Clear client tag
                </Button>
              )}
              <Select value={companiesIndustry || undefined} onValueChange={handleCompaniesIndustryChange}>
                <SelectTrigger className="w-[160px]">
                  <SelectValue placeholder="All Industries" />
                </SelectTrigger>
                <SelectContent>
                  {companiesIndustries?.filter((v) => v && v.trim()).map((industry) => (
                    <SelectItem key={industry} value={industry}>
                      {industry}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div className="relative">
                <input
                  type="text"
                  placeholder="Client tag..."
                  value={companiesClientTag}
                  onChange={(e) => handleCompaniesClientTagChange(e.target.value)}
                  className="px-3 py-1.5 text-sm border border-input rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring w-[140px]"
                />
              </div>
              <div className="relative">
                <Search className="absolute left-2 top-2 h-4 w-4 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search companies..."
                  value={companiesSearch}
                  onChange={(e) => handleCompaniesSearch(e.target.value)}
                  className="pl-8 pr-3 py-1.5 text-sm border border-input rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-ring w-[180px]"
                />
              </div>
              <Button onClick={() => setCompaniesCSVOpen(true)} className="gap-1">
                <Upload className="h-4 w-4" /> Import CSV
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Presence Filter Row - People */}
      {activeTab === "people" && (
        <div className="flex items-center gap-3 mb-3 flex-wrap">
          <span className="text-xs font-medium text-muted-foreground flex items-center gap-1">
            <Filter className="h-3 w-3" /> Filters:
          </span>
          {[
            { key: "has_email", label: "Email" },
            { key: "has_phone", label: "Phone" },
            { key: "has_linkedin", label: "LinkedIn" },
          ].map(({ key, label }) => (
            <Select
              key={key}
              value={peoplePresence[key] === true ? "has" : peoplePresence[key] === false ? "missing" : "any"}
              onValueChange={(v) => handlePeoplePresenceChange(key, v === "has" ? true : v === "missing" ? false : undefined)}
            >
              <SelectTrigger className="w-[120px] h-7 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="any">{label}: Any</SelectItem>
                <SelectItem value="has">{label}: Has</SelectItem>
                <SelectItem value="missing">{label}: Missing</SelectItem>
              </SelectContent>
            </Select>
          ))}
          {peoplePresenceCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs gap-1"
              onClick={() => { setPeoplePresence({}); peoplePresenceRef.current = {}; loadPeople(peopleSearch, filterCompanyId, peopleIndustry, peopleClientTag); }}
            >
              <X className="h-3 w-3" /> Clear filters
            </Button>
          )}
        </div>
      )}

      {/* Presence Filter Row - Companies */}
      {activeTab === "companies" && (
        <div className="flex items-center gap-3 mb-3 flex-wrap">
          <span className="text-xs font-medium text-muted-foreground flex items-center gap-1">
            <Filter className="h-3 w-3" /> Filters:
          </span>
          {[
            { key: "has_email", label: "Email" },
            { key: "has_phone", label: "Phone" },
            { key: "has_linkedin", label: "LinkedIn" },
            { key: "has_website", label: "Website" },
          ].map(({ key, label }) => (
            <Select
              key={key}
              value={companiesPresence[key] === true ? "has" : companiesPresence[key] === false ? "missing" : "any"}
              onValueChange={(v) => handleCompaniesPresenceChange(key, v === "has" ? true : v === "missing" ? false : undefined)}
            >
              <SelectTrigger className="w-[130px] h-7 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="any">{label}: Any</SelectItem>
                <SelectItem value="has">{label}: Has</SelectItem>
                <SelectItem value="missing">{label}: Missing</SelectItem>
              </SelectContent>
            </Select>
          ))}
          {companiesPresenceCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs gap-1"
              onClick={() => { setCompaniesPresence({}); companiesPresenceRef.current = {}; loadCompanies(companiesSearch, companiesIndustry, companiesClientTag); }}
            >
              <X className="h-3 w-3" /> Clear filters
            </Button>
          )}
        </div>
      )}

      {/* People Selection Toolbar */}
      {activeTab === "people" && selectedPeopleIds.size > 0 && (
        <div className="flex items-center gap-3 p-3 bg-primary/5 rounded-lg border border-primary/20 mb-4">
          <span className="text-sm font-medium">
            {selectedPeopleIds.size} selected
          </span>
          <div className="h-4 w-px bg-border" />
          <Button
            size="sm"
            variant="default"
            className="gap-1.5"
            onClick={() => setCreateListOpen(true)}
          >
            <ListPlus className="h-3.5 w-3.5" />
            Create List
          </Button>
          <Button
            size="sm"
            variant="secondary"
            className="gap-1.5"
            disabled={enriching}
            onClick={handleBulkEnrich}
          >
            {enriching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
            {enriching ? "Enriching..." : `Enrich (${selectedPeopleIds.size})`}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setSelectedPeopleIds(new Set())}
          >
            Clear selection
          </Button>
        </div>
      )}

      {/* Enrich result banner */}
      {enrichResult && (
        <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-lg border border-blue-200 mb-4 text-sm">
          <Sparkles className="h-4 w-4 text-blue-600" />
          <span>{enrichResult.message}</span>
          <Button size="sm" variant="ghost" className="ml-auto h-6 text-xs" onClick={() => setEnrichResult(null)}>
            <X className="h-3 w-3" />
          </Button>
        </div>
      )}

      {/* Companies Selection Toolbar */}
      {activeTab === "companies" && selectedCompanyIds.size > 0 && (
        <div className="flex items-center gap-3 p-3 bg-primary/5 rounded-lg border border-primary/20 mb-4">
          <span className="text-sm font-medium">
            {selectedCompanyIds.size} selected
          </span>
          <div className="h-4 w-px bg-border" />
          <Button
            size="sm"
            variant="default"
            className="gap-1.5"
            onClick={() => setCreateListOpen(true)}
          >
            <ListPlus className="h-3.5 w-3.5" />
            Create List
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setSelectedCompanyIds(new Set())}
          >
            Clear selection
          </Button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b mb-4">
        {tabs.map(({ key, label, count }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === key
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {label}
            <span className={`ml-1.5 text-xs px-1.5 py-0.5 rounded-full ${
              activeTab === key ? "bg-primary/10" : "bg-muted"
            }`}>
              {count}
            </span>
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "people" && (
        <>
          <PeopleTable
            people={people}
            loading={peopleLoading}
            selectedIds={selectedPeopleIds}
            onToggleSelect={handleToggleSelect}
            onToggleSelectAll={handleToggleSelectAll}
            onDelete={handleDeletePerson}
            onCompanyClick={handlePeopleCompanyClick}
            onEdit={handleEditPerson}
            onToggleConverted={handleToggleConverted}
            onPersonClick={handlePersonDetailClick}
          />
          <PaginationControls
            page={peoplePage}
            totalPages={peopleTotalPages}
            total={peopleTotal}
            pageSize={50}
            onPageChange={(p) => loadPeople(peopleSearch, filterCompanyId, peopleIndustry, peopleClientTag, p)}
          />
        </>
      )}

      {activeTab === "companies" && (
        <>
          <CompaniesTable
            companies={companies}
            loading={companiesLoading}
            selectedIds={selectedCompanyIds}
            onToggleSelect={handleToggleCompanySelect}
            onToggleSelectAll={handleToggleCompanySelectAll}
            onDelete={handleDeleteCompany}
            onPeopleClick={handlePeopleClick}
            onFindPeople={handleFindPeople}
            onRefresh={() => loadCompanies(companiesSearch, companiesIndustry, companiesClientTag)}
            onCompanyClick={handleCompanyDetailClick}
          />
          <PaginationControls
            page={companiesPage}
            totalPages={companiesTotalPages}
            total={companiesTotal}
            pageSize={50}
            onPageChange={(p) => loadCompanies(companiesSearch, companiesIndustry, companiesClientTag, p)}
          />
        </>
      )}

      {activeTab === "lists" && (
        listsLoading ? (
          <p className="text-muted-foreground py-8 text-center">Loading...</p>
        ) : lists.length === 0 ? (
          <div className="text-center py-12">
            <List className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
            <p className="text-muted-foreground">
              No lists yet. Select people or companies and click &ldquo;Create List&rdquo;.
            </p>
          </div>
        ) : (
          <div className="rounded-md border overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Name</th>
                  <th className="px-4 py-2 text-left font-medium">Client/Project</th>
                  <th className="px-4 py-2 text-center font-medium">People</th>
                  <th className="px-4 py-2 text-center font-medium">Companies</th>
                  <th className="px-4 py-2 text-left font-medium">Created</th>
                  <th className="px-4 py-2 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {lists.map((list) => (
                  <tr key={list.id} className="border-t">
                    <td className="px-4 py-2 font-medium">{list.name}</td>
                    <td className="px-4 py-2 text-muted-foreground">{list.client_tag || "—"}</td>
                    <td className="px-4 py-2 text-center">{list.people_count}</td>
                    <td className="px-4 py-2 text-center">{list.companies_count}</td>
                    <td className="px-4 py-2 text-muted-foreground">
                      {new Date(list.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-2 text-right space-x-1">
                      <Button
                        size="sm"
                        variant="outline"
                        className="gap-1 h-7 text-xs"
                        onClick={() => handleAddListToCampaign(list.id)}
                      >
                        <Send className="h-3 w-3" /> Add to Campaign
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="gap-1 h-7 text-xs"
                        onClick={() => handleExportList(list.id)}
                      >
                        <Download className="h-3 w-3" /> Export
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                        onClick={() => handleDeleteList(list.id)}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {/* Dialogs */}
      <PeopleCSVDialog
        open={peopleCSVOpen}
        onOpenChange={setPeopleCSVOpen}
        onImportComplete={() => loadPeople(peopleSearch, filterCompanyId, peopleIndustry, peopleClientTag)}
      />

      <CompaniesCSVDialog
        open={companiesCSVOpen}
        onOpenChange={setCompaniesCSVOpen}
        onImportComplete={() => { loadCompanies(companiesSearch, companiesIndustry, companiesClientTag); loadPeople(peopleSearch, filterCompanyId, peopleIndustry, peopleClientTag); }}
      />

      <EditPersonDialog
        person={editingPerson}
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        onUpdated={() => loadPeople(peopleSearch, filterCompanyId, peopleIndustry, peopleClientTag)}
      />

      <CreateListDialog
        open={createListOpen}
        onOpenChange={setCreateListOpen}
        selectedPersonIds={activeTab === "people" ? Array.from(selectedPeopleIds) : []}
        selectedCompanyIds={activeTab === "companies" ? Array.from(selectedCompanyIds) : []}
        defaultClientTag={activeTab === "people" ? peopleClientTag : companiesClientTag}
        onListCreated={handleListCreated}
      />

      <AddListToCampaignDialog
        open={addToCampaignOpen}
        onOpenChange={setAddToCampaignOpen}
        leadListId={addListToCampaignListId}
      />

      <FindPeopleDialog
        open={findPeopleOpen}
        onOpenChange={setFindPeopleOpen}
        company={findPeopleCompany}
        onImported={() => loadPeople(peopleSearch, filterCompanyId, peopleIndustry, peopleClientTag)}
      />

      <CompanyDetailDialog
        company={detailCompany}
        open={companyDetailOpen}
        onOpenChange={setCompanyDetailOpen}
        onPersonClick={handleDetailCompanyPersonClick}
        onUpdated={() => loadCompanies(companiesSearch, companiesIndustry, companiesClientTag)}
      />

      <PersonDetailDialog
        person={detailPerson}
        open={personDetailOpen}
        onOpenChange={setPersonDetailOpen}
        onCompanyClick={handleDetailPersonCompanyClick}
        onUpdated={() => loadPeople(peopleSearch, filterCompanyId, peopleIndustry, peopleClientTag)}
      />
    </div>
  );
}
