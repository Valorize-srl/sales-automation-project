"use client";

import { useState, useEffect } from "react";
import { Send, CheckCircle2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { Campaign } from "@/types";

interface AddListToCampaignDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  leadListId: number | null;
}

export function AddListToCampaignDialog({
  open,
  onOpenChange,
  leadListId,
}: AddListToCampaignDialogProps) {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedCampaignId, setSelectedCampaignId] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [loadingCampaigns, setLoadingCampaigns] = useState(false);
  const [result, setResult] = useState<{
    success: boolean;
    message: string;
    pushed?: number;
    errors?: number;
  } | null>(null);

  // Load campaigns when dialog opens
  useEffect(() => {
    if (open) {
      loadCampaigns();
      setResult(null);
      setSelectedCampaignId("");
    }
  }, [open]);

  const loadCampaigns = async () => {
    setLoadingCampaigns(true);
    try {
      const data = await api.getCampaigns();
      // Only show campaigns linked to Instantly
      const linkedCampaigns = data.campaigns.filter(
        (c) => c.instantly_campaign_id
      );
      setCampaigns(linkedCampaigns);
    } catch (err) {
      console.error("Failed to load campaigns:", err);
    } finally {
      setLoadingCampaigns(false);
    }
  };

  const handleAddToCampaign = async () => {
    if (!selectedCampaignId || !leadListId) return;

    setLoading(true);
    setResult(null);

    try {
      const res = await api.addListToCampaign(
        parseInt(selectedCampaignId),
        leadListId
      );
      setResult({
        success: true,
        message: res.message,
        pushed: res.pushed_to_instantly,
        errors: res.errors,
      });
    } catch (err) {
      setResult({
        success: false,
        message: err instanceof Error ? err.message : "Failed to add list to campaign",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Send className="h-5 w-5" />
            Add List to Campaign
          </DialogTitle>
          <DialogDescription>
            Associate this lead list with a campaign and push leads to Instantly.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {!result ? (
            <>
              <div>
                <label className="text-sm font-medium mb-1 block">
                  Select Campaign
                </label>
                {loadingCampaigns ? (
                  <p className="text-sm text-muted-foreground">Loading campaigns...</p>
                ) : campaigns.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No campaigns linked to Instantly found. Create a campaign first.
                  </p>
                ) : (
                  <Select
                    value={selectedCampaignId}
                    onValueChange={setSelectedCampaignId}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Choose a campaign..." />
                    </SelectTrigger>
                    <SelectContent>
                      {campaigns.map((c) => (
                        <SelectItem key={c.id} value={String(c.id)}>
                          {c.name}
                          <span className="text-xs text-muted-foreground ml-2">
                            ({c.status})
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>

              <div className="rounded-md bg-muted/50 p-3 text-sm text-muted-foreground">
                Leads will be pushed to the selected Instantly campaign immediately.
              </div>
            </>
          ) : (
            <div
              className={`rounded-md p-4 ${
                result.success
                  ? "bg-green-50 border border-green-200"
                  : "bg-red-50 border border-red-200"
              }`}
            >
              <div className="flex items-start gap-2">
                {result.success ? (
                  <CheckCircle2 className="h-5 w-5 text-green-600 mt-0.5" />
                ) : (
                  <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
                )}
                <div>
                  <p
                    className={`text-sm font-medium ${
                      result.success ? "text-green-800" : "text-red-800"
                    }`}
                  >
                    {result.success ? "Success" : "Error"}
                  </p>
                  <p
                    className={`text-sm mt-1 ${
                      result.success ? "text-green-700" : "text-red-700"
                    }`}
                  >
                    {result.message}
                  </p>
                  {result.success && result.pushed !== undefined && (
                    <p className="text-xs text-green-600 mt-1">
                      {result.pushed} leads pushed to Instantly
                      {result.errors ? `, ${result.errors} errors` : ""}
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          {result ? (
            <Button onClick={() => onOpenChange(false)}>Done</Button>
          ) : (
            <>
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={loading}
              >
                Skip
              </Button>
              <Button
                onClick={handleAddToCampaign}
                disabled={loading || !selectedCampaignId || campaigns.length === 0}
                className="gap-1.5"
              >
                <Send className="h-3.5 w-3.5" />
                {loading ? "Pushing..." : "Add & Push to Instantly"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
