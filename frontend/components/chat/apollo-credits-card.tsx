"use client";

import { Zap } from "lucide-react";

interface Props {
  creditsUsed: number | null;
}

export function ApolloCreditsCard({ creditsUsed }: Props) {
  const planLimit = 10000; // Basic plan monthly limit

  if (creditsUsed === null) {
    return null; // Don't show until first search
  }

  // Estimate remaining based on last known usage
  // This is a rough estimate since we don't track total monthly usage
  const estimatedRemaining = planLimit - creditsUsed;
  const percentage = (estimatedRemaining / planLimit) * 100;

  const color = percentage > 50 ? "text-green-600" :
                percentage > 20 ? "text-amber-600" :
                "text-red-600";

  return (
    <div className="rounded-lg border bg-card p-3 w-40">
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs text-muted-foreground">Ultima ricerca</p>
        <Zap className={`h-3 w-3 ${color}`} />
      </div>
      <p className="text-xl font-bold">
        {creditsUsed.toLocaleString()}
      </p>
      <p className="text-[10px] text-muted-foreground">
        crediti usati
      </p>
    </div>
  );
}
