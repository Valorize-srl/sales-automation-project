"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { Download, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ResponsesTable } from "@/components/responses/responses-table";
import { ResponseDetailDialog } from "@/components/responses/response-detail-dialog";
import { CampaignMultiSelect } from "@/components/responses/campaign-multi-select";
import { api } from "@/lib/api";
import {
  Campaign,
  CampaignListResponse,
  EmailResponseWithDetails,
  EmailResponseListResponse,
  FetchRepliesResponse,
} from "@/types";

export default function ResponsesPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedCampaignIds, setSelectedCampaignIds] = useState<number[]>([]);
  const [responses, setResponses] = useState<EmailResponseWithDetails[]>([]);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(false);
  const [fetchResult, setFetchResult] = useState<FetchRepliesResponse | null>(
    null
  );
  const [selectedResponse, setSelectedResponse] =
    useState<EmailResponseWithDetails | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  useEffect(() => {
    loadCampaigns();
  }, []);

  const loadResponses = useCallback(async (campaignIds: number[]) => {
    if (campaignIds.length === 0) {
      setResponses([]);
      return;
    }
    setLoading(true);
    try {
      const idsParam = campaignIds.join(",");
      const data = await api.get<EmailResponseListResponse>(
        `/responses?campaign_ids=${idsParam}`
      );
      setResponses(data.responses);
    } catch (err) {
      console.error("Failed to load responses:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadResponses(selectedCampaignIds);
  }, [selectedCampaignIds, loadResponses]);

  // Auto-refresh every 5 minutes
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
    if (selectedCampaignIds.length > 0) {
      intervalRef.current = setInterval(() => {
        loadResponses(selectedCampaignIds);
      }, 5 * 60 * 1000);
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [selectedCampaignIds, loadResponses]);

  const loadCampaigns = async () => {
    try {
      const data = await api.get<CampaignListResponse>("/campaigns");
      setCampaigns(data.campaigns);
    } catch (err) {
      console.error("Failed to load campaigns:", err);
    }
  };

  const handleFetchReplies = async () => {
    setFetching(true);
    setFetchResult(null);
    try {
      const result = await api.post<FetchRepliesResponse>("/responses/fetch", {
        campaign_ids: selectedCampaignIds,
      });
      setFetchResult(result);
      await loadResponses(selectedCampaignIds);
    } catch (err) {
      console.error("Fetch failed:", err);
      alert("Failed to fetch replies. Check console.");
    } finally {
      setFetching(false);
    }
  };

  const handleApprove = async (id: number, editedReply?: string) => {
    try {
      const updated = await api.post<EmailResponseWithDetails>(
        `/responses/${id}/approve`,
        editedReply ? { edited_reply: editedReply } : {}
      );
      setResponses((prev) => prev.map((r) => (r.id === id ? updated : r)));
      if (selectedResponse?.id === id) {
        setSelectedResponse(updated);
      }
    } catch (err) {
      console.error("Failed to approve:", err);
      alert("Failed to approve reply.");
    }
  };

  const handleSend = async (id: number) => {
    try {
      await api.post(`/responses/${id}/send`, {});
      loadResponses(selectedCampaignIds);
      setDetailOpen(false);
      alert("Reply sent successfully!");
    } catch (err: any) {
      console.error("Failed to send:", err);
      const errorMessage = err.response?.data?.detail || err.message || "Unknown error occurred";
      alert(`Failed to send reply: ${errorMessage}`);
    }
  };

  const handleIgnore = async (id: number) => {
    try {
      const updated = await api.post<EmailResponseWithDetails>(
        `/responses/${id}/ignore`,
        {}
      );
      setResponses((prev) => prev.map((r) => (r.id === id ? updated : r)));
      if (selectedResponse?.id === id) {
        setSelectedResponse(updated);
      }
    } catch (err) {
      console.error("Failed to ignore:", err);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/responses/${id}`);
      setResponses((prev) => prev.filter((r) => r.id !== id));
      if (selectedResponse?.id === id) {
        setDetailOpen(false);
        setSelectedResponse(null);
      }
    } catch (err) {
      console.error("Failed to delete:", err);
      alert("Failed to delete response.");
    }
  };

  const handleViewDetail = (response: EmailResponseWithDetails) => {
    setSelectedResponse(response);
    setDetailOpen(true);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Responses</h1>
          <p className="text-sm text-muted-foreground">
            {responses.length} response{responses.length !== 1 ? "s" : ""}
            {selectedCampaignIds.length > 0 &&
              ` from ${selectedCampaignIds.length} campaign${selectedCampaignIds.length > 1 ? "s" : ""}`}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <CampaignMultiSelect
            campaigns={campaigns}
            selectedIds={selectedCampaignIds}
            onSelectionChange={setSelectedCampaignIds}
          />
          <Button
            onClick={handleFetchReplies}
            disabled={fetching || selectedCampaignIds.length === 0}
            variant="outline"
            className="gap-1"
          >
            {fetching ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            {fetching ? "Fetching..." : "Fetch Replies"}
          </Button>
        </div>
      </div>

      {fetchResult && (
        <div className="mb-4 p-3 rounded-lg bg-muted text-sm">
          Fetched {fetchResult.fetched} new replies, skipped{" "}
          {fetchResult.skipped} duplicates
          {fetchResult.errors > 0 && `, ${fetchResult.errors} errors`}.
        </div>
      )}

      <ResponsesTable
        responses={responses}
        loading={loading}
        onViewDetail={handleViewDetail}
        onApprove={(id) => handleApprove(id)}
        onSend={handleSend}
        onIgnore={handleIgnore}
        onDelete={handleDelete}
      />

      <ResponseDetailDialog
        response={selectedResponse}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        onApprove={handleApprove}
        onSend={handleSend}
        onIgnore={handleIgnore}
        onDelete={handleDelete}
        onResponseUpdated={(updated) => {
          setResponses((prev) =>
            prev.map((r) => (r.id === updated.id ? updated : r))
          );
          setSelectedResponse(updated);
        }}
      />
    </div>
  );
}
