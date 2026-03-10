"use client";

import { useEffect, useState, useCallback } from "react";
import {
  MessageSquareReply,
  ThumbsUp,
  ThumbsDown,
  Star,
  Clock,
  Calendar,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { CampaignMultiSelect } from "@/components/responses/campaign-multi-select";
import { api } from "@/lib/api";
import {
  Campaign,
  CampaignListResponse,
  ResponseStats,
} from "@/types";

type DateRange = "7d" | "30d" | "custom" | "all";

const DATE_RANGE_PRESETS: { value: DateRange; label: string }[] = [
  { value: "7d", label: "7d" },
  { value: "30d", label: "30d" },
  { value: "custom", label: "Custom" },
  { value: "all", label: "All" },
];

function todayStr() {
  return new Date().toISOString().split("T")[0];
}

function daysAgoStr(days: number) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().split("T")[0];
}

function fmtDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("it-IT", { month: "short", day: "numeric" });
}

function pct(num: number, den: number): string {
  if (den === 0) return "0%";
  return `${((num / den) * 100).toFixed(1)}%`;
}

export default function RepliesAnalyticsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedCampaignIds, setSelectedCampaignIds] = useState<number[]>([]);
  const [stats, setStats] = useState<ResponseStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const [dateRange, setDateRange] = useState<DateRange>("30d");
  const [customStart, setCustomStart] = useState(daysAgoStr(30));
  const [customEnd, setCustomEnd] = useState(todayStr());

  useEffect(() => {
    loadCampaigns();
  }, []);

  const loadCampaigns = async () => {
    try {
      const data = await api.get<CampaignListResponse>("/campaigns");
      setCampaigns(data.campaigns);
    } catch (err) {
      console.error("Failed to load campaigns:", err);
    }
  };

  const getDateParams = useCallback((): { from?: string; to?: string } => {
    if (dateRange === "all") return {};
    if (dateRange === "custom") return { from: customStart, to: customEnd };
    const days = dateRange === "7d" ? 7 : 30;
    return { from: daysAgoStr(days), to: todayStr() };
  }, [dateRange, customStart, customEnd]);

  const loadStats = useCallback(async () => {
    if (selectedCampaignIds.length === 0) {
      setStats(null);
      return;
    }
    setLoading(true);
    try {
      const { from, to } = getDateParams();
      const data = await api.getResponseStats(selectedCampaignIds, from, to);
      setStats(data);
      setLastRefresh(new Date());
    } catch (err) {
      console.error("Failed to load stats:", err);
    } finally {
      setLoading(false);
    }
  }, [selectedCampaignIds, getDateParams]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const chartData = stats?.chart_data.map((d) => ({
    ...d,
    date: fmtDate(d.date),
  })) ?? [];

  const interested = stats?.by_sentiment.interested ?? 0;
  const positive = stats?.by_sentiment.positive ?? 0;
  const neutral = stats?.by_sentiment.neutral ?? 0;
  const negative = stats?.by_sentiment.negative ?? 0;
  const total = stats?.total ?? 0;

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Replies Analytics</h1>
          <p className="text-sm text-muted-foreground">
            Sentiment analysis overview
            {selectedCampaignIds.length > 0 &&
              ` — ${selectedCampaignIds.length} campaign${selectedCampaignIds.length > 1 ? "s" : ""} selected`}
            {lastRefresh && (
              <span className="ml-2 inline-flex items-center gap-1">
                <Clock className="h-3 w-3" />
                Updated {lastRefresh.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })}
              </span>
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <CampaignMultiSelect
            campaigns={campaigns}
            selectedIds={selectedCampaignIds}
            onSelectionChange={setSelectedCampaignIds}
          />
          <div className="flex items-center gap-1 rounded-lg border bg-card p-1">
            <Calendar className="h-4 w-4 text-muted-foreground ml-2" />
            {DATE_RANGE_PRESETS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setDateRange(opt.value)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  dateRange === opt.value
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          {dateRange === "custom" && (
            <div className="flex items-center gap-1.5">
              <input
                type="date"
                value={customStart}
                onChange={(e) => setCustomStart(e.target.value)}
                className="h-8 rounded-md border bg-card px-2 text-xs"
              />
              <span className="text-xs text-muted-foreground">—</span>
              <input
                type="date"
                value={customEnd}
                onChange={(e) => setCustomEnd(e.target.value)}
                className="h-8 rounded-md border bg-card px-2 text-xs"
              />
            </div>
          )}
        </div>
      </div>

      {selectedCampaignIds.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">
          Select one or more campaigns to view analytics
        </div>
      ) : loading ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="rounded-lg border bg-card p-5 animate-pulse">
                <div className="h-4 w-20 bg-muted rounded mb-3" />
                <div className="h-8 w-14 bg-muted rounded" />
              </div>
            ))}
          </div>
          <div className="rounded-lg border bg-card p-5 animate-pulse h-72" />
        </div>
      ) : stats ? (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div className="rounded-lg border bg-card p-5">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm text-muted-foreground">Total Replies</p>
                <MessageSquareReply className="h-4 w-4 text-primary" />
              </div>
              <p className="text-3xl font-bold">{total}</p>
            </div>
            <div className="rounded-lg border bg-green-50 border-green-200 p-5">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm text-green-700">Interested</p>
                <Star className="h-4 w-4 text-green-600" />
              </div>
              <p className="text-3xl font-bold text-green-800">{interested}</p>
              <p className="text-xs text-green-600 mt-1">{pct(interested, total)}</p>
            </div>
            <div className="rounded-lg border bg-blue-50 border-blue-200 p-5">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm text-blue-700">Positive</p>
                <ThumbsUp className="h-4 w-4 text-blue-600" />
              </div>
              <p className="text-3xl font-bold text-blue-800">{positive}</p>
              <p className="text-xs text-blue-600 mt-1">{pct(positive, total)}</p>
            </div>
            <div className="rounded-lg border bg-red-50 border-red-200 p-5">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm text-red-700">Negative</p>
                <ThumbsDown className="h-4 w-4 text-red-600" />
              </div>
              <p className="text-3xl font-bold text-red-800">{negative}</p>
              <p className="text-xs text-red-600 mt-1">{pct(negative, total)}</p>
            </div>
          </div>

          {/* Filtered total highlight */}
          <div className="rounded-lg border bg-primary/5 border-primary/20 p-3 mb-4 flex items-center justify-between">
            <span className="text-sm font-medium">
              Showing <strong className="text-lg">{total}</strong> total replies
              {selectedCampaignIds.length > 0 && ` across ${selectedCampaignIds.length} campaign${selectedCampaignIds.length > 1 ? "s" : ""}`}
            </span>
            <span className="text-xs text-muted-foreground">
              {dateRange === "all" ? "All time" : dateRange === "custom" ? `${customStart} — ${customEnd}` : `Last ${dateRange}`}
            </span>
          </div>

          {/* Chart */}
          <div className="rounded-lg border bg-card p-5 mb-4">
            <h2 className="text-sm font-semibold mb-4">
              Replies by Sentiment — {dateRange === "custom"
                ? `${customStart} → ${customEnd}`
                : dateRange === "all" ? "All time" : `Last ${dateRange}`}
            </h2>
            {chartData.length === 0 ? (
              <div className="h-64 flex items-center justify-center text-muted-foreground text-sm">
                No data available for this period
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      fontSize: 12,
                      borderRadius: 8,
                      border: "1px solid hsl(var(--border))",
                      background: "hsl(var(--card))",
                      color: "hsl(var(--foreground))",
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12, paddingTop: 12 }} />
                  <Line type="monotone" dataKey="interested" name="Interested" stroke="#22c55e" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                  <Line type="monotone" dataKey="positive" name="Positive" stroke="#3b82f6" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                  <Line type="monotone" dataKey="neutral" name="Neutral" stroke="#9ca3af" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                  <Line type="monotone" dataKey="negative" name="Negative" stroke="#ef4444" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Summary Table */}
          <div className="rounded-lg border bg-card overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">Sentiment</th>
                  <th className="text-right px-4 py-3 font-medium">Count</th>
                  <th className="text-right px-4 py-3 font-medium">% of Total</th>
                </tr>
              </thead>
              <tbody>
                {([
                  { key: "interested", label: "Interested", cls: "text-green-700" },
                  { key: "positive", label: "Positive", cls: "text-blue-700" },
                  { key: "neutral", label: "Neutral", cls: "text-gray-600" },
                  { key: "negative", label: "Negative", cls: "text-red-700" },
                ] as const).map(({ key, label, cls }) => {
                  const count = stats.by_sentiment[key] || 0;
                  return (
                    <tr key={key} className="border-t">
                      <td className={`px-4 py-2.5 font-medium ${cls}`}>{label}</td>
                      <td className="text-right px-4 py-2.5">{count}</td>
                      <td className="text-right px-4 py-2.5 text-muted-foreground">{pct(count, total)}</td>
                    </tr>
                  );
                })}
                <tr className="border-t-2 font-semibold">
                  <td className="px-4 py-2.5">Total</td>
                  <td className="text-right px-4 py-2.5">{total}</td>
                  <td className="text-right px-4 py-2.5">100%</td>
                </tr>
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  );
}
