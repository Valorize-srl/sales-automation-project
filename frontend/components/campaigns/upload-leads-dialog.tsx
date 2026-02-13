"use client";

import { useEffect, useState } from "react";
import { Loader2, Upload, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { Campaign, Lead, LeadListResponse, LeadUploadResponse } from "@/types";

interface UploadLeadsDialogProps {
  campaign: Campaign | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function UploadLeadsDialog({
  campaign,
  open,
  onOpenChange,
}: UploadLeadsDialogProps) {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [loadingLeads, setLoadingLeads] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [result, setResult] = useState<LeadUploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open && campaign) {
      loadLeads();
      setSelectedIds(new Set());
      setResult(null);
      setError(null);
    }
  }, [open, campaign]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadLeads = async () => {
    if (!campaign) return;
    setLoadingLeads(true);
    try {
      const endpoint = campaign.icp_id
        ? `/leads?icp_id=${campaign.icp_id}`
        : "/leads";
      const data = await api.get<LeadListResponse>(endpoint);
      setLeads(data.leads);
    } catch (err) {
      console.error("Failed to load leads:", err);
    } finally {
      setLoadingLeads(false);
    }
  };

  const toggleLead = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedIds.size === leads.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(leads.map((l) => l.id)));
    }
  };

  const handlePush = async () => {
    if (!campaign || selectedIds.size === 0) return;
    setPushing(true);
    setError(null);
    try {
      const data = await api.post<LeadUploadResponse>(
        `/campaigns/${campaign.id}/upload-leads`,
        { lead_ids: Array.from(selectedIds) }
      );
      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to upload leads"
      );
    } finally {
      setPushing(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Upload Leads to Instantly</DialogTitle>
        </DialogHeader>

        {result ? (
          <div className="space-y-4 pt-2 text-center">
            <div className="py-4">
              <div className="mx-auto w-12 h-12 rounded-full bg-green-100 flex items-center justify-center mb-3">
                <Check className="h-6 w-6 text-green-600" />
              </div>
              <p className="text-lg font-medium">Upload Complete</p>
            </div>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-2xl font-bold text-green-600">
                  {result.pushed}
                </p>
                <p className="text-muted-foreground">Pushed</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-red-600">
                  {result.errors}
                </p>
                <p className="text-muted-foreground">Errors</p>
              </div>
            </div>
            <Button onClick={() => onOpenChange(false)} className="mt-4">
              Done
            </Button>
          </div>
        ) : (
          <div className="space-y-4 pt-2">
            {campaign?.icp_id && (
              <p className="text-sm text-muted-foreground">
                Showing leads for ICP: {campaign.icp_name || "linked ICP"}
              </p>
            )}

            {loadingLeads ? (
              <p className="text-center text-muted-foreground py-4">
                Loading leads...
              </p>
            ) : leads.length === 0 ? (
              <p className="text-center text-muted-foreground py-4">
                No leads found. Import leads first.
              </p>
            ) : (
              <>
                <div className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selectedIds.size === leads.length}
                    onChange={toggleAll}
                    className="h-4 w-4 rounded border-gray-300"
                  />
                  <span>
                    Select all ({leads.length} lead
                    {leads.length !== 1 ? "s" : ""})
                  </span>
                </div>

                <Separator />

                <div className="max-h-[300px] overflow-y-auto space-y-1">
                  {leads.map((lead) => (
                    <label
                      key={lead.id}
                      className="flex items-center gap-2 p-2 rounded hover:bg-muted cursor-pointer text-sm"
                    >
                      <input
                        type="checkbox"
                        checked={selectedIds.has(lead.id)}
                        onChange={() => toggleLead(lead.id)}
                        className="h-4 w-4 rounded border-gray-300"
                      />
                      <span className="font-medium">
                        {lead.first_name} {lead.last_name}
                      </span>
                      <span className="text-muted-foreground truncate">
                        {lead.email}
                      </span>
                    </label>
                  ))}
                </div>
              </>
            )}

            {error && <p className="text-sm text-destructive">{error}</p>}

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                onClick={handlePush}
                disabled={selectedIds.size === 0 || pushing}
                className="gap-1"
              >
                {pushing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Upload className="h-4 w-4" />
                )}
                {pushing
                  ? "Pushing..."
                  : `Push ${selectedIds.size} Lead${selectedIds.size !== 1 ? "s" : ""}`}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
