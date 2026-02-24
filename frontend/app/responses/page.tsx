"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { Download, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ResponsesTable } from "@/components/responses/responses-table";
import { ResponseDetailDialog } from "@/components/responses/response-detail-dialog";
import { CampaignMultiSelect } from "@/components/responses/campaign-multi-select";
import { useToast } from "@/hooks/use-toast";
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
  const [fetchProgress, setFetchProgress] = useState<string>("");
  const [fetchResult, setFetchResult] = useState<FetchRepliesResponse | null>(
    null
  );
  const [selectedResponse, setSelectedResponse] =
    useState<EmailResponseWithDetails | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [filterSentiment, setFilterSentiment] = useState<string>("");
  const [filterDateFrom, setFilterDateFrom] = useState<string>("");
  const [filterDateTo, setFilterDateTo] = useState<string>("");
  const { toast } = useToast();

  useEffect(() => {
    loadCampaigns();
  }, []);

  const loadResponses = useCallback(async (
    campaignIds: number[],
    sentiment: string,
    dateFrom: string,
    dateTo: string
  ) => {
    if (campaignIds.length === 0) {
      setResponses([]);
      return;
    }
    setLoading(true);
    try {
      const params = new URLSearchParams({ campaign_ids: campaignIds.join(",") });
      if (sentiment) params.set("sentiment", sentiment);
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);
      const data = await api.get<EmailResponseListResponse>(`/responses?${params}`);
      setResponses(data.responses);
    } catch (err) {
      console.error("Failed to load responses:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadResponses(selectedCampaignIds, filterSentiment, filterDateFrom, filterDateTo);
  }, [selectedCampaignIds, filterSentiment, filterDateFrom, filterDateTo, loadResponses]);

  // Auto-refresh every 5 minutes
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
    if (selectedCampaignIds.length > 0) {
      intervalRef.current = setInterval(() => {
        loadResponses(selectedCampaignIds, filterSentiment, filterDateFrom, filterDateTo);
      }, 5 * 60 * 1000);
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [selectedCampaignIds, filterSentiment, filterDateFrom, filterDateTo, loadResponses]);

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
    setFetchProgress("Fetching replies from Instantly...");

    const campaignCount = selectedCampaignIds.length;
    const campaignNames = campaigns
      .filter(c => selectedCampaignIds.includes(c.id))
      .map(c => c.name)
      .join(", ");

    try {
      const result = await api.post<FetchRepliesResponse>("/responses/fetch", {
        campaign_ids: selectedCampaignIds,
      });

      setFetchResult(result);
      setFetchProgress("");

      toast({
        title: "Replies Fetched Successfully",
        description: `Fetched ${result.fetched} new ${result.fetched === 1 ? 'reply' : 'replies'} from ${campaignCount} ${campaignCount === 1 ? 'campaign' : 'campaigns'}. ${result.skipped > 0 ? `Skipped ${result.skipped} duplicates.` : ''}`,
      });

      await loadResponses(selectedCampaignIds, filterSentiment, filterDateFrom, filterDateTo);
    } catch (err: any) {
      console.error("Fetch failed:", err);
      setFetchProgress("");
      toast({
        title: "Fetch Failed",
        description: err.response?.data?.detail || "Failed to fetch replies from Instantly",
        variant: "destructive",
      });
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
      toast({
        title: "Reply Approved",
        description: "AI-generated reply has been approved and is ready to send",
      });
    } catch (err: any) {
      console.error("Failed to approve:", err);
      toast({
        title: "Approval Failed",
        description: err.response?.data?.detail || "Failed to approve reply",
        variant: "destructive",
      });
    }
  };

  const handleSend = async (id: number) => {
    try {
      await api.post(`/responses/${id}/send`, {});
      toast({
        title: "Reply Sent",
        description: "Your reply has been sent successfully via Instantly",
      });
      loadResponses(selectedCampaignIds, filterSentiment, filterDateFrom, filterDateTo);
      setDetailOpen(false);
    } catch (err: any) {
      console.error("Failed to send:", err);
      toast({
        title: "Send Failed",
        description: err.response?.data?.detail || err.message || "Failed to send reply",
        variant: "destructive",
      });
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
          <h1 className="text-2xl font-bold">Replies</h1>
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

      {fetching && fetchProgress && (
        <div className="mb-4 p-3 rounded-lg bg-blue-50 border border-blue-200 text-sm flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
          <span className="text-blue-900">{fetchProgress}</span>
        </div>
      )}

      {fetchResult && !fetching && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${
          fetchResult.errors > 0
            ? "bg-yellow-50 border border-yellow-200 text-yellow-900"
            : "bg-green-50 border border-green-200 text-green-900"
        }`}>
          <strong>Fetch Complete:</strong> {fetchResult.fetched} new {fetchResult.fetched === 1 ? 'reply' : 'replies'} imported
          {fetchResult.skipped > 0 && `, ${fetchResult.skipped} ${fetchResult.skipped === 1 ? 'duplicate' : 'duplicates'} skipped`}
          {fetchResult.errors > 0 && ` ⚠️ ${fetchResult.errors} ${fetchResult.errors === 1 ? 'error' : 'errors'} occurred`}.
        </div>
      )}

      {/* Filters bar */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        {/* Sentiment filter */}
        <div className="flex items-center gap-1">
          {(["", "interested", "positive", "neutral", "negative"] as const).map(
            (s) => {
              const labels: Record<string, string> = {
                "": "All",
                interested: "Interested",
                positive: "Positive",
                neutral: "Neutral",
                negative: "Negative",
              };
              const colors: Record<string, string> = {
                "": "",
                interested: "bg-green-100 text-green-800 border-green-300",
                positive: "bg-blue-100 text-blue-800 border-blue-300",
                neutral: "bg-gray-100 text-gray-800 border-gray-300",
                negative: "bg-red-100 text-red-800 border-red-300",
              };
              const isActive = filterSentiment === s;
              return (
                <button
                  key={s}
                  onClick={() => setFilterSentiment(s)}
                  className={`px-3 py-1 rounded-full text-xs font-medium border transition-all ${
                    isActive
                      ? s === ""
                        ? "bg-primary text-primary-foreground border-primary"
                        : colors[s] + " ring-2 ring-offset-1 ring-current"
                      : s === ""
                      ? "border-input bg-background hover:bg-accent"
                      : colors[s] + " opacity-60 hover:opacity-100"
                  }`}
                >
                  {labels[s]}
                </button>
              );
            }
          )}
        </div>

        {/* Date range filter */}
        <div className="flex items-center gap-2 ml-2">
          <span className="text-xs text-muted-foreground">From</span>
          <input
            type="date"
            value={filterDateFrom}
            onChange={(e) => setFilterDateFrom(e.target.value)}
            className="text-xs border border-input rounded-md px-2 py-1 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <span className="text-xs text-muted-foreground">To</span>
          <input
            type="date"
            value={filterDateTo}
            onChange={(e) => setFilterDateTo(e.target.value)}
            className="text-xs border border-input rounded-md px-2 py-1 bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          />
          {(filterDateFrom || filterDateTo) && (
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={() => {
                setFilterDateFrom("");
                setFilterDateTo("");
              }}
              title="Clear dates"
            >
              <X className="h-3 w-3" />
            </Button>
          )}
        </div>
      </div>

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
