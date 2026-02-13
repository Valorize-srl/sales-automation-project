"use client";

import { useState } from "react";
import { RefreshCw, Wand2, Upload, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Campaign, CampaignStatus, EmailStep } from "@/types";

interface CampaignDetailDialogProps {
  campaign: Campaign | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSyncMetrics: (id: number) => void;
  onGenerateTemplates: (campaign: Campaign) => void;
  onUploadLeads: (campaign: Campaign) => void;
  onDelete: (id: number) => void;
}

const statusColors: Record<CampaignStatus, string> = {
  draft: "bg-gray-100 text-gray-800",
  active: "bg-green-100 text-green-800",
  paused: "bg-yellow-100 text-yellow-800",
  completed: "bg-blue-100 text-blue-800",
};

function parseJsonSafe<T>(value: string | null, fallback: T): T {
  if (!value) return fallback;
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

export function CampaignDetailDialog({
  campaign,
  open,
  onOpenChange,
  onSyncMetrics,
  onGenerateTemplates,
  onUploadLeads,
  onDelete,
}: CampaignDetailDialogProps) {
  const [deleting, setDeleting] = useState(false);

  if (!campaign) return null;

  const subjectLines = parseJsonSafe<string[]>(campaign.subject_lines, []);
  const emailSteps = parseJsonSafe<EmailStep[]>(campaign.email_templates, []);

  const openRate =
    campaign.total_sent > 0
      ? ((campaign.total_opened / campaign.total_sent) * 100).toFixed(1)
      : "—";
  const replyRate =
    campaign.total_sent > 0
      ? ((campaign.total_replied / campaign.total_sent) * 100).toFixed(1)
      : "—";

  const handleDelete = async () => {
    if (!confirm(`Delete campaign "${campaign.name}"? This cannot be undone.`))
      return;
    setDeleting(true);
    onDelete(campaign.id);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {campaign.name}
            <Badge
              variant="outline"
              className={statusColors[campaign.status] || ""}
            >
              {campaign.status}
            </Badge>
          </DialogTitle>
        </DialogHeader>

        {/* ICP */}
        <div className="text-sm text-muted-foreground">
          ICP: {campaign.icp_name || "None (imported)"}
        </div>

        <Separator />

        {/* Metrics */}
        <div className="grid grid-cols-5 gap-4 text-center">
          <div>
            <p className="text-2xl font-bold">{campaign.total_sent}</p>
            <p className="text-xs text-muted-foreground">Sent</p>
          </div>
          <div>
            <p className="text-2xl font-bold">{campaign.total_opened}</p>
            <p className="text-xs text-muted-foreground">Opened</p>
          </div>
          <div>
            <p className="text-2xl font-bold">{campaign.total_replied}</p>
            <p className="text-xs text-muted-foreground">Replied</p>
          </div>
          <div>
            <p className="text-2xl font-bold">{openRate}%</p>
            <p className="text-xs text-muted-foreground">Open Rate</p>
          </div>
          <div>
            <p className="text-2xl font-bold">{replyRate}%</p>
            <p className="text-xs text-muted-foreground">Reply Rate</p>
          </div>
        </div>

        <Separator />

        {/* Subject Lines */}
        {subjectLines.length > 0 && (
          <div>
            <h4 className="font-medium mb-2">Subject Lines</h4>
            <ul className="space-y-1">
              {subjectLines.map((s, i) => (
                <li key={i} className="text-sm bg-muted p-2 rounded">
                  {s}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Email Steps */}
        {emailSteps.length > 0 && (
          <div>
            <h4 className="font-medium mb-2">Email Sequence</h4>
            <div className="space-y-3">
              {emailSteps.map((step, i) => (
                <div key={i} className="bg-muted p-3 rounded space-y-1">
                  <div className="flex justify-between items-center">
                    <span className="text-xs font-medium">
                      Step {step.step}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {step.wait_days === 0
                        ? "Immediate"
                        : `Wait ${step.wait_days} days`}
                    </span>
                  </div>
                  <p className="text-sm font-medium">{step.subject}</p>
                  <p className="text-xs text-muted-foreground whitespace-pre-wrap">
                    {step.body}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {subjectLines.length === 0 && emailSteps.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-4">
            No email templates generated yet.
          </p>
        )}

        <Separator />

        {/* Actions */}
        <div className="flex flex-wrap gap-2">
          {campaign.instantly_campaign_id && (
            <Button
              variant="outline"
              size="sm"
              className="gap-1"
              onClick={() => onSyncMetrics(campaign.id)}
            >
              <RefreshCw className="h-3 w-3" />
              Sync Metrics
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            className="gap-1"
            onClick={() => onGenerateTemplates(campaign)}
          >
            <Wand2 className="h-3 w-3" />
            Generate Templates
          </Button>
          {campaign.instantly_campaign_id && (
            <Button
              variant="outline"
              size="sm"
              className="gap-1"
              onClick={() => onUploadLeads(campaign)}
            >
              <Upload className="h-3 w-3" />
              Upload Leads
            </Button>
          )}
          <Button
            variant="destructive"
            size="sm"
            className="gap-1 ml-auto"
            onClick={handleDelete}
            disabled={deleting}
          >
            <Trash2 className="h-3 w-3" />
            Delete
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
