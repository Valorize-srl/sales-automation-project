"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  FileText,
  Search,
  DollarSign,
  MessageSquare,
  Zap,
  Building2,
  Sparkles
} from "lucide-react";

interface ICPDraft {
  name?: string;
  industry?: string;
  company_size?: string;
  job_titles?: string;
  geography?: string;
  keywords?: string;
}

interface LastSearchResults {
  type: string;
  count: number;
  company_ids: number[];
}

interface SessionStats {
  totalCost: number;
  messageCount: number;
  apolloCredits: number;
}

interface SessionSidebarProps {
  currentIcp: Record<string, unknown> | null;
  lastSearchResults: LastSearchResults | null;
  sessionStats: SessionStats;
  onEnrichCompanies?: () => void;
}

export function SessionSidebar({
  currentIcp,
  lastSearchResults,
  sessionStats,
  onEnrichCompanies,
}: SessionSidebarProps) {
  return (
    <div className="space-y-4">
      {/* ICP Draft Card */}
      {currentIcp && <ICPDraftCard icp={currentIcp as ICPDraft} />}

      {/* Last Search Card */}
      {lastSearchResults && (
        <LastSearchCard
          results={lastSearchResults}
          onEnrich={onEnrichCompanies}
        />
      )}

      {/* Session Stats Card */}
      <SessionStatsCard stats={sessionStats} />
    </div>
  );
}

function ICPDraftCard({ icp }: { icp: ICPDraft }) {
  const fields = [
    { label: "Industry", value: icp.industry },
    { label: "Company Size", value: icp.company_size },
    { label: "Job Titles", value: icp.job_titles },
    { label: "Geography", value: icp.geography },
    { label: "Keywords", value: icp.keywords },
  ].filter((f) => f.value);

  return (
    <Card className="border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-primary" />
            <CardTitle className="text-sm">ICP Draft</CardTitle>
          </div>
          <Badge variant="secondary" className="text-xs">
            <Sparkles className="h-3 w-3 mr-1" />
            Building...
          </Badge>
        </div>
      </CardHeader>
      <Separator />
      <CardContent className="pt-4">
        {icp.name && (
          <p className="font-semibold text-sm mb-3">{icp.name}</p>
        )}
        <div className="space-y-2">
          {fields.map((field) => (
            <div key={field.label}>
              <p className="text-xs text-muted-foreground font-medium">
                {field.label}
              </p>
              <p className="text-xs mt-0.5 line-clamp-2">{field.value}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function LastSearchCard({
  results,
  onEnrich,
}: {
  results: LastSearchResults;
  onEnrich?: () => void;
}) {
  const isCompanySearch = results.type === "companies";

  return (
    <Card className="border-blue-500/20 bg-gradient-to-br from-blue-500/5 to-transparent">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Search className="h-4 w-4 text-blue-500" />
            <CardTitle className="text-sm">Last Search</CardTitle>
          </div>
          <Badge variant="outline" className="text-xs">
            {results.count} results
          </Badge>
        </div>
      </CardHeader>
      <Separator />
      <CardContent className="pt-4">
        <div className="space-y-3">
          <div>
            <p className="text-xs text-muted-foreground font-medium">Type</p>
            <div className="flex items-center gap-1 mt-0.5">
              {isCompanySearch ? (
                <Building2 className="h-3 w-3 text-blue-500" />
              ) : (
                <MessageSquare className="h-3 w-3 text-blue-500" />
              )}
              <p className="text-xs capitalize">{results.type}</p>
            </div>
          </div>

          <div>
            <p className="text-xs text-muted-foreground font-medium">
              Available IDs
            </p>
            <p className="text-xs mt-0.5">
              {results.company_ids.length > 5
                ? `${results.company_ids.slice(0, 5).join(", ")}... (+${
                    results.company_ids.length - 5
                  } more)`
                : results.company_ids.join(", ")}
            </p>
          </div>

          {isCompanySearch && onEnrich && (
            <>
              <Separator className="my-2" />
              <Button
                size="sm"
                variant="outline"
                className="w-full gap-2 text-xs"
                onClick={onEnrich}
              >
                <Sparkles className="h-3 w-3" />
                Enrich with Contact Emails
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function SessionStatsCard({ stats }: { stats: SessionStats }) {
  return (
    <Card className="border-muted">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Zap className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-sm">Session Stats</CardTitle>
        </div>
      </CardHeader>
      <Separator />
      <CardContent className="pt-4">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <MessageSquare className="h-3 w-3 text-muted-foreground" />
              <p className="text-xs text-muted-foreground">Messages</p>
            </div>
            <p className="text-sm font-medium">{stats.messageCount}</p>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Search className="h-3 w-3 text-muted-foreground" />
              <p className="text-xs text-muted-foreground">Apollo Credits</p>
            </div>
            <p className="text-sm font-medium">{stats.apolloCredits}</p>
          </div>

          <Separator />

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <DollarSign className="h-3 w-3 text-green-600" />
              <p className="text-xs font-medium">Total Cost</p>
            </div>
            <p className="text-sm font-bold text-green-600">
              ${stats.totalCost.toFixed(4)}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
