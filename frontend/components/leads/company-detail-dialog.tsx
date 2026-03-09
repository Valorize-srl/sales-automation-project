"use client";

import { useEffect, useState } from "react";
import {
  Building2, Mail, Phone, Globe, Linkedin, MapPin, Tag, Calendar,
  Users, ExternalLink, Loader2, Megaphone, Sparkles, X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { Company, CompanyDetailResponse, PersonSummary, CampaignSummary } from "@/types";

interface CompanyDetailDialogProps {
  company: Company | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPersonClick?: (personId: number) => void;
}

export function CompanyDetailDialog({ company, open, onOpenChange, onPersonClick }: CompanyDetailDialogProps) {
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState<CompanyDetailResponse | null>(null);

  useEffect(() => {
    if (open && company) {
      setLoading(true);
      api.getCompanyDetail(company.id)
        .then(setDetail)
        .catch((err) => console.error("Failed to load company detail:", err))
        .finally(() => setLoading(false));
    } else {
      setDetail(null);
    }
  }, [open, company]);

  if (!company) return null;

  const people = detail?.people ?? [];
  const campaigns = detail?.campaigns ?? [];
  const c = detail?.company ?? company;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[640px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-primary" />
            {c.name}
          </DialogTitle>
          <div className="flex items-center gap-2 text-sm text-muted-foreground flex-wrap">
            {c.industry && <span>{c.industry}</span>}
            {c.industry && c.location && <span>&middot;</span>}
            {c.location && (
              <span className="flex items-center gap-1">
                <MapPin className="h-3 w-3" /> {c.location}
              </span>
            )}
            {(c.industry || c.location) && <span>&middot;</span>}
            <span className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              {new Date(c.created_at).toLocaleDateString()}
            </span>
          </div>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-5 pt-2">
            {/* Contacts Section */}
            <section>
              <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
                <Mail className="h-4 w-4" /> Contatti
              </h3>
              <div className="grid grid-cols-1 gap-1.5 text-sm">
                {c.email && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground w-28 shrink-0">Email principale:</span>
                    <a href={`mailto:${c.email}`} className="text-primary hover:underline">{c.email}</a>
                  </div>
                )}
                {c.generic_emails && c.generic_emails.length > 0 && (
                  <div className="flex items-start gap-2">
                    <span className="text-muted-foreground w-28 shrink-0">Email aggiuntive:</span>
                    <div className="flex flex-wrap gap-1">
                      {c.generic_emails.map((email) => (
                        <Badge key={email} variant="secondary" className="text-xs">{email}</Badge>
                      ))}
                    </div>
                  </div>
                )}
                {c.phone && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground w-28 shrink-0">Telefono:</span>
                    <span className="flex items-center gap-1"><Phone className="h-3 w-3" /> {c.phone}</span>
                  </div>
                )}
                {c.website && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground w-28 shrink-0">Sito web:</span>
                    <a href={c.website.startsWith("http") ? c.website : `https://${c.website}`} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline flex items-center gap-1">
                      <Globe className="h-3 w-3" /> {c.website}
                    </a>
                  </div>
                )}
                {c.linkedin_url && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground w-28 shrink-0">LinkedIn:</span>
                    <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline flex items-center gap-1">
                      <Linkedin className="h-3 w-3" /> LinkedIn Page
                    </a>
                  </div>
                )}
                {!c.email && !c.phone && !c.website && !c.linkedin_url && (
                  <p className="text-muted-foreground text-xs italic">Nessun contatto disponibile</p>
                )}
              </div>
            </section>

            <Separator />

            {/* Details Section */}
            <section>
              <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
                <Tag className="h-4 w-4" /> Dettagli
              </h3>
              <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm">
                <div>
                  <span className="text-muted-foreground">Settore:</span>{" "}
                  <span>{c.industry || "—"}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Client/Progetto:</span>{" "}
                  <span>{c.client_tag || "—"}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Dominio email:</span>{" "}
                  <span>{c.email_domain || "—"}</span>
                </div>
                {c.signals && (
                  <div className="col-span-2">
                    <span className="text-muted-foreground">Segnali:</span>{" "}
                    <span>{c.signals}</span>
                  </div>
                )}
              </div>
              {/* Enrichment info */}
              {c.enrichment_status && (
                <div className="mt-2 flex items-center gap-2 text-xs">
                  <Sparkles className="h-3 w-3 text-blue-500" />
                  <span className="text-muted-foreground">Enrichment:</span>
                  <Badge variant="outline" className="text-[10px]">{c.enrichment_source || "—"}</Badge>
                  {c.enrichment_date && (
                    <span className="text-muted-foreground">{new Date(c.enrichment_date).toLocaleDateString()}</span>
                  )}
                  <Badge
                    variant={c.enrichment_status === "completed" ? "default" : "secondary"}
                    className="text-[10px]"
                  >
                    {c.enrichment_status}
                  </Badge>
                </div>
              )}
            </section>

            <Separator />

            {/* People Section */}
            <section>
              <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
                <Users className="h-4 w-4" /> Persone ({people.length})
              </h3>
              {people.length === 0 ? (
                <p className="text-muted-foreground text-xs italic">Nessuna persona associata</p>
              ) : (
                <div className="space-y-1.5 max-h-[200px] overflow-y-auto">
                  {people.map((p) => (
                    <div
                      key={p.id}
                      className="flex items-center justify-between p-2 rounded-md border text-sm hover:bg-accent/50 cursor-pointer"
                      onClick={() => onPersonClick?.(p.id)}
                    >
                      <div className="flex flex-col">
                        <span className="font-medium">
                          {p.first_name} {p.last_name}
                          {p.title && <span className="text-muted-foreground font-normal"> &middot; {p.title}</span>}
                        </span>
                        <span className="text-xs text-muted-foreground">{p.email}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {p.converted_at && (
                          <Badge variant="default" className="text-[10px] bg-emerald-500">Converted</Badge>
                        )}
                        {p.linkedin_url && (
                          <a href={p.linkedin_url} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}>
                            <ExternalLink className="h-3 w-3 text-muted-foreground hover:text-primary" />
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <Separator />

            {/* Campaigns Section */}
            <section>
              <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
                <Megaphone className="h-4 w-4" /> Campagne ({campaigns.length})
              </h3>
              {campaigns.length === 0 ? (
                <p className="text-muted-foreground text-xs italic">Nessuna campagna associata</p>
              ) : (
                <div className="space-y-1.5">
                  {campaigns.map((camp) => (
                    <div key={camp.id} className="flex items-center justify-between p-2 rounded-md border text-sm">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{camp.name}</span>
                        <Badge
                          variant={camp.status === "active" ? "default" : "secondary"}
                          className="text-[10px]"
                        >
                          {camp.status}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground">
                        <span>{camp.total_sent} sent</span>
                        <span>{camp.total_opened} opened</span>
                        <span>{camp.total_replied} replied</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
