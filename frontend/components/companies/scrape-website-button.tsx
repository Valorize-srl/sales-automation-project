"use client";

import { useState } from "react";
import { Globe, Loader2, Mail, Linkedin, CheckCircle, AlertCircle, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { WebsiteScrapeResult } from "@/types";

interface ScrapeWebsiteButtonProps {
  websiteUrl: string;
  companyId: number;
  currentEmail?: string | null;
  currentLinkedin?: string | null;
  onSaved?: () => void;
}

export function ScrapeWebsiteButton({
  websiteUrl,
  companyId,
  currentEmail,
  currentLinkedin,
  onSaved,
}: ScrapeWebsiteButtonProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<WebsiteScrapeResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleScrape = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setSaved(false);
    try {
      const data = await api.scrapeWebsite(websiteUrl);
      if (data.error) {
        setError(data.error);
      } else {
        setResult(data);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Errore durante lo scraping");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!result) return;
    setSaving(true);
    try {
      const updates: Record<string, string | null> = {};
      if (result.emails.length > 0 && !currentEmail) {
        updates.email = result.emails[0];
      }
      if (result.linkedin_url && !currentLinkedin) {
        updates.linkedin_url = result.linkedin_url;
      }
      if (Object.keys(updates).length > 0) {
        await api.updateCompany(companyId, updates);
        setSaved(true);
        onSaved?.();
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Errore durante il salvataggio");
    } finally {
      setSaving(false);
    }
  };

  const hasNewEmail = result && result.emails.length > 0 && !currentEmail;
  const hasNewLinkedin = result && result.linkedin_url && !currentLinkedin;
  const hasNewData = hasNewEmail || hasNewLinkedin;

  return (
    <div className="flex flex-col gap-2">
      <Button
        size="sm"
        variant="outline"
        onClick={handleScrape}
        disabled={loading}
        className="w-fit"
      >
        {loading ? (
          <>
            <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
            Scraping...
          </>
        ) : (
          <>
            <Globe className="h-3.5 w-3.5 mr-1.5" />
            Scrapa sito
          </>
        )}
      </Button>

      {error && (
        <div className="flex items-center gap-1.5 text-xs text-red-600 dark:text-red-400">
          <AlertCircle className="h-3 w-3 shrink-0" />
          {error}
        </div>
      )}

      {result && !error && (
        <div className="rounded-md border bg-muted/40 p-2.5 space-y-2 text-xs">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Globe className="h-3 w-3" />
            <span>{result.pages_visited} pagine visitate</span>
          </div>

          {result.emails.length > 0 ? (
            <div className="space-y-1">
              <div className="flex items-center gap-1 font-medium">
                <Mail className="h-3 w-3 text-blue-500" />
                Email trovate
              </div>
              <div className="flex flex-wrap gap-1">
                {result.emails.map((email) => (
                  <Badge key={email} variant="secondary" className="text-[10px]">
                    {email}
                  </Badge>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-1 text-muted-foreground">
              <Mail className="h-3 w-3" />
              Nessuna email trovata
            </div>
          )}

          {result.linkedin_url ? (
            <div className="flex items-center gap-1.5">
              <Linkedin className="h-3 w-3 text-[#0A66C2]" />
              <a
                href={result.linkedin_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#0A66C2] hover:underline truncate max-w-[280px]"
              >
                {result.linkedin_url}
              </a>
            </div>
          ) : (
            <div className="flex items-center gap-1 text-muted-foreground">
              <Linkedin className="h-3 w-3" />
              LinkedIn non trovato
            </div>
          )}

          {saved ? (
            <div className="flex items-center gap-1.5 text-green-600 dark:text-green-400 font-medium">
              <CheckCircle className="h-3 w-3" />
              Salvato nell&apos;azienda
            </div>
          ) : hasNewData ? (
            <Button
              size="sm"
              variant="default"
              className="h-7 text-xs w-fit"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? (
                <Loader2 className="h-3 w-3 animate-spin mr-1" />
              ) : (
                <Save className="h-3 w-3 mr-1" />
              )}
              Salva nella scheda
            </Button>
          ) : (
            <p className="text-muted-foreground italic">
              Nessun dato nuovo da salvare
            </p>
          )}
        </div>
      )}
    </div>
  );
}
