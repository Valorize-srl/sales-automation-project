"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronDown, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

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
        <div className="absolute top-full mt-1 left-0 z-50 w-[320px] bg-popover border rounded-md shadow-md max-h-60 overflow-y-auto">
          {instantlyCampaigns.length === 0 ? (
            <p className="p-3 text-sm text-muted-foreground">
              No campaigns linked to Instantly
            </p>
          ) : (
            <>
              <button
                className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-accent text-left border-b"
                onClick={() => {
                  if (selectedIds.length === instantlyCampaigns.length) {
                    onSelectionChange([]);
                  } else {
                    onSelectionChange(instantlyCampaigns.map((c) => c.id));
                  }
                }}
              >
                <div
                  className={`h-4 w-4 border rounded flex items-center justify-center ${
                    selectedIds.length === instantlyCampaigns.length
                      ? "bg-primary border-primary"
                      : ""
                  }`}
                >
                  {selectedIds.length === instantlyCampaigns.length && (
                    <Check className="h-3 w-3 text-primary-foreground" />
                  )}
                </div>
                <span className="font-medium">Select all</span>
              </button>
              {instantlyCampaigns.map((c) => (
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
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}
