"use client";

import { useEffect, useState, useCallback } from "react";
import { Upload, Search, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { LeadsTable } from "@/components/leads/leads-table";
import { PeopleTable } from "@/components/leads/people-table";
import { CompaniesTable } from "@/components/leads/companies-table";
import { CSVUploadDialog } from "@/components/leads/csv-upload-dialog";
import { PeopleCSVDialog } from "@/components/leads/people-csv-dialog";
import { CompaniesCSVDialog } from "@/components/leads/companies-csv-dialog";
import { api } from "@/lib/api";
import {
  Lead,
  ICP,
  Person,
  Company,
  LeadListResponse,
  ICPListResponse,
  PersonListResponse,
  CompanyListResponse,
} from "@/types";

type Tab = "people" | "companies" | "leads";
const ALL_ICPS = "__all__";

export default function LeadsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("people");

  // --- People state ---
  const [people, setPeople] = useState<Person[]>([]);
  const [peopleLoading, setPeopleLoading] = useState(false);
  const [peopleSearch, setPeopleSearch] = useState("");
  const [filterCompanyId, setFilterCompanyId] = useState<number | null>(null);
  const [peopleCSVOpen, setPeopleCSVOpen] = useState(false);

  // --- Companies state ---
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companiesLoading, setCompaniesLoading] = useState(false);
  const [companiesSearch, setCompaniesSearch] = useState("");
  const [companiesCSVOpen, setCompaniesCSVOpen] = useState(false);

  // --- Legacy Leads state ---
  const [leads, setLeads] = useState<Lead[]>([]);
  const [icps, setIcps] = useState<ICP[]>([]);
  const [leadsLoading, setLeadsLoading] = useState(false);
  const [filterIcpId, setFilterIcpId] = useState<string>(ALL_ICPS);
  const [csvDialogOpen, setCsvDialogOpen] = useState(false);

  // Load data on mount
  useEffect(() => {
    loadPeople();
    loadCompanies();
    loadIcps();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    loadLeads();
  }, [filterIcpId]); // eslint-disable-line react-hooks/exhaustive-deps

  // --- People ---
  const loadPeople = useCallback(async (search?: string, companyId?: number | null) => {
    setPeopleLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (companyId != null) params.set("company_id", String(companyId));
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
    loadPeople(value, filterCompanyId);
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

  const handleCompanyClick = (companyId: number) => {
    setFilterCompanyId(companyId);
    setActiveTab("people");
    loadPeople(peopleSearch, companyId);
  };

  const handlePeopleCompanyClick = (companyId: number) => {
    // Switch to companies tab and scroll to that company
    setActiveTab("companies");
  };

  // --- Companies ---
  const loadCompanies = useCallback(async (search?: string) => {
    setCompaniesLoading(true);
    try {
      const qs = search ? `?search=${encodeURIComponent(search)}` : "";
      const data = await api.get<CompanyListResponse>(`/companies${qs}`);
      setCompanies(data.companies);
    } catch (err) {
      console.error("Failed to load companies:", err);
    } finally {
      setCompaniesLoading(false);
    }
  }, []);

  const handleCompaniesSearch = (value: string) => {
    setCompaniesSearch(value);
    loadCompanies(value);
  };

  const handleDeleteCompany = async (id: number) => {
    if (!confirm("Delete this company? People linked to it will be unlinked.")) return;
    try {
      await api.delete(`/companies/${id}`);
      setCompanies((prev) => prev.filter((c) => c.id !== id));
      // Reload people to reflect unlinked company_id
      loadPeople(peopleSearch, filterCompanyId);
    } catch (err) {
      console.error("Failed to delete company:", err);
    }
  };

  const handlePeopleClick = (companyId: number) => {
    setFilterCompanyId(companyId);
    setActiveTab("people");
    loadPeople(peopleSearch, companyId);
  };

  // --- Legacy Leads ---
  const loadIcps = async () => {
    try {
      const data = await api.get<ICPListResponse>("/icps");
      setIcps(data.icps);
    } catch (err) {
      console.error("Failed to load ICPs:", err);
    }
  };

  const loadLeads = async () => {
    setLeadsLoading(true);
    try {
      const endpoint = filterIcpId !== ALL_ICPS ? `/leads?icp_id=${filterIcpId}` : "/leads";
      const data = await api.get<LeadListResponse>(endpoint);
      setLeads(data.leads);
    } catch (err) {
      console.error("Failed to load leads:", err);
    } finally {
      setLeadsLoading(false);
    }
  };

  const handleDeleteLead = async (id: number) => {
    if (!confirm("Delete this lead?")) return;
    try {
      await api.delete(`/leads/${id}`);
      setLeads((prev) => prev.filter((l) => l.id !== id));
    } catch (err) {
      console.error("Failed to delete lead:", err);
    }
  };

  const activeIcps = icps.filter((icp) => icp.status === "active" || icp.status === "draft");

  const tabs: { key: Tab; label: string; count: number }[] = [
    { key: "people", label: "People", count: people.length },
    { key: "companies", label: "Companies", count: companies.length },
    { key: "leads", label: "Leads", count: leads.length },
  ];

  return (
    <div>
      {/* Page Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Leads</h1>
          <p className="text-sm text-muted-foreground">
            {activeTab === "people" && `${people.length} people${filterCompanyId ? " (filtered by company)" : ""}`}
            {activeTab === "companies" && `${companies.length} companies`}
            {activeTab === "leads" && `${leads.length} leads${filterIcpId !== ALL_ICPS ? " (filtered)" : ""}`}
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
                  onClick={() => { setFilterCompanyId(null); loadPeople(peopleSearch, null); }}
                >
                  Clear company filter
                </Button>
              )}
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
          {activeTab === "leads" && (
            <>
              <Select value={filterIcpId} onValueChange={setFilterIcpId}>
                <SelectTrigger className="w-[160px]">
                  <SelectValue placeholder="Filter by ICP" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL_ICPS}>All ICPs</SelectItem>
                  {icps.map((icp) => (
                    <SelectItem key={icp.id} value={String(icp.id)}>{icp.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                onClick={() => setCsvDialogOpen(true)}
                className="gap-1"
                disabled={activeIcps.length === 0}
              >
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
        />
      )}

      {activeTab === "leads" && (
        <>
          {activeIcps.length === 0 && !leadsLoading && (
            <div className="text-center py-8 mb-4 rounded-md border border-dashed">
              <p className="text-muted-foreground">
                Create an ICP first in the AI Chat before importing leads.
              </p>
            </div>
          )}
          <LeadsTable leads={leads} onDelete={handleDeleteLead} loading={leadsLoading} />
        </>
      )}

      {/* Dialogs */}
      <PeopleCSVDialog
        open={peopleCSVOpen}
        onOpenChange={setPeopleCSVOpen}
        onImportComplete={() => loadPeople(peopleSearch, filterCompanyId)}
      />

      <CompaniesCSVDialog
        open={companiesCSVOpen}
        onOpenChange={setCompaniesCSVOpen}
        onImportComplete={() => { loadCompanies(companiesSearch); loadPeople(peopleSearch, filterCompanyId); }}
      />

      <CSVUploadDialog
        open={csvDialogOpen}
        onOpenChange={setCsvDialogOpen}
        icps={activeIcps}
        onImportComplete={loadLeads}
      />
    </div>
  );
}
