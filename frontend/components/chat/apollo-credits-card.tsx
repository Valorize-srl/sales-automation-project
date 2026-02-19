"use client";

import { useEffect, useState } from "react";
import { Zap } from "lucide-react";

interface Props {
  creditsUsed: number | null;
}

interface MonthlyUsage {
  month: string;
  total: number;
}

const MONTHLY_LIMIT = 10000;
const STORAGE_KEY = "apollo_credits_monthly";

export function ApolloCreditsCard({ creditsUsed }: Props) {
  const [monthlyConsumed, setMonthlyConsumed] = useState(0);
  const [loading, setLoading] = useState(true);

  // Get current month in YYYY-MM format
  const getCurrentMonth = () => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  };

  // Load monthly usage from localStorage
  useEffect(() => {
    const currentMonth = getCurrentMonth();
    const stored = localStorage.getItem(STORAGE_KEY);

    if (stored) {
      try {
        const data: MonthlyUsage = JSON.parse(stored);

        // Check if it's the same month
        if (data.month === currentMonth) {
          setMonthlyConsumed(data.total);
        } else {
          // New month - reset counter
          const newData: MonthlyUsage = { month: currentMonth, total: 0 };
          localStorage.setItem(STORAGE_KEY, JSON.stringify(newData));
          setMonthlyConsumed(0);
        }
      } catch (e) {
        console.error("Error parsing Apollo credits data:", e);
        setMonthlyConsumed(0);
      }
    } else {
      // First time - initialize
      const newData: MonthlyUsage = { month: currentMonth, total: 0 };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newData));
      setMonthlyConsumed(0);
    }

    setLoading(false);
  }, []);

  // Update total when new credits are consumed
  useEffect(() => {
    if (creditsUsed !== null && creditsUsed > 0) {
      const currentMonth = getCurrentMonth();
      const newTotal = monthlyConsumed + creditsUsed;

      const data: MonthlyUsage = { month: currentMonth, total: newTotal };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      setMonthlyConsumed(newTotal);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [creditsUsed]);

  const remaining = MONTHLY_LIMIT - monthlyConsumed;
  const percentage = (remaining / MONTHLY_LIMIT) * 100;

  const color =
    percentage > 50
      ? "text-green-600"
      : percentage > 20
        ? "text-amber-600"
        : "text-red-600";

  if (loading) {
    return (
      <div className="rounded-lg border bg-card p-3 animate-pulse w-40">
        <div className="h-3 w-16 bg-muted rounded mb-2" />
        <div className="h-6 w-20 bg-muted rounded" />
      </div>
    );
  }

  return (
    <div
      className="rounded-lg border bg-card p-3 w-40"
      title={`Consumati questo mese: ${monthlyConsumed.toLocaleString()}`}
    >
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs text-muted-foreground">Crediti Apollo</p>
        <Zap className={`h-3 w-3 ${color}`} />
      </div>
      <p className="text-xl font-bold">{remaining.toLocaleString()}</p>
      <p className="text-[10px] text-muted-foreground">
        di {MONTHLY_LIMIT.toLocaleString()} / mese
      </p>
    </div>
  );
}
