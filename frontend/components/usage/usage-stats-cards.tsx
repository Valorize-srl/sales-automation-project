import { UsageStats } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DollarSign, Search, Zap, TrendingUp } from "lucide-react";

const TOOL_LABELS: Record<string, string> = {
  people: "Apollo People",
  companies: "Apollo Companies",
  google_maps: "Google Maps",
  website_contacts: "Website Scraper",
  linkedin_companies: "LinkedIn Aziende",
  linkedin_people: "LinkedIn Persone",
};

interface UsageStatsCardsProps {
  stats: UsageStats;
}

export default function UsageStatsCards({ stats }: UsageStatsCardsProps) {
  const byTool = stats.cost_breakdown.by_tool;

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Cost</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${stats.total_cost_usd.toFixed(2)}</div>
            <p className="text-xs text-muted-foreground mt-1">
              Tools: ${stats.cost_breakdown.apollo_usd.toFixed(2)} | Claude: $
              {stats.cost_breakdown.claude_usd.toFixed(2)}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Searches</CardTitle>
            <Search className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total_searches}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {stats.total_results} results total
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Apollo Credits</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total_apollo_credits}</div>
            <p className="text-xs text-muted-foreground mt-1">
              @ $0.10 per credit
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Claude Tokens</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(
                (stats.total_claude_input_tokens + stats.total_claude_output_tokens) /
                1000
              ).toFixed(1)}
              k
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {(stats.total_claude_input_tokens / 1000).toFixed(1)}k in | {(stats.total_claude_output_tokens / 1000).toFixed(1)}k out
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Per-tool cost breakdown */}
      {byTool && Object.keys(byTool).length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Cost per Tool</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2 md:grid-cols-3 lg:grid-cols-4">
              {Object.entries(byTool).map(([tool, cost]) => (
                <div key={tool} className="flex items-center justify-between rounded-md border px-3 py-2">
                  <span className="text-sm text-muted-foreground">
                    {TOOL_LABELS[tool] || tool}
                  </span>
                  <span className="text-sm font-medium">${cost.toFixed(4)}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
