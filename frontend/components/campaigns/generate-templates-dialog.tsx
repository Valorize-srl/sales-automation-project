"use client";

import { useState } from "react";
import { Loader2, Wand2, Check, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import {
  Campaign,
  ICP,
  EmailTemplateGenerateResponse,
  PushSequencesResponse,
} from "@/types";

interface GenerateTemplatesDialogProps {
  campaign: Campaign | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  icps: ICP[];
  onGenerated: () => void;
}

const NO_ICP = "__none__";

export function GenerateTemplatesDialog({
  campaign,
  open,
  onOpenChange,
  icps,
  onGenerated,
}: GenerateTemplatesDialogProps) {
  const [icpId, setIcpId] = useState<string>(NO_ICP);
  const [context, setContext] = useState("");
  const [numSubjects, setNumSubjects] = useState(3);
  const [numSteps, setNumSteps] = useState(3);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState<EmailTemplateGenerateResponse | null>(
    null
  );
  const [error, setError] = useState<string | null>(null);
  const [pushingSequences, setPushingSequences] = useState(false);

  const reset = () => {
    setIcpId(
      campaign?.icp_id ? String(campaign.icp_id) : NO_ICP
    );
    setContext("");
    setNumSubjects(3);
    setNumSteps(3);
    setGenerating(false);
    setResult(null);
    setError(null);
  };

  const handleOpenChange = (open: boolean) => {
    if (open) {
      reset();
    }
    onOpenChange(open);
  };

  const handleGenerate = async () => {
    if (!campaign) return;
    setGenerating(true);
    setError(null);
    try {
      const data = await api.post<EmailTemplateGenerateResponse>(
        `/campaigns/${campaign.id}/generate-templates`,
        {
          icp_id: icpId !== NO_ICP ? parseInt(icpId) : null,
          additional_context: context || null,
          num_subject_lines: numSubjects,
          num_steps: numSteps,
        }
      );
      setResult(data);
      onGenerated();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to generate templates"
      );
    } finally {
      setGenerating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Generate Email Templates</DialogTitle>
        </DialogHeader>

        {!result ? (
          <div className="space-y-4 pt-2">
            <div>
              <Label>ICP</Label>
              <Select
                value={icpId}
                onValueChange={setIcpId}
                disabled={generating}
              >
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="Select ICP..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_ICP}>
                    {campaign?.icp_name
                      ? `Campaign ICP (${campaign.icp_name})`
                      : "Select an ICP..."}
                  </SelectItem>
                  {icps.map((icp) => (
                    <SelectItem key={icp.id} value={String(icp.id)}>
                      {icp.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label>Additional Context (optional)</Label>
              <Textarea
                className="mt-1"
                placeholder="e.g. Focus on sustainability benefits, mention our free trial..."
                value={context}
                onChange={(e) => setContext(e.target.value)}
                disabled={generating}
                rows={3}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Subject Line Variations</Label>
                <Input
                  className="mt-1"
                  type="number"
                  min={1}
                  max={10}
                  value={numSubjects}
                  onChange={(e) => setNumSubjects(parseInt(e.target.value) || 3)}
                  disabled={generating}
                />
              </div>
              <div>
                <Label>Email Steps</Label>
                <Input
                  className="mt-1"
                  type="number"
                  min={1}
                  max={5}
                  value={numSteps}
                  onChange={(e) => setNumSteps(parseInt(e.target.value) || 3)}
                  disabled={generating}
                />
              </div>
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}

            <div className="flex justify-end">
              <Button
                onClick={handleGenerate}
                disabled={generating || (icpId === NO_ICP && !campaign?.icp_id)}
                className="gap-1"
              >
                {generating ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Wand2 className="h-4 w-4" />
                )}
                {generating ? "Generating with AI..." : "Generate"}
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4 pt-2">
            <div className="text-center py-2">
              <div className="mx-auto w-10 h-10 rounded-full bg-green-100 flex items-center justify-center mb-2">
                <Check className="h-5 w-5 text-green-600" />
              </div>
              <p className="font-medium">Templates Generated & Saved</p>
            </div>

            <Separator />

            <div>
              <h4 className="font-medium mb-2">Subject Lines</h4>
              <ul className="space-y-1">
                {result.subject_lines.map((s, i) => (
                  <li key={i} className="text-sm bg-muted p-2 rounded">
                    {s}
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h4 className="font-medium mb-2">Email Sequence</h4>
              <div className="space-y-3">
                {result.email_steps.map((step, i) => (
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

            <div className="flex justify-end gap-2">
              {campaign?.instantly_campaign_id && (
                <Button
                  variant="outline"
                  className="gap-1"
                  disabled={pushingSequences}
                  onClick={async () => {
                    if (!campaign) return;
                    setPushingSequences(true);
                    try {
                      const res = await api.post<PushSequencesResponse>(
                        `/campaigns/${campaign.id}/push-sequences`,
                        {}
                      );
                      alert(res.message);
                    } catch (err) {
                      alert(
                        err instanceof Error
                          ? err.message
                          : "Failed to push sequences"
                      );
                    } finally {
                      setPushingSequences(false);
                    }
                  }}
                >
                  {pushingSequences ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                  {pushingSequences ? "Pushing..." : "Push to Instantly"}
                </Button>
              )}
              <Button onClick={() => handleOpenChange(false)}>Done</Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
