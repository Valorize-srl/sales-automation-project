"use client";

import { useEffect, useState } from "react";
import {
  Building2, Mail, Phone, Globe, Linkedin, MapPin, Calendar,
  Users, ExternalLink, Loader2, Megaphone, Sparkles, FileText, Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EditableField } from "@/components/ui/editable-field";
import { api } from "@/lib/api";
import { ActivityTimeline } from "@/components/leads/activity-timeline";
import { Company, CompanyDetailResponse, CompanyUpdate } from "@/types";

interface CompanyDetailDialogProps {
  company: Company | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPersonClick?: (personId: number) => void;
  onUpdated?: () => void;
}

export function CompanyDetailDialog({ company, open, onOpenChange, onPersonClick, onUpdated }: CompanyDetailDialogProps) {
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

  const saveField = async (field: keyof CompanyUpdate, value: string) => {
    const updated = await api.updateCompany(c.id, { [field]: value || null });
    setDetail((prev) => prev ? { ...prev, company: { ...prev.company, ...updated } } : prev);
    onUpdated?.();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[640px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-primary" />
            {c.name}
            <span className="ml-1 text-[10px] font-mono text-muted-foreground">account_id={c.id}</span>
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
          <div className="space-y-4 pt-2">
            {/* Editable Fields */}
            <section>
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Building2 className="h-3.5 w-3.5" /> Anagrafica
              </h3>
              <div className="space-y-0.5">
                <EditableField label="Nome" value={c.name} onSave={(v) => saveField("name", v)} placeholder="Nome azienda" />
                <EditableField label="Email" value={c.email} onSave={(v) => saveField("email", v)} placeholder="email@azienda.com" icon={<Mail className="h-3 w-3 text-muted-foreground" />} />
                <EditableField label="Telefono" value={c.phone} onSave={(v) => saveField("phone", v)} placeholder="+39 ..." icon={<Phone className="h-3 w-3 text-muted-foreground" />} />
                <EditableField label="Sito web" value={c.website} onSave={(v) => saveField("website", v)} type="url" placeholder="https://..." icon={<Globe className="h-3 w-3 text-muted-foreground" />} />
                <EditableField label="LinkedIn" value={c.linkedin_url} onSave={(v) => saveField("linkedin_url", v)} type="url" placeholder="https://linkedin.com/..." icon={<Linkedin className="h-3 w-3 text-muted-foreground" />} />
                <EditableField label="Settore" value={c.industry} onSave={(v) => saveField("industry", v)} placeholder="es. Technology" />
                <EditableField label="Location" value={c.location} onSave={(v) => saveField("location", v)} placeholder="es. Milano, Italia" icon={<MapPin className="h-3 w-3 text-muted-foreground" />} />
                <EditableField label="Client/Progetto" value={c.client_tag} onSave={(v) => saveField("client_tag", v)} placeholder="es. cliente_xyz" />
              </div>

              {/* Generic emails (read-only, from enrichment) */}
              {c.generic_emails && c.generic_emails.length > 0 && (
                <div className="flex items-start gap-1.5 mt-1 px-1">
                  <span className="text-muted-foreground text-xs w-28 shrink-0 pt-0.5">Email aggiuntive</span>
                  <div className="flex flex-wrap gap-1">
                    {c.generic_emails.map((email) => (
                      <Badge key={email} variant="secondary" className="text-[10px]">{email}</Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Enrichment info (read-only) */}
              {c.enrichment_status && (
                <div className="flex items-center gap-2 text-xs mt-2 px-1">
                  <Sparkles className="h-3 w-3 text-blue-500" />
                  <span className="text-muted-foreground">Enrichment:</span>
                  <Badge variant="outline" className="text-[10px]">{c.enrichment_source || "—"}</Badge>
                  {c.enrichment_date && (
                    <span className="text-muted-foreground">{new Date(c.enrichment_date).toLocaleDateString()}</span>
                  )}
                  <Badge variant={c.enrichment_status === "completed" ? "default" : "secondary"} className="text-[10px]">
                    {c.enrichment_status}
                  </Badge>
                </div>
              )}
            </section>

            <Separator />

            {/* Signals */}
            <section>
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Zap className="h-3.5 w-3.5" /> Segnali
              </h3>
              <EditableField label="Signals" value={c.signals} onSave={(v) => saveField("signals", v)} type="textarea" placeholder="Funding, acquisizioni, news..." />
            </section>

            <Separator />

            {/* Notes */}
            <section>
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <FileText className="h-3.5 w-3.5" /> Note
              </h3>
              <EditableField label="Note" value={c.notes} onSave={(v) => saveField("notes", v)} type="textarea" placeholder="Aggiungi note sull'azienda..." />
            </section>

            <Separator />

            {/* People Section (read-only) */}
            <section>
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Users className="h-3.5 w-3.5" /> Persone ({people.length})
              </h3>
              {people.length === 0 ? (
                <p className="text-muted-foreground text-xs italic px-1">Nessuna persona associata</p>
              ) : (
                <div className="space-y-1 max-h-[200px] overflow-y-auto">
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

            <Separator />

            <ActivityTimeline targetType="account" targetId={c.id} />

            <Separator />

            {/* Campaigns Section (read-only) */}
            <section>
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Megaphone className="h-3.5 w-3.5" /> Campagne ({campaigns.length})
              </h3>
              {campaigns.length === 0 ? (
                <p className="text-muted-foreground text-xs italic px-1">Nessuna campagna associata</p>
              ) : (
                <div className="space-y-1">
                  {campaigns.map((camp) => (
                    <div key={camp.id} className="flex items-center justify-between p-2 rounded-md border text-sm">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{camp.name}</span>
                        <Badge variant={camp.status === "active" ? "default" : "secondary"} className="text-[10px]">
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
