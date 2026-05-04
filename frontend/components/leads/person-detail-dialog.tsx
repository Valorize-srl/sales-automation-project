"use client";

import { useEffect, useState } from "react";
import {
  User, Mail, Phone, Linkedin, MapPin, Calendar, Building2,
  Loader2, Megaphone, Trophy, FileText, Briefcase,
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
import { Person, CampaignSummary, PersonUpdate } from "@/types";

interface PersonDetailDialogProps {
  person: Person | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCompanyClick?: (companyId: number) => void;
  onUpdated?: () => void;
}

export function PersonDetailDialog({ person, open, onOpenChange, onCompanyClick, onUpdated }: PersonDetailDialogProps) {
  const [loading, setLoading] = useState(false);
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);
  const [current, setCurrent] = useState<Person | null>(null);

  useEffect(() => {
    if (open && person) {
      setCurrent(person);
      setLoading(true);
      api.getPersonCampaigns(person.id)
        .then((data) => setCampaigns(data.campaigns))
        .catch((err) => console.error("Failed to load person campaigns:", err))
        .finally(() => setLoading(false));
    } else {
      setCampaigns([]);
      setCurrent(null);
    }
  }, [open, person]);

  if (!current) return null;

  const saveField = async (field: keyof PersonUpdate, value: string) => {
    const updated = await api.updatePerson(current.id, { [field]: value || null });
    setCurrent(updated);
    onUpdated?.();
  };

  const fullName = `${current.first_name} ${current.last_name}`;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <User className="h-5 w-5 text-primary" />
            {fullName}
            <span className="ml-1 text-[10px] font-mono text-muted-foreground">contact_id={current.id}</span>
          </DialogTitle>
          <div className="flex items-center gap-2 text-sm text-muted-foreground flex-wrap">
            {current.company_name && (
              <>
                <span className="flex items-center gap-1">
                  <Building2 className="h-3 w-3" />
                  {current.company_id ? (
                    <button
                      className="text-primary hover:underline"
                      onClick={() => onCompanyClick?.(current.company_id!)}
                    >
                      {current.company_name}
                    </button>
                  ) : (
                    current.company_name
                  )}
                </span>
                <span>&middot;</span>
              </>
            )}
            <span className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              {new Date(current.created_at).toLocaleDateString()}
            </span>
            {current.converted_at && (
              <Badge variant="default" className="text-[10px] bg-emerald-500 ml-1">
                <Trophy className="h-3 w-3 mr-0.5" /> Converted
              </Badge>
            )}
          </div>
        </DialogHeader>

        <div className="space-y-4 pt-2">
          {/* Editable Fields */}
          <section>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <User className="h-3.5 w-3.5" /> Anagrafica
            </h3>
            <div className="space-y-0.5">
              <EditableField label="Nome" value={current.first_name} onSave={(v) => saveField("first_name", v)} placeholder="Nome" />
              <EditableField label="Cognome" value={current.last_name} onSave={(v) => saveField("last_name", v)} placeholder="Cognome" />
              <EditableField label="Email lavoro" value={current.email} onSave={(v) => saveField("email", v)} placeholder="email@esempio.com" icon={<Mail className="h-3 w-3 text-muted-foreground" />} />
              <EditableField label="Telefono" value={current.phone} onSave={(v) => saveField("phone", v)} placeholder="+39 ..." icon={<Phone className="h-3 w-3 text-muted-foreground" />} />
              <EditableField label="LinkedIn" value={current.linkedin_url} onSave={(v) => saveField("linkedin_url", v)} type="url" placeholder="https://linkedin.com/in/..." icon={<Linkedin className="h-3 w-3 text-muted-foreground" />} />
            </div>
          </section>

          <Separator />

          {/* Professional */}
          <section>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Briefcase className="h-3.5 w-3.5" /> Professionale
            </h3>
            <div className="space-y-0.5">
              <EditableField label="Ruolo/Titolo" value={current.title} onSave={(v) => saveField("title", v)} placeholder="es. CEO, CTO, Sales Manager" />
              <EditableField label="Azienda" value={current.company_name} onSave={(v) => saveField("company_name", v)} placeholder="Nome azienda" icon={<Building2 className="h-3 w-3 text-muted-foreground" />} />
              <EditableField label="Settore" value={current.industry} onSave={(v) => saveField("industry", v)} placeholder="es. Technology" />
              <EditableField label="Location" value={current.location} onSave={(v) => saveField("location", v)} placeholder="es. Milano, Italia" icon={<MapPin className="h-3 w-3 text-muted-foreground" />} />
              <EditableField label="Client/Progetto" value={current.client_tag} onSave={(v) => saveField("client_tag", v)} placeholder="es. cliente_xyz" />
            </div>

            {/* Tags (read-only) */}
            {current.tags && current.tags.length > 0 && (
              <div className="flex items-start gap-1.5 mt-1 px-1">
                <span className="text-muted-foreground text-xs w-28 shrink-0 pt-0.5">Tags</span>
                <div className="flex flex-wrap gap-1">
                  {current.tags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="text-[10px]">{tag}</Badge>
                  ))}
                </div>
              </div>
            )}

            {/* Conversion info */}
            {current.converted_at && (
              <div className="flex items-center gap-2 text-xs mt-2 px-1">
                <Trophy className="h-3 w-3 text-emerald-500" />
                <span className="text-muted-foreground">Convertito il:</span>
                <span>{new Date(current.converted_at).toLocaleDateString()}</span>
              </div>
            )}
          </section>

          <Separator />

          {/* Notes */}
          <section>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <FileText className="h-3.5 w-3.5" /> Note
            </h3>
            <EditableField label="Note" value={current.notes} onSave={(v) => saveField("notes", v)} type="textarea" placeholder="Aggiungi note sul contatto..." />
          </section>

          <Separator />

          <Separator />

          <ActivityTimeline targetType="contact" targetId={current.id} />

          <Separator />

          {/* Campaigns Section (read-only) */}
          <section>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Megaphone className="h-3.5 w-3.5" /> Campagne ({loading ? "..." : campaigns.length})
            </h3>
            {loading ? (
              <div className="flex items-center gap-2 py-3 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Caricamento...
              </div>
            ) : campaigns.length === 0 ? (
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
      </DialogContent>
    </Dialog>
  );
}
