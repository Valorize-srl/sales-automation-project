"use client";

import { useEffect, useState } from "react";
import { Plus, RefreshCw, Loader2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CampaignTable } from "@/components/campaigns/campaign-table";
import { CreateCampaignDialog } from "@/components/campaigns/create-campaign-dialog";
import { CampaignDetailDialog } from "@/components/campaigns/campaign-detail-dialog";
import { GenerateTemplatesDialog } from "@/components/campaigns/generate-templates-dialog";
import { UploadLeadsDialog } from "@/components/campaigns/upload-leads-dialog";
import { DeleteConfirmDialog } from "@/components/campaigns/delete-confirm-dialog";
import { api } from "@/lib/api";
import {
  Campaign,
  ICP,
  CampaignListResponse,
  ICPListResponse,
  InstantlySyncResponse,
} from "@/types";

const ALL_ICPS = "__all__";

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [icps, setIcps] = useState<ICP[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [filterIcpId, setFilterIcpId] = useState<string>(ALL_ICPS);
  const [selectedCampaignIds, setSelectedCampaignIds] = useState<number[]>([]);

  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [selectedCampaign, setSelectedCampaign] = useState<Campaign | null>(
    null
  );
  const [detailOpen, setDetailOpen] = useState(false);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [uploadLeadsOpen, setUploadLeadsOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  useEffect(() => {
    loadIcps();
    loadCampaigns();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    loadCampaigns();
  }, [filterIcpId]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadIcps = async () => {
    try {
      const data = await api.get<ICPListResponse>("/icps");
      setIcps(data.icps);
    } catch (err) {
      console.error("Failed to load ICPs:", err);
    }
  };

  const loadCampaigns = async () => {
    setLoading(true);
    try {
      const endpoint =
        filterIcpId !== ALL_ICPS
          ? `/campaigns?icp_id=${filterIcpId}`
          : "/campaigns";
      const data = await api.get<CampaignListResponse>(endpoint);
      setCampaigns(data.campaigns);
    } catch (err) {
      console.error("Failed to load campaigns:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const result = await api.post<InstantlySyncResponse>(
        "/campaigns/sync",
        {}
      );
      alert(
        `Sync complete: ${result.imported} imported, ${result.updated} updated, ${result.errors} errors`
      );
      loadCampaigns();
    } catch (err) {
      console.error("Sync failed:", err);
      alert("Sync failed. Check console for details.");
    } finally {
      setSyncing(false);
    }
  };

  const handleSyncMetrics = async (id: number) => {
    try {
      const updated = await api.post<Campaign>(
        `/campaigns/${id}/sync-metrics`,
        {}
      );
      setCampaigns((prev) =>
        prev.map((c) => (c.id === id ? updated : c))
      );
      if (selectedCampaign?.id === id) {
        setSelectedCampaign(updated);
      }
    } catch (err) {
      console.error("Failed to sync metrics:", err);
      alert("Failed to sync metrics. Check console.");
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/campaigns/${id}`);
      setCampaigns((prev) => prev.filter((c) => c.id !== id));
      setDetailOpen(false);
      setSelectedCampaign(null);
    } catch (err) {
      console.error("Failed to delete campaign:", err);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedCampaignIds.length === 0) return;

    try {
      const result = await api.post<{
        deleted: number;
        instantly_deleted: number;
        errors: string[];
        message: string;
      }>("/campaigns/bulk-delete", { campaign_ids: selectedCampaignIds });

      alert(result.message);
      if (result.errors.length > 0) {
        console.error("Delete errors:", result.errors);
      }

      // Reload campaigns and clear selection
      setSelectedCampaignIds([]);
      setDeleteConfirmOpen(false);
      loadCampaigns();
    } catch (err: any) {
      console.error("Failed to bulk delete:", err);
      const errorMessage =
        err.response?.data?.detail ||
        err.message ||
        "Failed to delete campaigns";
      alert(`Error: ${errorMessage}`);
    }
  };

  const handleToggleSelect = (id: number) => {
    setSelectedCampaignIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  const handleToggleSelectAll = () => {
    if (selectedCampaignIds.length === campaigns.length) {
      setSelectedCampaignIds([]);
    } else {
      setSelectedCampaignIds(campaigns.map((c) => c.id));
    }
  };

  const handleViewDetails = (campaign: Campaign) => {
    setSelectedCampaign(campaign);
    setDetailOpen(true);
  };

  const handleGenerateTemplates = (campaign: Campaign) => {
    setSelectedCampaign(campaign);
    setDetailOpen(false);
    setGenerateOpen(true);
  };

  const handleUploadLeads = (campaign: Campaign) => {
    setSelectedCampaign(campaign);
    setDetailOpen(false);
    setUploadLeadsOpen(true);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Campaigns</h1>
          <p className="text-sm text-muted-foreground">
            {campaigns.length} campaign{campaigns.length !== 1 ? "s" : ""}
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
          {selectedCampaignIds.length > 0 && (
            <Button
              variant="destructive"
              onClick={() => setDeleteConfirmOpen(true)}
              className="gap-1"
            >
              <Trash2 className="h-4 w-4" />
              Delete ({selectedCampaignIds.length})
            </Button>
          )}
          <Button
            variant="outline"
            onClick={handleSync}
            disabled={syncing}
            className="gap-1"
          >
            {syncing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {syncing ? "Syncing..." : "Sync from Instantly"}
          </Button>
          <Button
            onClick={() => setCreateDialogOpen(true)}
            className="gap-1"
          >
            <Plus className="h-4 w-4" />
            New Campaign
          </Button>
        </div>
      </div>

      <CampaignTable
        campaigns={campaigns}
        selectedIds={selectedCampaignIds}
        onToggleSelect={handleToggleSelect}
        onToggleSelectAll={handleToggleSelectAll}
        onSyncMetrics={handleSyncMetrics}
        onViewDetails={handleViewDetails}
        loading={loading}
      />

      <CreateCampaignDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        icps={icps}
        onCreated={loadCampaigns}
      />

      <CampaignDetailDialog
        campaign={selectedCampaign}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        onSyncMetrics={handleSyncMetrics}
        onGenerateTemplates={handleGenerateTemplates}
        onUploadLeads={handleUploadLeads}
        onDelete={handleDelete}
      />

      <GenerateTemplatesDialog
        campaign={selectedCampaign}
        open={generateOpen}
        onOpenChange={setGenerateOpen}
        icps={icps}
        onGenerated={loadCampaigns}
      />

      <UploadLeadsDialog
        campaign={selectedCampaign}
        open={uploadLeadsOpen}
        onOpenChange={setUploadLeadsOpen}
      />

      <DeleteConfirmDialog
        open={deleteConfirmOpen}
        onOpenChange={setDeleteConfirmOpen}
        onConfirm={handleBulkDelete}
        count={selectedCampaignIds.length}
      />
    </div>
  );
}
