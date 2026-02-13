"use client";

import { useState, useEffect } from "react";
import { Loader2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  ICP,
  Campaign,
  InstantlyEmailAccount,
  InstantlyEmailAccountListResponse,
} from "@/types";

interface CreateCampaignDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  icps: ICP[];
  onCreated: () => void;
}

const NO_ICP = "__none__";

const TIMEZONES = [
  "Europe/Rome",
  "Europe/London",
  "Europe/Berlin",
  "Europe/Paris",
  "America/New_York",
  "America/Chicago",
  "America/Los_Angeles",
  "Asia/Tokyo",
  "Etc/UTC",
];

const DAYS = [
  { key: "1", label: "Mon" },
  { key: "2", label: "Tue" },
  { key: "3", label: "Wed" },
  { key: "4", label: "Thu" },
  { key: "5", label: "Fri" },
  { key: "6", label: "Sat" },
  { key: "0", label: "Sun" },
];

export function CreateCampaignDialog({
  open,
  onOpenChange,
  icps,
  onCreated,
}: CreateCampaignDialogProps) {
  // Base
  const [name, setName] = useState("");
  const [icpId, setIcpId] = useState<string>(NO_ICP);
  const [createOnInstantly, setCreateOnInstantly] = useState(true);

  // Schedule
  const [timezone, setTimezone] = useState("Europe/Rome");
  const [scheduleFrom, setScheduleFrom] = useState("09:00");
  const [scheduleTo, setScheduleTo] = useState("17:00");
  const [scheduleDays, setScheduleDays] = useState<Record<string, boolean>>({
    "0": false,
    "1": true,
    "2": true,
    "3": true,
    "4": true,
    "5": true,
    "6": false,
  });

  // Email accounts
  const [emailAccounts, setEmailAccounts] = useState<InstantlyEmailAccount[]>(
    []
  );
  const [selectedEmails, setSelectedEmails] = useState<Set<string>>(new Set());
  const [loadingAccounts, setLoadingAccounts] = useState(false);

  // Sending options
  const [dailyLimit, setDailyLimit] = useState<string>("");
  const [emailGap, setEmailGap] = useState<string>("");
  const [stopOnReply, setStopOnReply] = useState(true);
  const [stopOnAutoReply, setStopOnAutoReply] = useState(true);
  const [linkTracking, setLinkTracking] = useState(false);
  const [openTracking, setOpenTracking] = useState(true);
  const [textOnly, setTextOnly] = useState(false);

  // UI state
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load email accounts when dialog opens and createOnInstantly is enabled
  useEffect(() => {
    if (open && createOnInstantly) {
      loadEmailAccounts();
    }
  }, [open, createOnInstantly]);

  const loadEmailAccounts = async () => {
    setLoadingAccounts(true);
    try {
      const data = await api.get<InstantlyEmailAccountListResponse>(
        "/campaigns/instantly/accounts"
      );
      setEmailAccounts(data.accounts);
    } catch (err) {
      console.error("Failed to load email accounts:", err);
    } finally {
      setLoadingAccounts(false);
    }
  };

  const reset = () => {
    setName("");
    setIcpId(NO_ICP);
    setCreateOnInstantly(true);
    setTimezone("Europe/Rome");
    setScheduleFrom("09:00");
    setScheduleTo("17:00");
    setScheduleDays({
      "0": false,
      "1": true,
      "2": true,
      "3": true,
      "4": true,
      "5": true,
      "6": false,
    });
    setSelectedEmails(new Set());
    setDailyLimit("");
    setEmailGap("");
    setStopOnReply(true);
    setStopOnAutoReply(true);
    setLinkTracking(false);
    setOpenTracking(true);
    setTextOnly(false);
    setCreating(false);
    setError(null);
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) reset();
    onOpenChange(open);
  };

  const toggleDay = (day: string) => {
    setScheduleDays((prev) => ({ ...prev, [day]: !prev[day] }));
  };

  const toggleEmail = (email: string) => {
    setSelectedEmails((prev) => {
      const next = new Set(prev);
      if (next.has(email)) next.delete(email);
      else next.add(email);
      return next;
    });
  };

  const toggleAllEmails = () => {
    if (selectedEmails.size === emailAccounts.length) {
      setSelectedEmails(new Set());
    } else {
      setSelectedEmails(new Set(emailAccounts.map((a) => a.email)));
    }
  };

  const handleCreate = async () => {
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        name: name.trim(),
        icp_id: icpId !== NO_ICP ? parseInt(icpId) : null,
        create_on_instantly: createOnInstantly,
      };

      if (createOnInstantly) {
        payload.schedule_timezone = timezone;
        payload.schedule_from = scheduleFrom;
        payload.schedule_to = scheduleTo;
        payload.schedule_days = scheduleDays;
        payload.email_accounts = Array.from(selectedEmails);
        payload.stop_on_reply = stopOnReply;
        payload.stop_on_auto_reply = stopOnAutoReply;
        payload.link_tracking = linkTracking;
        payload.open_tracking = openTracking;
        payload.text_only = textOnly;
        if (dailyLimit) payload.daily_limit = parseInt(dailyLimit);
        if (emailGap) payload.email_gap = parseInt(emailGap);
      }

      await api.post<Campaign>("/campaigns", payload);
      onCreated();
      handleOpenChange(false);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create campaign"
      );
    } finally {
      setCreating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[700px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create Campaign</DialogTitle>
        </DialogHeader>

        <div className="space-y-5 pt-2">
          {/* Section 1: Base Info */}
          <div className="space-y-3">
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
              <Select
                value={icpId}
                onValueChange={setIcpId}
                disabled={creating}
              >
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
          </div>

          {createOnInstantly && (
            <>
              <Separator />

              {/* Section 2: Schedule */}
              <div className="space-y-3">
                <h4 className="font-medium text-sm">Schedule</h4>

                <div>
                  <Label>Timezone</Label>
                  <Select
                    value={timezone}
                    onValueChange={setTimezone}
                    disabled={creating}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {TIMEZONES.map((tz) => (
                        <SelectItem key={tz} value={tz}>
                          {tz}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>From</Label>
                    <Input
                      className="mt-1"
                      type="time"
                      value={scheduleFrom}
                      onChange={(e) => setScheduleFrom(e.target.value)}
                      disabled={creating}
                    />
                  </div>
                  <div>
                    <Label>To</Label>
                    <Input
                      className="mt-1"
                      type="time"
                      value={scheduleTo}
                      onChange={(e) => setScheduleTo(e.target.value)}
                      disabled={creating}
                    />
                  </div>
                </div>

                <div>
                  <Label>Active Days</Label>
                  <div className="flex gap-2 mt-1">
                    {DAYS.map((d) => (
                      <button
                        key={d.key}
                        type="button"
                        onClick={() => toggleDay(d.key)}
                        disabled={creating}
                        className={`px-3 py-1.5 text-xs font-medium rounded-md border transition-colors ${
                          scheduleDays[d.key]
                            ? "bg-primary text-primary-foreground border-primary"
                            : "bg-background text-muted-foreground border-input hover:bg-accent"
                        }`}
                      >
                        {d.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <Separator />

              {/* Section 3: Email Accounts */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-medium text-sm">Email Accounts</h4>
                  {emailAccounts.length > 0 && (
                    <button
                      type="button"
                      onClick={toggleAllEmails}
                      className="text-xs text-primary hover:underline"
                      disabled={creating}
                    >
                      {selectedEmails.size === emailAccounts.length
                        ? "Deselect All"
                        : "Select All"}
                    </button>
                  )}
                </div>

                {loadingAccounts ? (
                  <p className="text-sm text-muted-foreground">
                    Loading accounts...
                  </p>
                ) : emailAccounts.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No email accounts found on Instantly.
                  </p>
                ) : (
                  <div className="max-h-[150px] overflow-y-auto border rounded-md p-2 space-y-1">
                    {emailAccounts.map((account) => (
                      <label
                        key={account.email}
                        className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-accent cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={selectedEmails.has(account.email)}
                          onChange={() => toggleEmail(account.email)}
                          disabled={creating}
                          className="h-4 w-4 rounded border-gray-300"
                        />
                        <span className="text-sm">{account.email}</span>
                        {account.first_name && (
                          <span className="text-xs text-muted-foreground">
                            ({account.first_name} {account.last_name || ""})
                          </span>
                        )}
                      </label>
                    ))}
                  </div>
                )}

                <p className="text-xs text-muted-foreground">
                  {selectedEmails.size} account
                  {selectedEmails.size !== 1 ? "s" : ""} selected
                </p>
              </div>

              <Separator />

              {/* Section 4: Sending Options */}
              <div className="space-y-3">
                <h4 className="font-medium text-sm">Sending Options</h4>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Daily Limit (per account)</Label>
                    <Input
                      className="mt-1"
                      type="number"
                      min={1}
                      placeholder="Default"
                      value={dailyLimit}
                      onChange={(e) => setDailyLimit(e.target.value)}
                      disabled={creating}
                    />
                  </div>
                  <div>
                    <Label>Email Gap (minutes)</Label>
                    <Input
                      className="mt-1"
                      type="number"
                      min={1}
                      placeholder="Default"
                      value={emailGap}
                      onChange={(e) => setEmailGap(e.target.value)}
                      disabled={creating}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={stopOnReply}
                      onChange={(e) => setStopOnReply(e.target.checked)}
                      disabled={creating}
                      className="h-4 w-4 rounded border-gray-300"
                    />
                    <span className="text-sm">Stop on Reply</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={stopOnAutoReply}
                      onChange={(e) => setStopOnAutoReply(e.target.checked)}
                      disabled={creating}
                      className="h-4 w-4 rounded border-gray-300"
                    />
                    <span className="text-sm">Stop on Auto Reply</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={linkTracking}
                      onChange={(e) => setLinkTracking(e.target.checked)}
                      disabled={creating}
                      className="h-4 w-4 rounded border-gray-300"
                    />
                    <span className="text-sm">Link Tracking</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={openTracking}
                      onChange={(e) => setOpenTracking(e.target.checked)}
                      disabled={creating}
                      className="h-4 w-4 rounded border-gray-300"
                    />
                    <span className="text-sm">Open Tracking</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={textOnly}
                      onChange={(e) => setTextOnly(e.target.checked)}
                      disabled={creating}
                      className="h-4 w-4 rounded border-gray-300"
                    />
                    <span className="text-sm">Text Only</span>
                  </label>
                </div>
              </div>
            </>
          )}

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
