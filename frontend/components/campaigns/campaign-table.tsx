"use client";

import { RefreshCw, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Campaign, CampaignStatus } from "@/types";

interface CampaignTableProps {
  campaigns: Campaign[];
  onSyncMetrics: (id: number) => void;
  onViewDetails: (campaign: Campaign) => void;
  loading: boolean;
}

const statusColors: Record<CampaignStatus, string> = {
  draft: "bg-gray-100 text-gray-800",
  active: "bg-green-100 text-green-800",
  paused: "bg-yellow-100 text-yellow-800",
  completed: "bg-blue-100 text-blue-800",
};

function formatRate(numerator: number, denominator: number): string {
  if (denominator === 0) return "—";
  return `${((numerator / denominator) * 100).toFixed(1)}%`;
}

export function CampaignTable({
  campaigns,
  onSyncMetrics,
  onViewDetails,
  loading,
}: CampaignTableProps) {
  if (loading) {
    return (
      <p className="text-muted-foreground py-8 text-center">Loading...</p>
    );
  }

  if (campaigns.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">
          No campaigns yet. Sync from Instantly or create a new one.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-md border overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>ICP</TableHead>
            <TableHead className="text-right">Sent</TableHead>
            <TableHead className="text-right">Opened</TableHead>
            <TableHead className="text-right">Replied</TableHead>
            <TableHead className="text-right">Open Rate</TableHead>
            <TableHead className="text-right">Reply Rate</TableHead>
            <TableHead className="w-[100px]"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {campaigns.map((campaign) => (
            <TableRow
              key={campaign.id}
              className="cursor-pointer"
              onClick={() => onViewDetails(campaign)}
            >
              <TableCell className="font-medium">{campaign.name}</TableCell>
              <TableCell>
                <Badge
                  variant="outline"
                  className={statusColors[campaign.status] || ""}
                >
                  {campaign.status}
                </Badge>
              </TableCell>
              <TableCell>
                {campaign.icp_name || (
                  <span className="text-muted-foreground text-xs">
                    Imported
                  </span>
                )}
              </TableCell>
              <TableCell className="text-right">
                {campaign.total_sent}
              </TableCell>
              <TableCell className="text-right">
                {campaign.total_opened}
              </TableCell>
              <TableCell className="text-right">
                {campaign.total_replied}
              </TableCell>
              <TableCell className="text-right">
                {formatRate(campaign.total_opened, campaign.total_sent)}
              </TableCell>
              <TableCell className="text-right">
                {formatRate(campaign.total_replied, campaign.total_sent)}
              </TableCell>
              <TableCell>
                <div className="flex gap-1">
                  {campaign.instantly_campaign_id && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      title="Sync metrics"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSyncMetrics(campaign.id);
                      }}
                    >
                      <RefreshCw className="h-3 w-3" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    title="View details"
                    onClick={(e) => {
                      e.stopPropagation();
                      onViewDetails(campaign);
                    }}
                  >
                    <Eye className="h-3 w-3" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
