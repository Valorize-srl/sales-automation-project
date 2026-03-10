"use client";

import { useState, useEffect } from "react";
import { RefreshCw, Upload, Trash2, Send, Loader2, Download, Save, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { Campaign, CampaignStatus, EmailStep } from "@/types";

interface CampaignDetailDialogProps {
  campaign: Campaign | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSyncMetrics: (id: number) => void;
  onUploadLeads: (campaign: Campaign) => void;
  onDelete: (id: number) => void;
  onUpdated?: () => void;
}

const statusColors: Record<CampaignStatus, string> = {
  draft: "bg-gray-100 text-gray-800",
  active: "bg-green-100 text-green-800",
  paused: "bg-yellow-100 text-yellow-800",
  completed: "bg-blue-100 text-blue-800",
  scheduled: "bg-purple-100 text-purple-800",
  error: "bg-red-100 text-red-800",
};

function parseJsonSafe<T>(value: string | null, fallback: T): T {
  if (!value) return fallback;
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

interface EditableStep {
  step: number;
  subject: string;
  body: string;
  wait_days: number;
}

export function CampaignDetailDialog({
  campaign,
  open,
  onOpenChange,
  onSyncMetrics,
  onUploadLeads,
  onDelete,
  onUpdated,
}: CampaignDetailDialogProps) {
  const [deleting, setDeleting] = useState(false);
  const [pushingSequences, setPushingSequences] = useState(false);
  const [syncingLeads, setSyncingLeads] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editableSteps, setEditableSteps] = useState<EditableStep[]>([]);
  const [dirty, setDirty] = useState(false);
  const { toast } = useToast();

  // Sync editable steps when campaign changes or dialog opens
  useEffect(() => {
    if (campaign && open) {
      const steps = parseJsonSafe<EmailStep[]>(campaign.email_templates, []);
      setEditableSteps(
        steps.length > 0
          ? steps.map((s) => ({
              step: s.step,
              subject: s.subject || "",
              body: s.body || "",
              wait_days: s.wait_days ?? 0,
            }))
          : [{ step: 1, subject: "", body: "", wait_days: 0 }]
      );
      setDirty(false);
    }
  }, [campaign, open]);

  if (!campaign) return null;

  const subjectLines = parseJsonSafe<string[]>(campaign.subject_lines, []);

  const openRate =
    campaign.total_sent > 0
      ? ((campaign.total_opened / campaign.total_sent) * 100).toFixed(1)
      : "—";
  const replyRate =
    campaign.total_sent > 0
      ? ((campaign.total_replied / campaign.total_sent) * 100).toFixed(1)
      : "—";

  const updateStep = (index: number, field: keyof EditableStep, value: string | number) => {
    setEditableSteps((prev) =>
      prev.map((s, i) => (i === index ? { ...s, [field]: value } : s))
    );
    setDirty(true);
  };

  const addStep = () => {
    if (editableSteps.length >= 3) return;
    setEditableSteps((prev) => [
      ...prev,
      { step: prev.length + 1, subject: "", body: "", wait_days: 3 },
    ]);
    setDirty(true);
  };

  const removeStep = (index: number) => {
    setEditableSteps((prev) =>
      prev.filter((_, i) => i !== index).map((s, i) => ({ ...s, step: i + 1 }))
    );
    setDirty(true);
  };

  const handleSaveSequences = async () => {
    setSaving(true);
    try {
      const filledSteps = editableSteps
        .filter((s) => s.subject.trim() || s.body.trim())
        .map((s, i) => ({
          step: i + 1,
          subject: s.subject.trim(),
          body: s.body.trim(),
          wait_days: i === 0 ? 0 : s.wait_days,
        }));

      await api.put(`/campaigns/${campaign.id}`, {
        email_templates: JSON.stringify(filledSteps),
      });
      setDirty(false);
      onUpdated?.();
      toast({
        title: "Sequences Saved",
        description: `${filledSteps.length} email step${filledSteps.length !== 1 ? "s" : ""} saved`,
      });
    } catch (err) {
      toast({
        title: "Save Failed",
        description: err instanceof Error ? err.message : "Failed to save sequences",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAndPush = async () => {
    await handleSaveSequences();
    if (!dirty) {
      handlePushSequences();
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Delete campaign "${campaign.name}"? This cannot be undone.`))
      return;
    setDeleting(true);
    onDelete(campaign.id);
  };

  const handlePushSequences = async () => {
    setPushingSequences(true);
    try {
      const result = await api.pushSequences(campaign.id);
      toast({
        title: "Sequences Pushed",
        description: result.message,
      });
    } catch (err) {
      toast({
        title: "Push Failed",
        description: err instanceof Error ? err.message : "Failed to push sequences to Instantly",
        variant: "destructive",
      });
    } finally {
      setPushingSequences(false);
    }
  };

  const handleSyncLeads = async () => {
    setSyncingLeads(true);
    try {
      const result = await api.syncLeadsFromInstantly(campaign.id);
      toast({
        title: "Leads Synced",
        description: result.message,
      });
    } catch (err) {
      toast({
        title: "Sync Failed",
        description: err instanceof Error ? err.message : "Failed to sync leads from Instantly",
        variant: "destructive",
      });
    } finally {
      setSyncingLeads(false);
    }
  };

  const hasFilledSteps = editableSteps.some((s) => s.subject.trim() || s.body.trim());

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[650px] max-h-[85vh] overflow-y-auto">
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
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 sm:gap-4 text-center">
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

        {/* Subject Lines (read-only, from old data) */}
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

        {/* Editable Email Sequence */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="font-medium">Email Sequence</h4>
            {editableSteps.length < 3 && (
              <button
                type="button"
                onClick={addStep}
                className="text-xs text-primary hover:underline flex items-center gap-1"
              >
                <Plus className="h-3 w-3" />
                Add Step
              </button>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            Use {"{{firstName}}"}, {"{{lastName}}"}, {"{{companyName}}"} for personalization.
          </p>

          {editableSteps.map((step, index) => (
            <div key={index} className="border rounded-md p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium">
                  Step {index + 1}{index === 0 ? " (sent immediately)" : ""}
                </span>
                {index > 0 && (
                  <div className="flex items-center gap-2">
                    <Label className="text-xs">Wait</Label>
                    <Input
                      className="w-16 h-7 text-xs"
                      type="number"
                      min={1}
                      max={30}
                      value={step.wait_days}
                      onChange={(e) =>
                        updateStep(index, "wait_days", parseInt(e.target.value) || 1)
                      }
                    />
                    <span className="text-xs text-muted-foreground">days</span>
                    <button
                      type="button"
                      onClick={() => removeStep(index)}
                      className="text-muted-foreground hover:text-destructive ml-1"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}
              </div>
              <div>
                <Label className="text-xs">Subject</Label>
                <Input
                  className="mt-1 text-sm"
                  placeholder="e.g. Quick question, {{firstName}}"
                  value={step.subject}
                  onChange={(e) => updateStep(index, "subject", e.target.value)}
                />
              </div>
              <div>
                <Label className="text-xs">Body</Label>
                <Textarea
                  className="mt-1 text-sm"
                  placeholder="Write your email body here..."
                  rows={4}
                  value={step.body}
                  onChange={(e) => updateStep(index, "body", e.target.value)}
                />
              </div>
            </div>
          ))}

          {/* Save & Push buttons for sequences */}
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              className="gap-1"
              onClick={handleSaveSequences}
              disabled={saving || !dirty}
            >
              {saving ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Save className="h-3 w-3" />
              )}
              {saving ? "Saving..." : "Save"}
            </Button>
            {campaign.instantly_campaign_id && hasFilledSteps && (
              <Button
                variant="outline"
                size="sm"
                className="gap-1"
                onClick={dirty ? handleSaveAndPush : handlePushSequences}
                disabled={pushingSequences || saving}
              >
                {pushingSequences ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Send className="h-3 w-3" />
                )}
                {pushingSequences ? "Pushing..." : dirty ? "Save & Push to Instantly" : "Push to Instantly"}
              </Button>
            )}
          </div>
        </div>

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
          {campaign.instantly_campaign_id && (
            <Button
              variant="outline"
              size="sm"
              className="gap-1"
              onClick={handleSyncLeads}
              disabled={syncingLeads}
            >
              {syncingLeads ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Download className="h-3 w-3" />
              )}
              {syncingLeads ? "Syncing..." : "Sync Leads"}
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
