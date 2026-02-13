"use client";

import { useEffect, useState } from "react";
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

  useEffect(() => {
    if (selectedCampaignIds.length > 0) {
      loadResponses();
    } else {
      setResponses([]);
    }
  }, [selectedCampaignIds]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadCampaigns = async () => {
    try {
      const data = await api.get<CampaignListResponse>("/campaigns");
      setCampaigns(data.campaigns);
    } catch (err) {
      console.error("Failed to load campaigns:", err);
    }
  };

  const loadResponses = async () => {
    setLoading(true);
    try {
      const allResponses: EmailResponseWithDetails[] = [];
      for (const campaignId of selectedCampaignIds) {
        const data = await api.get<EmailResponseListResponse>(
          `/responses?campaign_id=${campaignId}`
        );
        allResponses.push(...data.responses);
      }
      // Sort by date descending
      allResponses.sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setResponses(allResponses);
    } catch (err) {
      console.error("Failed to load responses:", err);
    } finally {
      setLoading(false);
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
      loadResponses();
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
      // Reload to get updated status
      loadResponses();
      setDetailOpen(false);
    } catch (err) {
      console.error("Failed to send:", err);
      alert("Failed to send reply. Check console.");
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
          Fetched {fetchResult.fetched} new replies, analyzed{" "}
          {fetchResult.analyzed}, skipped {fetchResult.skipped} duplicates
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
      />

      <ResponseDetailDialog
        response={selectedResponse}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        onApprove={handleApprove}
        onSend={handleSend}
        onIgnore={handleIgnore}
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
