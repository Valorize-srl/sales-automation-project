"use client";

import { useEffect, useState, useCallback } from "react";
import { Upload, Search, X } from "lucide-react";
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
import { api } from "@/lib/api";
import {
  Person,
  Company,
  PersonListResponse,
  CompanyListResponse,
} from "@/types";

type Tab = "people" | "companies";

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

  // --- Companies state ---
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companiesLoading, setCompaniesLoading] = useState(false);
  const [companiesSearch, setCompaniesSearch] = useState("");
  const [companiesIndustry, setCompaniesIndustry] = useState<string>("");
  const [companiesIndustries, setCompaniesIndustries] = useState<string[]>([]);
  const [companiesClientTag, setCompaniesClientTag] = useState<string>("");
  const [companiesCSVOpen, setCompaniesCSVOpen] = useState(false);

  // Load data and industries on mount
  useEffect(() => {
    loadPeople();
    loadCompanies();
    loadPeopleIndustries();
    loadCompaniesIndustries();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // --- People ---
  const loadPeopleIndustries = useCallback(async () => {
    try {
      const data = await api.get<string[]>("/people/industries");
      setPeopleIndustries(data);
    } catch (err) {
      console.error("Failed to load people industries:", err);
    }
  }, []);

  const loadPeople = useCallback(async (search?: string, companyId?: number | null, industry?: string, clientTag?: string) => {
    setPeopleLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (companyId != null) params.set("company_id", String(companyId));
      if (industry) params.set("industry", industry);
      if (clientTag) params.set("client_tag", clientTag);
      const qs = params.toString();
      const data = await api.get<PersonListResponse>(`/people${qs ? `?${qs}` : ""}`);
      setPeople(data.people);
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

  const handlePeopleCompanyClick = (_companyId: number) => {
    setActiveTab("companies");
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

  const loadCompanies = useCallback(async (search?: string, industry?: string, clientTag?: string) => {
    setCompaniesLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (industry) params.set("industry", industry);
      if (clientTag) params.set("client_tag", clientTag);
      const qs = params.toString();
      const data = await api.get<CompanyListResponse>(`/companies${qs ? `?${qs}` : ""}`);
      setCompanies(data.companies);
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
    { key: "people", label: "People", count: people.length },
    { key: "companies", label: "Companies", count: companies.length },
  ];

  return (
    <div>
      {/* Page Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Leads</h1>
          <p className="text-sm text-muted-foreground">
            {activeTab === "people" && `${people.length} people${filterCompanyId ? " (filtered by company)" : ""}${peopleIndustry ? ` in ${peopleIndustry}` : ""}${peopleClientTag ? ` · tag: ${peopleClientTag}` : ""}`}
            {activeTab === "companies" && `${companies.length} companies${companiesIndustry ? ` in ${companiesIndustry}` : ""}${companiesClientTag ? ` · tag: ${companiesClientTag}` : ""}`}
          </p>
        </div>

        {/* Tab-specific actions */}
        <div className="flex items-center gap-3">
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
                  {peopleIndustries?.filter(Boolean).map((industry) => (
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
                  {companiesIndustries?.filter(Boolean).map((industry) => (
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
        <PeopleTable
          people={people}
          loading={peopleLoading}
          onDelete={handleDeletePerson}
          onCompanyClick={handlePeopleCompanyClick}
        />
      )}

      {activeTab === "companies" && (
        <CompaniesTable
          companies={companies}
          loading={companiesLoading}
          onDelete={handleDeleteCompany}
          onPeopleClick={handlePeopleClick}
          onRefresh={() => loadCompanies(companiesSearch, companiesIndustry, companiesClientTag)}
        />
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
    </div>
  );
}
