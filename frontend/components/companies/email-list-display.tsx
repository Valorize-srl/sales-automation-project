"use client";

import { Mail, Globe } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface EmailListDisplayProps {
  primaryEmail?: string;
  genericEmails?: string[];
  enrichmentSource?: string;
  enrichmentDate?: string;
}

export function EmailListDisplay({
  primaryEmail,
  genericEmails,
  enrichmentSource,
  enrichmentDate,
}: EmailListDisplayProps) {
  // Show primary email if present
  const hasPrimary = !!primaryEmail;
  const hasGeneric = genericEmails && genericEmails.length > 0;

  if (!hasPrimary && !hasGeneric) {
    return <span className="text-muted-foreground">—</span>;
  }

  return (
    <div className="space-y-1">
      {hasPrimary && (
        <div className="flex items-center gap-2">
          <Mail className="h-3 w-3" />
          <span className="text-sm">{primaryEmail}</span>
          {enrichmentSource === "apollo" && (
            <Badge variant="secondary" className="text-xs">
              Apollo
            </Badge>
          )}
        </div>
      )}

      {hasGeneric && (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">Generic contacts:</p>
          {genericEmails.map((email) => (
            <div key={email} className="flex items-center gap-2 pl-4">
              <Globe className="h-3 w-3 text-muted-foreground" />
              <span className="text-sm">{email}</span>
            </div>
          ))}
          {(enrichmentSource === "web_scrape" ||
            enrichmentSource === "both") && (
            <Badge variant="outline" className="text-xs ml-4">
              Web Scraped
            </Badge>
          )}
        </div>
      )}
    </div>
  );
}
