"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronDown, Check, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Campaign } from "@/types";

interface CampaignMultiSelectProps {
  campaigns: Campaign[];
  selectedIds: number[];
  onSelectionChange: (ids: number[]) => void;
}

export function CampaignMultiSelect({
  campaigns,
  selectedIds,
  onSelectionChange,
}: CampaignMultiSelectProps) {
  const [open, setOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setSearchQuery(""); // Reset search when closing
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (open && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [open]);

  const toggle = (id: number) => {
    if (selectedIds.includes(id)) {
      onSelectionChange(selectedIds.filter((i) => i !== id));
    } else {
      onSelectionChange([...selectedIds, id]);
    }
  };

  const instantlyCampaigns = campaigns.filter(
    (c) => c.instantly_campaign_id
  );

  // Filter campaigns based on search query
  const filteredCampaigns = instantlyCampaigns.filter((c) =>
    c.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="relative" ref={ref}>
      <Button
        variant="outline"
        onClick={() => setOpen(!open)}
        className="gap-1 min-w-[220px] justify-between"
      >
        <span className="truncate">
          {selectedIds.length === 0
            ? "Select campaigns"
            : `${selectedIds.length} campaign${selectedIds.length > 1 ? "s" : ""} selected`}
        </span>
        <ChevronDown className="h-4 w-4 shrink-0" />
      </Button>
      {open && (
        <div className="absolute top-full mt-1 left-0 z-50 w-[320px] bg-popover border rounded-md shadow-md">
          {instantlyCampaigns.length === 0 ? (
            <p className="p-3 text-sm text-muted-foreground">
              No campaigns linked to Instantly
            </p>
          ) : (
            <>
              <div className="p-2 border-b sticky top-0 bg-popover">
                <div className="relative">
                  <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    ref={searchInputRef}
                    type="text"
                    placeholder="Search campaigns..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-8 h-8 text-sm"
                  />
                </div>
              </div>
              <div className="max-h-60 overflow-y-auto">
                <button
                  className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-accent text-left border-b sticky top-0 bg-popover"
                  onClick={() => {
                    const filteredIds = filteredCampaigns.map((c) => c.id);
                    const allFilteredSelected = filteredIds.every((id) =>
                      selectedIds.includes(id)
                    );
                    if (allFilteredSelected) {
                      // Deselect all filtered campaigns
                      onSelectionChange(
                        selectedIds.filter((id) => !filteredIds.includes(id))
                      );
                    } else {
                      // Select all filtered campaigns (keep existing selections)
                      const newSelection = [
                        ...selectedIds.filter((id) => !filteredIds.includes(id)),
                        ...filteredIds,
                      ];
                      onSelectionChange(newSelection);
                    }
                  }}
                >
                  <div
                    className={`h-4 w-4 border rounded flex items-center justify-center ${
                      filteredCampaigns.length > 0 &&
                      filteredCampaigns.every((c) => selectedIds.includes(c.id))
                        ? "bg-primary border-primary"
                        : ""
                    }`}
                  >
                    {filteredCampaigns.length > 0 &&
                      filteredCampaigns.every((c) =>
                        selectedIds.includes(c.id)
                      ) && <Check className="h-3 w-3 text-primary-foreground" />}
                  </div>
                  <span className="font-medium">
                    Select all {searchQuery && `(${filteredCampaigns.length})`}
                  </span>
                </button>
                {filteredCampaigns.length === 0 ? (
                  <p className="p-3 text-sm text-muted-foreground text-center">
                    No campaigns match your search
                  </p>
                ) : (
                  filteredCampaigns.map((c) => (
                <button
                  key={c.id}
                  className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-accent text-left"
                  onClick={() => toggle(c.id)}
                >
                  <div
                    className={`h-4 w-4 border rounded flex items-center justify-center ${
                      selectedIds.includes(c.id)
                        ? "bg-primary border-primary"
                        : ""
                    }`}
                  >
                    {selectedIds.includes(c.id) && (
                      <Check className="h-3 w-3 text-primary-foreground" />
                    )}
                  </div>
                  <span className="truncate">{c.name}</span>
                  <Badge variant="outline" className="ml-auto text-xs shrink-0">
                    {c.status}
                  </Badge>
                </button>
              ))
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
