"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { Plus, RefreshCw, Loader2, Trash2, Search, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { useToast } from "@/hooks/use-toast";
import {
  Campaign,
  ICP,
  ICPListResponse,
} from "@/types";

const ALL_ICPS = "__all__";

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [icps, setIcps] = useState<ICP[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [filterIcpId, setFilterIcpId] = useState<string>(ALL_ICPS);
  const [filterStatus, setFilterStatus] = useState<string>("__all__");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCampaignIds, setSelectedCampaignIds] = useState<number[]>([]);
  const { toast } = useToast();

  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const POLL_INTERVAL = 5 * 60 * 1000; // 5 minutes

  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [selectedCampaign, setSelectedCampaign] = useState<Campaign | null>(
    null
  );
  const [detailOpen, setDetailOpen] = useState(false);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [uploadLeadsOpen, setUploadLeadsOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);

  const loadIcps = useCallback(async () => {
    try {
      const data = await api.get<ICPListResponse>("/icps");
      setIcps(data.icps);
    } catch (err) {
      console.error("Failed to load ICPs:", err);
    }
  }, []);

  const loadCampaigns = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const params: Record<string, string | number> = {};
      if (filterIcpId !== ALL_ICPS) {
        params.icp_id = parseInt(filterIcpId);
      }
      if (filterStatus !== "__all__") {
        params.status = filterStatus;
      }
      if (searchQuery) {
        params.search = searchQuery;
      }
      const data = await api.getCampaigns(params);
      setCampaigns(data.campaigns);
      setLastRefresh(new Date());
    } catch (err) {
      console.error("Failed to load campaigns:", err);
    } finally {
      if (!silent) setLoading(false);
    }
  }, [filterIcpId, filterStatus, searchQuery]);

  // Initial load
  useEffect(() => {
    loadIcps();
    loadCampaigns();
  }, [loadIcps, loadCampaigns]);

  // Auto-polling every 5 minutes: sync metrics from Instantly + reload campaigns
  useEffect(() => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    pollingRef.current = setInterval(async () => {
      try {
        // First sync metrics from Instantly for all active campaigns
        await api.syncAllCampaignMetrics();
      } catch (err) {
        console.error("Auto-sync metrics failed:", err);
      }
      // Then reload campaign list with fresh data
      loadCampaigns(true);
    }, POLL_INTERVAL);
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [loadCampaigns]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const result = await api.syncCampaigns();
      toast({
        title: "Sync Complete",
        description: `${result.imported} imported, ${result.updated} updated, ${result.errors} errors`,
      });
      loadCampaigns();
    } catch (err) {
      toast({
        title: "Sync Failed",
        description: err instanceof Error ? err.message : "Failed to sync with Instantly",
        variant: "destructive",
      });
    } finally {
      setSyncing(false);
    }
  };

  const handleSyncMetrics = async (id: number) => {
    try {
      const updated = await api.syncCampaignMetrics(id);
      setCampaigns((prev) =>
        prev.map((c) => (c.id === id ? updated : c))
      );
      if (selectedCampaign?.id === id) {
        setSelectedCampaign(updated);
      }
      toast({
        title: "Metrics Updated",
        description: "Campaign metrics synced from Instantly",
      });
    } catch (err) {
      toast({
        title: "Sync Failed",
        description: err instanceof Error ? err.message : "Failed to sync metrics",
        variant: "destructive",
      });
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.deleteCampaign(id);
      setCampaigns((prev) => prev.filter((c) => c.id !== id));
      setDetailOpen(false);
      setSelectedCampaign(null);
      toast({
        title: "Campaign Deleted",
        description: "Campaign has been removed",
      });
    } catch (err) {
      toast({
        title: "Delete Failed",
        description: err instanceof Error ? err.message : "Failed to delete campaign",
        variant: "destructive",
      });
    }
  };

  const handleBulkDelete = async () => {
    if (selectedCampaignIds.length === 0) return;

    try {
      const result = await api.bulkDeleteCampaigns(selectedCampaignIds);
      toast({
        title: "Campaigns Deleted",
        description: result.message,
      });
      setSelectedCampaignIds([]);
      setDeleteConfirmOpen(false);
      loadCampaigns();
    } catch (err) {
      toast({
        title: "Delete Failed",
        description: err instanceof Error ? err.message : "Failed to delete campaigns",
        variant: "destructive",
      });
    }
  };

  const handleActivate = async (id: number) => {
    try {
      const updated = await api.activateCampaign(id);
      setCampaigns((prev) => prev.map((c) => (c.id === id ? updated : c)));
      if (selectedCampaign?.id === id) {
        setSelectedCampaign(updated);
      }
      toast({
        title: "Campaign Activated",
        description: `Campaign "${updated.name}" is now active on Instantly`,
      });
    } catch (err) {
      toast({
        title: "Activation Failed",
        description: err instanceof Error ? err.message : "Failed to activate campaign",
        variant: "destructive",
      });
    }
  };

  const handlePause = async (id: number) => {
    try {
      const updated = await api.pauseCampaign(id);
      setCampaigns((prev) => prev.map((c) => (c.id === id ? updated : c)));
      if (selectedCampaign?.id === id) {
        setSelectedCampaign(updated);
      }
      toast({
        title: "Campaign Paused",
        description: `Campaign "${updated.name}" has been paused`,
      });
    } catch (err) {
      toast({
        title: "Pause Failed",
        description: err instanceof Error ? err.message : "Failed to pause campaign",
        variant: "destructive",
      });
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
            {(filterIcpId !== ALL_ICPS || filterStatus !== "__all__") && " (filtered)"}
            {searchQuery && " (search results)"}
            {lastRefresh && (
              <span className="ml-2 inline-flex items-center gap-1">
                <Clock className="h-3 w-3" />
                Updated {lastRefresh.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })}
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative w-[200px]">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search campaigns..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8"
            />
          </div>
          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All Statuses</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="paused">Paused</SelectItem>
              <SelectItem value="draft">Draft</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="scheduled">Scheduled</SelectItem>
              <SelectItem value="error">Error</SelectItem>
            </SelectContent>
          </Select>
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
        onActivate={handleActivate}
        onPause={handlePause}
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
