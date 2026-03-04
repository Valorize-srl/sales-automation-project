"use client";

import { useEffect, useState } from "react";
import { Loader2, Upload, Check, Search, List } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { Campaign, Person, LeadList, LeadUploadResponse, AddListToCampaignResponse } from "@/types";

type Mode = "people" | "lists";

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
  const [mode, setMode] = useState<Mode>("people");

  // People mode state
  const [people, setPeople] = useState<Person[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [loadingPeople, setLoadingPeople] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [result, setResult] = useState<LeadUploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // Lists mode state
  const [lists, setLists] = useState<LeadList[]>([]);
  const [loadingLists, setLoadingLists] = useState(false);
  const [selectedListId, setSelectedListId] = useState<number | null>(null);
  const [listResult, setListResult] = useState<AddListToCampaignResponse | null>(null);

  useEffect(() => {
    if (open && campaign) {
      loadPeople();
      loadLists();
      setSelectedIds(new Set());
      setResult(null);
      setListResult(null);
      setError(null);
      setSearchQuery("");
      setSelectedListId(null);
      setMode("people");
    }
  }, [open, campaign]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadPeople = async () => {
    if (!campaign) return;
    setLoadingPeople(true);
    try {
      const data = await api.getPeople({ limit: 500 });
      setPeople(data.people);
    } catch (err) {
      console.error("Failed to load people:", err);
    } finally {
      setLoadingPeople(false);
    }
  };

  const loadLists = async () => {
    setLoadingLists(true);
    try {
      const data = await api.getLeadLists();
      setLists(data.lists);
    } catch (err) {
      console.error("Failed to load lists:", err);
    } finally {
      setLoadingLists(false);
    }
  };

  const togglePerson = (id: number) => {
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

  const filteredPeople = people.filter((p) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      p.first_name?.toLowerCase().includes(q) ||
      p.last_name?.toLowerCase().includes(q) ||
      p.email?.toLowerCase().includes(q) ||
      p.company_name?.toLowerCase().includes(q)
    );
  });

  const toggleAll = () => {
    if (selectedIds.size === filteredPeople.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredPeople.map((p) => p.id)));
    }
  };

  const handlePush = async () => {
    if (!campaign || selectedIds.size === 0) return;
    setPushing(true);
    setError(null);
    try {
      const data = await api.post<LeadUploadResponse>(
        `/campaigns/${campaign.id}/upload-leads`,
        { person_ids: Array.from(selectedIds) }
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

  const handlePushList = async () => {
    if (!campaign || !selectedListId) return;
    setPushing(true);
    setError(null);
    try {
      const data = await api.addListToCampaign(campaign.id, selectedListId);
      setListResult(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to push list"
      );
    } finally {
      setPushing(false);
    }
  };

  const hasResult = result || listResult;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[550px] max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Push Leads to Instantly</DialogTitle>
        </DialogHeader>

        {hasResult ? (
          <div className="space-y-4 pt-2 text-center">
            <div className="py-4">
              <div className="mx-auto w-12 h-12 rounded-full bg-green-100 flex items-center justify-center mb-3">
                <Check className="h-6 w-6 text-green-600" />
              </div>
              <p className="text-lg font-medium">Upload Complete</p>
            </div>
            {result && (
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
            )}
            {listResult && (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-2xl font-bold text-green-600">
                      {listResult.pushed_to_instantly}
                    </p>
                    <p className="text-muted-foreground">Pushed</p>
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-red-600">
                      {listResult.errors}
                    </p>
                    <p className="text-muted-foreground">Errors</p>
                  </div>
                </div>
                {listResult.instantly_lead_count != null && (
                  <div className="text-sm bg-blue-50 rounded-md p-3 border border-blue-200">
                    <p className="font-medium text-blue-800">
                      Verifica Instantly: {listResult.instantly_lead_count} lead totali nella campagna
                    </p>
                  </div>
                )}
                {listResult.skipped_invalid ? (
                  <p className="text-xs text-muted-foreground">
                    {listResult.skipped_invalid} email non valide saltate
                  </p>
                ) : null}
                {listResult.error_details && listResult.error_details.length > 0 && (
                  <div className="text-xs text-red-600 bg-red-50 rounded p-2 max-h-[100px] overflow-y-auto">
                    {listResult.error_details.map((d, i) => (
                      <p key={i}>{d}</p>
                    ))}
                  </div>
                )}
                {/* Debug info */}
                <div className="text-xs text-muted-foreground bg-muted/50 rounded p-2 space-y-1">
                  <p>Instantly Campaign ID: {(listResult as any).instantly_campaign_id || "N/A"}</p>
                  <p>Valid leads: {(listResult as any).valid_leads || 0}</p>
                  {(listResult as any).api_responses?.length > 0 && (
                    <details>
                      <summary className="cursor-pointer">API Response</summary>
                      <pre className="mt-1 text-[10px] whitespace-pre-wrap break-all">
                        {JSON.stringify((listResult as any).api_responses[0], null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              </div>
            )}
            <Button onClick={() => onOpenChange(false)} className="mt-4">
              Done
            </Button>
          </div>
        ) : (
          <div className="space-y-4 pt-2">
            {/* Mode tabs */}
            <div className="flex border-b">
              <button
                onClick={() => setMode("people")}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  mode === "people"
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                People
              </button>
              <button
                onClick={() => setMode("lists")}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  mode === "lists"
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                <span className="flex items-center gap-1.5">
                  <List className="h-3.5 w-3.5" /> Lists
                </span>
              </button>
            </div>

            {mode === "people" && (
              <>
                <p className="text-sm text-muted-foreground">
                  Select people from your database to push to this Instantly campaign.
                </p>

                {/* Search */}
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search by name, email, or company..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-8 h-9 text-sm"
                  />
                </div>

                {loadingPeople ? (
                  <p className="text-center text-muted-foreground py-4">
                    Loading people...
                  </p>
                ) : people.length === 0 ? (
                  <p className="text-center text-muted-foreground py-4">
                    No people found. Import leads from Prospecting first.
                  </p>
                ) : (
                  <>
                    <div className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={selectedIds.size === filteredPeople.length && filteredPeople.length > 0}
                        onChange={toggleAll}
                        className="h-4 w-4 rounded border-gray-300"
                      />
                      <span>
                        Select all ({filteredPeople.length} people)
                      </span>
                      {selectedIds.size > 0 && (
                        <span className="text-muted-foreground">
                          — {selectedIds.size} selected
                        </span>
                      )}
                    </div>

                    <Separator />

                    <div className="max-h-[300px] overflow-y-auto space-y-1">
                      {filteredPeople.map((person) => (
                        <label
                          key={person.id}
                          className="flex items-center gap-2 p-2 rounded hover:bg-muted cursor-pointer text-sm"
                        >
                          <input
                            type="checkbox"
                            checked={selectedIds.has(person.id)}
                            onChange={() => togglePerson(person.id)}
                            className="h-4 w-4 rounded border-gray-300"
                          />
                          <span className="font-medium">
                            {person.first_name} {person.last_name}
                          </span>
                          <span className="text-muted-foreground truncate flex-1">
                            {person.email}
                          </span>
                          {person.company_name && (
                            <span className="text-xs text-muted-foreground">
                              {person.company_name}
                            </span>
                          )}
                        </label>
                      ))}
                    </div>
                  </>
                )}
              </>
            )}

            {mode === "lists" && (
              <>
                <p className="text-sm text-muted-foreground">
                  Select a lead list to push all its people to this Instantly campaign.
                </p>

                {loadingLists ? (
                  <p className="text-center text-muted-foreground py-4">
                    Loading lists...
                  </p>
                ) : lists.length === 0 ? (
                  <p className="text-center text-muted-foreground py-4">
                    No lead lists found. Create a list from the Leads page first.
                  </p>
                ) : (
                  <div className="max-h-[350px] overflow-y-auto space-y-1">
                    {lists.map((list) => (
                      <label
                        key={list.id}
                        className={`flex items-center gap-3 p-3 rounded border cursor-pointer text-sm transition-colors ${
                          selectedListId === list.id
                            ? "border-primary bg-primary/5"
                            : "border-transparent hover:bg-muted"
                        }`}
                      >
                        <input
                          type="radio"
                          name="lead-list"
                          checked={selectedListId === list.id}
                          onChange={() => setSelectedListId(list.id)}
                          className="h-4 w-4"
                        />
                        <div className="flex-1 min-w-0">
                          <p className="font-medium">{list.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {list.people_count} people
                            {list.companies_count > 0 && `, ${list.companies_count} companies`}
                            {list.client_tag && ` · ${list.client_tag}`}
                          </p>
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {new Date(list.created_at).toLocaleDateString()}
                        </span>
                      </label>
                    ))}
                  </div>
                )}
              </>
            )}

            {error && <p className="text-sm text-destructive">{error}</p>}

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              {mode === "people" ? (
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
              ) : (
                <Button
                  onClick={handlePushList}
                  disabled={!selectedListId || pushing}
                  className="gap-1"
                >
                  {pushing ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Upload className="h-4 w-4" />
                  )}
                  {pushing ? "Pushing..." : "Push List"}
                </Button>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
