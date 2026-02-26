"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { UsageStatsResponse, SearchHistoryListResponse, ClientSummaryResponse } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { format, subDays } from "date-fns";
import { Calendar, Search, Users } from "lucide-react";
import UsageStatsCards from "@/components/usage/usage-stats-cards";
import SearchHistoryTable from "@/components/usage/search-history-table";
import ClientSummaryTable from "@/components/usage/client-summary-table";

type DateRangePreset = "today" | "yesterday" | "last7" | "last30" | "custom";
type ActiveTab = "overview" | "clients";

export default function UsagePage() {
  const [usageStats, setUsageStats] = useState<UsageStatsResponse | null>(null);
  const [searchHistory, setSearchHistory] = useState<SearchHistoryListResponse | null>(null);
  const [clientSummary, setClientSummary] = useState<ClientSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [preset, setPreset] = useState<DateRangePreset>("last30");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [clientTagFilter, setClientTagFilter] = useState("");
  const [activeTab, setActiveTab] = useState<ActiveTab>("overview");

  const loadData = async (overrideClientTag?: string) => {
    setLoading(true);
    try {
      let start = "";
      let end = "";

      const today = new Date();
      const todayStr = format(today, "yyyy-MM-dd");
      const yesterdayStr = format(subDays(today, 1), "yyyy-MM-dd");

      if (preset === "today") {
        start = todayStr;
        end = todayStr;
      } else if (preset === "yesterday") {
        start = yesterdayStr;
        end = yesterdayStr;
      } else if (preset === "last7") {
        start = format(subDays(today, 7), "yyyy-MM-dd");
        end = todayStr;
      } else if (preset === "last30") {
        start = format(subDays(today, 30), "yyyy-MM-dd");
        end = todayStr;
      } else if (preset === "custom") {
        start = startDate;
        end = endDate;
      }

      const tag = overrideClientTag !== undefined ? overrideClientTag : clientTagFilter;

      const [stats, history, clients] = await Promise.all([
        api.getUsageStats(start, end, tag || undefined),
        api.getSearchHistory(start, end, tag || undefined, 100),
        api.getClientSummary(),
      ]);

      setUsageStats(stats);
      setSearchHistory(history);
      setClientSummary(clients);
    } catch (error) {
      console.error("Failed to load usage data:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleApplyFilters = () => {
    loadData();
  };

  const handleClientClick = (clientTag: string) => {
    setClientTagFilter(clientTag);
    setActiveTab("overview");
    loadData(clientTag);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Usage & Costs</h1>
          <p className="text-muted-foreground mt-1">
            Track Apollo credits, Claude tokens, and total spending
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b">
        {([
          { key: "overview" as const, label: "Overview" },
          { key: "clients" as const, label: "Per Client" },
        ]).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.key
                ? "border-b-2 border-primary text-primary"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "overview" && (
        <>
          {/* Filters */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="h-5 w-5" />
                Filters
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                  <Label>Date Range</Label>
                  <Select
                    value={preset}
                    onValueChange={(value) => setPreset(value as DateRangePreset)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="today">Today</SelectItem>
                      <SelectItem value="yesterday">Yesterday</SelectItem>
                      <SelectItem value="last7">Last 7 Days</SelectItem>
                      <SelectItem value="last30">Last 30 Days</SelectItem>
                      <SelectItem value="custom">Custom Range</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {preset === "custom" && (
                  <>
                    <div>
                      <Label>Start Date</Label>
                      <Input
                        type="date"
                        value={startDate}
                        onChange={(e) => setStartDate(e.target.value)}
                      />
                    </div>
                    <div>
                      <Label>End Date</Label>
                      <Input
                        type="date"
                        value={endDate}
                        onChange={(e) => setEndDate(e.target.value)}
                      />
                    </div>
                  </>
                )}

                <div>
                  <Label>Client/Project Tag (Optional)</Label>
                  <div className="flex gap-1">
                    <Input
                      placeholder="Filter by client tag..."
                      value={clientTagFilter}
                      onChange={(e) => setClientTagFilter(e.target.value)}
                    />
                    {clientTagFilter && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="px-2 shrink-0"
                        onClick={() => {
                          setClientTagFilter("");
                          loadData("");
                        }}
                      >
                        &times;
                      </Button>
                    )}
                  </div>
                </div>

                <div className="flex items-end">
                  <Button onClick={handleApplyFilters} className="w-full">
                    <Search className="h-4 w-4 mr-2" />
                    Apply Filters
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Stats Cards */}
          {usageStats && <UsageStatsCards stats={usageStats.stats} />}

          {/* Search History Table */}
          {searchHistory && (
            <Card>
              <CardHeader>
                <CardTitle>Search History</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Showing {searchHistory.history.length} of {searchHistory.total} total searches
                </p>
              </CardHeader>
              <CardContent>
                <SearchHistoryTable history={searchHistory.history} />
              </CardContent>
            </Card>
          )}
        </>
      )}

      {activeTab === "clients" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              Cost per Client
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              Total costs across all sessions and searches, grouped by client/project tag.
              Includes all Claude token costs (chat + searches).
            </p>
          </CardHeader>
          <CardContent>
            {clientSummary ? (
              <ClientSummaryTable
                data={clientSummary}
                onClientClick={handleClientClick}
              />
            ) : loading ? (
              <div className="text-center py-8 text-muted-foreground text-sm">
                Loading client data...
              </div>
            ) : null}
          </CardContent>
        </Card>
      )}

      {loading && (
        <div className="flex justify-center py-12">
          <div className="text-muted-foreground">Loading usage data...</div>
        </div>
      )}
    </div>
  );
}
