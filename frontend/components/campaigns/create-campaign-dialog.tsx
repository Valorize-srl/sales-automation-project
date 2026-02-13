"use client";

import { useState } from "react";
import { Loader2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { ICP, Campaign } from "@/types";

interface CreateCampaignDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  icps: ICP[];
  onCreated: () => void;
}

const NO_ICP = "__none__";

export function CreateCampaignDialog({
  open,
  onOpenChange,
  icps,
  onCreated,
}: CreateCampaignDialogProps) {
  const [name, setName] = useState("");
  const [icpId, setIcpId] = useState<string>(NO_ICP);
  const [createOnInstantly, setCreateOnInstantly] = useState(true);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setName("");
    setIcpId(NO_ICP);
    setCreateOnInstantly(true);
    setCreating(false);
    setError(null);
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) reset();
    onOpenChange(open);
  };

  const handleCreate = async () => {
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await api.post<Campaign>("/campaigns", {
        name: name.trim(),
        icp_id: icpId !== NO_ICP ? parseInt(icpId) : null,
        create_on_instantly: createOnInstantly,
      });
      onCreated();
      handleOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create campaign");
    } finally {
      setCreating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[450px]">
        <DialogHeader>
          <DialogTitle>Create Campaign</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 pt-2">
          <div>
            <Label>Campaign Name</Label>
            <Input
              className="mt-1"
              placeholder="e.g. Q1 Outreach - Restaurants"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={creating}
            />
          </div>

          <div>
            <Label>ICP (optional)</Label>
            <Select value={icpId} onValueChange={setIcpId} disabled={creating}>
              <SelectTrigger className="mt-1">
                <SelectValue placeholder="No ICP" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_ICP}>No ICP</SelectItem>
                {icps.map((icp) => (
                  <SelectItem key={icp.id} value={String(icp.id)}>
                    {icp.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="createOnInstantly"
              checked={createOnInstantly}
              onChange={(e) => setCreateOnInstantly(e.target.checked)}
              disabled={creating}
              className="h-4 w-4 rounded border-gray-300"
            />
            <Label htmlFor="createOnInstantly" className="font-normal">
              Also create on Instantly
            </Label>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={creating}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={!name.trim() || creating}
              className="gap-1"
            >
              {creating ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              {creating ? "Creating..." : "Create"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
