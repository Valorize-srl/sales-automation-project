"use client";

import { useState } from "react";
import { ListPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";

interface CreateListDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedPersonIds: number[];
  defaultClientTag?: string;
  onListCreated: (listId: number) => void;
}

export function CreateListDialog({
  open,
  onOpenChange,
  selectedPersonIds,
  defaultClientTag,
  onListCreated,
}: CreateListDialogProps) {
  const [listName, setListName] = useState("");
  const [clientTag, setClientTag] = useState(defaultClientTag || "");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!listName.trim()) {
      setError("List name is required");
      return;
    }

    setCreating(true);
    setError(null);

    try {
      const result = await api.createLeadList({
        name: listName.trim(),
        client_tag: clientTag.trim() || undefined,
        person_ids: selectedPersonIds,
      });
      onListCreated(result.id);
      // Reset form
      setListName("");
      setClientTag(defaultClientTag || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create list");
    } finally {
      setCreating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ListPlus className="h-5 w-5" />
            Create Lead List
          </DialogTitle>
          <DialogDescription>
            Create a new list with {selectedPersonIds.length} selected{" "}
            {selectedPersonIds.length === 1 ? "person" : "people"}.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div>
            <Label htmlFor="list-name" className="text-sm">
              List Name <span className="text-red-500">*</span>
            </Label>
            <Input
              id="list-name"
              placeholder="e.g. SEO Managers - Italy"
              value={listName}
              onChange={(e) => {
                setListName(e.target.value);
                setError(null);
              }}
              className="mt-1"
            />
          </div>

          <div>
            <Label htmlFor="list-client-tag" className="text-sm">
              Client/Project Tag
            </Label>
            <Input
              id="list-client-tag"
              placeholder="e.g. Cliente X"
              value={clientTag}
              onChange={(e) => setClientTag(e.target.value)}
              className="mt-1"
            />
          </div>

          <div className="rounded-md bg-muted/50 p-3 text-sm">
            <p className="text-muted-foreground">
              <strong>{selectedPersonIds.length}</strong>{" "}
              {selectedPersonIds.length === 1 ? "person" : "people"} will be
              added to this list.
            </p>
          </div>

          {error && (
            <p className="text-sm text-red-500">{error}</p>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={creating}
          >
            Cancel
          </Button>
          <Button onClick={handleCreate} disabled={creating}>
            {creating ? "Creating..." : "Create List"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
