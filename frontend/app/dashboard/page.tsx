"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import {
  Users,
  Building2,
  Mail,
  Send,
  Eye,
  MessageSquareReply,
  Clock,
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
import { api } from "@/lib/api";
import { DashboardStats } from "@/types";

function pct(num: number, den: number): string {
  if (den === 0) return "0%";
  return `${((num / den) * 100).toFixed(1)}%`;
}

function fmtDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("it-IT", { month: "short", day: "numeric" });
}

interface KpiCard {
  label: string;
  value: number;
  sub?: string;
  icon: React.ElementType;
  color: string;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);
  const POLL_INTERVAL = 5 * 60 * 1000; // 5 minutes

  const loadStats = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const data = await api.get<DashboardStats>("/analytics/dashboard");
      setStats(data);
      setLastRefresh(new Date());
    } catch (err) {
      console.error("Failed to load dashboard:", err);
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadStats();
  }, [loadStats]);

  // Auto-polling every 5 minutes
  useEffect(() => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    pollingRef.current = setInterval(() => {
      loadStats(true);
    }, POLL_INTERVAL);
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [loadStats]);

  const cards: KpiCard[] = stats
    ? [
        {
          label: "People",
          value: stats.people_count,
          icon: Users,
          color: "text-blue-600",
        },
        {
          label: "Companies",
          value: stats.companies_count,
          icon: Building2,
          color: "text-violet-600",
        },
        {
          label: "Active Campaigns",
          value: stats.active_campaigns,
          icon: Mail,
          color: "text-orange-600",
        },
        {
          label: "Emails Sent",
          value: stats.total_sent,
          icon: Send,
          color: "text-sky-600",
        },
        {
          label: "Opened",
          value: stats.total_opened,
          sub: pct(stats.total_opened, stats.total_sent),
          icon: Eye,
          color: "text-amber-600",
        },
        {
          label: "Replies",
          value: stats.total_replied,
          sub: pct(stats.total_replied, stats.total_sent),
          icon: MessageSquareReply,
          color: "text-green-600",
        },
      ]
    : [];

  const chartData = stats?.chart_data.map((d) => ({
    ...d,
    date: fmtDate(d.date),
  })) ?? [];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Platform overview
          {lastRefresh && (
            <span className="ml-2 inline-flex items-center gap-1">
              <Clock className="h-3 w-3" />
              Updated {lastRefresh.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" })}
            </span>
          )}
        </p>
      </div>

      {/* KPI Cards */}
      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-8">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="rounded-lg border bg-card p-5 animate-pulse">
              <div className="h-4 w-24 bg-muted rounded mb-3" />
              <div className="h-8 w-16 bg-muted rounded" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-8">
          {cards.map(({ label, value, sub, icon: Icon, color }) => (
            <div key={label} className="rounded-lg border bg-card p-5">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm text-muted-foreground">{label}</p>
                <Icon className={`h-4 w-4 ${color}`} />
              </div>
              <p className="text-3xl font-bold">{value.toLocaleString()}</p>
              {sub && <p className="text-xs text-muted-foreground mt-1">{sub} rate</p>}
            </div>
          ))}
        </div>
      )}

      {/* Line Chart */}
      <div className="rounded-lg border bg-card p-5">
        <h2 className="text-sm font-semibold mb-4">Email Activity — Last 30 days</h2>
        {loading ? (
          <div className="h-64 bg-muted animate-pulse rounded" />
        ) : chartData.length === 0 ? (
          <div className="h-64 flex items-center justify-center text-muted-foreground text-sm">
            No data available yet
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                allowDecimals={false}
              />
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
              <Line
                type="monotone"
                dataKey="sent"
                name="Sent"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
              />
              <Line
                type="monotone"
                dataKey="replies"
                name="Replies"
                stroke="#22c55e"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
