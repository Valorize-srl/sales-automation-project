"use client";

import { useState } from "react";
import { Search, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface EnrichButtonProps {
  companyId: number;
  onEnrichComplete?: () => void;
}

export function EnrichButton({
  companyId,
  onEnrichComplete,
}: EnrichButtonProps) {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const handleEnrich = async () => {
    setLoading(true);
    setMessage(null);

    try {
      const result = await api.enrichCompany(companyId);

      if (result.status === "completed") {
        setMessage({
          type: "success",
          text: `Found ${result.emails_found.length} email(s)`,
        });
        // Wait a bit to show success message before refreshing
        setTimeout(() => {
          onEnrichComplete?.();
        }, 1000);
      } else if (result.status === "failed") {
        setMessage({
          type: "error",
          text: result.error || "Failed to enrich company",
        });
      } else if (result.status === "skipped") {
        setMessage({
          type: "error",
          text: result.error || "Company skipped",
        });
      }
    } catch (error) {
      console.error("Enrichment error:", error);
      setMessage({
        type: "error",
        text: "Failed to enrich company",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <Button
        size="sm"
        variant="outline"
        onClick={handleEnrich}
        disabled={loading}
      >
        {loading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
            Enriching...
          </>
        ) : (
          <>
            <Search className="h-4 w-4 mr-2" />
            Find Emails
          </>
        )}
      </Button>

      {message && (
        <span
          className={`text-xs ${
            message.type === "success"
              ? "text-green-600 dark:text-green-400"
              : "text-red-600 dark:text-red-400"
          }`}
        >
          {message.text}
        </span>
      )}
    </div>
  );
}
