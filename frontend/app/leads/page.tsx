"use client";

import { useEffect, useState } from "react";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { LeadsTable } from "@/components/leads/leads-table";
import { CSVUploadDialog } from "@/components/leads/csv-upload-dialog";
import { api } from "@/lib/api";
import { Lead, ICP, LeadListResponse, ICPListResponse } from "@/types";

const ALL_ICPS = "__all__";

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [icps, setIcps] = useState<ICP[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterIcpId, setFilterIcpId] = useState<string>(ALL_ICPS);
  const [csvDialogOpen, setCsvDialogOpen] = useState(false);

  useEffect(() => {
    loadIcps();
    loadLeads();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    loadLeads();
  }, [filterIcpId]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadIcps = async () => {
    try {
      const data = await api.get<ICPListResponse>("/icps");
      setIcps(data.icps);
    } catch (err) {
      console.error("Failed to load ICPs:", err);
    }
  };

  const loadLeads = async () => {
    setLoading(true);
    try {
      const endpoint =
        filterIcpId !== ALL_ICPS
          ? `/leads?icp_id=${filterIcpId}`
          : "/leads";
      const data = await api.get<LeadListResponse>(endpoint);
      setLeads(data.leads);
    } catch (err) {
      console.error("Failed to load leads:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this lead?")) return;
    try {
      await api.delete(`/leads/${id}`);
      setLeads((prev) => prev.filter((lead) => lead.id !== id));
    } catch (err) {
      console.error("Failed to delete lead:", err);
    }
  };

  const activeIcps = icps.filter((icp) => icp.status === "active" || icp.status === "draft");

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Leads</h1>
          <p className="text-sm text-muted-foreground">
            {leads.length} lead{leads.length !== 1 ? "s" : ""}
            {filterIcpId !== ALL_ICPS && " (filtered)"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={filterIcpId} onValueChange={setFilterIcpId}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Filter by ICP" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_ICPS}>All ICPs</SelectItem>
              {icps.map((icp) => (
                <SelectItem key={icp.id} value={String(icp.id)}>
                  {icp.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            onClick={() => setCsvDialogOpen(true)}
            className="gap-1"
            disabled={activeIcps.length === 0}
          >
            <Upload className="h-4 w-4" />
            Import CSV
          </Button>
        </div>
      </div>

      {activeIcps.length === 0 && !loading && (
        <div className="text-center py-8 mb-4 rounded-md border border-dashed">
          <p className="text-muted-foreground">
            Create an ICP first in the AI Chat before importing leads.
          </p>
        </div>
      )}

      <LeadsTable leads={leads} onDelete={handleDelete} loading={loading} />

      <CSVUploadDialog
        open={csvDialogOpen}
        onOpenChange={setCsvDialogOpen}
        icps={activeIcps}
        onImportComplete={loadLeads}
      />
    </div>
  );
}
