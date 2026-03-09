"use client";

import { useEffect, useState } from "react";
import {
  User, Mail, Phone, Linkedin, MapPin, Tag, Calendar, Building2,
  ExternalLink, Loader2, Megaphone, Trophy, Pencil, Sparkles,
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
import { Person, CampaignSummary } from "@/types";

interface PersonDetailDialogProps {
  person: Person | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCompanyClick?: (companyId: number) => void;
  onEdit?: (person: Person) => void;
}

export function PersonDetailDialog({ person, open, onOpenChange, onCompanyClick, onEdit }: PersonDetailDialogProps) {
  const [loading, setLoading] = useState(false);
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);

  useEffect(() => {
    if (open && person) {
      setLoading(true);
      api.getPersonCampaigns(person.id)
        .then((data) => setCampaigns(data.campaigns))
        .catch((err) => console.error("Failed to load person campaigns:", err))
        .finally(() => setLoading(false));
    } else {
      setCampaigns([]);
    }
  }, [open, person]);

  if (!person) return null;

  const fullName = `${person.first_name} ${person.last_name}`;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <User className="h-5 w-5 text-primary" />
            {fullName}
          </DialogTitle>
          <div className="flex items-center gap-2 text-sm text-muted-foreground flex-wrap">
            {person.company_name && (
              <>
                <span className="flex items-center gap-1">
                  <Building2 className="h-3 w-3" />
                  {person.company_id ? (
                    <button
                      className="text-primary hover:underline"
                      onClick={() => onCompanyClick?.(person.company_id!)}
                    >
                      {person.company_name}
                    </button>
                  ) : (
                    person.company_name
                  )}
                </span>
                <span>&middot;</span>
              </>
            )}
            {person.location && (
              <>
                <span className="flex items-center gap-1">
                  <MapPin className="h-3 w-3" /> {person.location}
                </span>
                <span>&middot;</span>
              </>
            )}
            <span className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              {new Date(person.created_at).toLocaleDateString()}
            </span>
            {person.converted_at && (
              <Badge variant="default" className="text-[10px] bg-emerald-500 ml-1">
                <Trophy className="h-3 w-3 mr-0.5" /> Converted
              </Badge>
            )}
          </div>
        </DialogHeader>

        <div className="space-y-5 pt-2">
          {/* Contacts Section */}
          <section>
            <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
              <Mail className="h-4 w-4" /> Contatti
            </h3>
            <div className="grid grid-cols-1 gap-1.5 text-sm">
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground w-24 shrink-0">Email:</span>
                <a href={`mailto:${person.email}`} className="text-primary hover:underline">{person.email}</a>
              </div>
              {person.phone && (
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground w-24 shrink-0">Telefono:</span>
                  <span className="flex items-center gap-1"><Phone className="h-3 w-3" /> {person.phone}</span>
                </div>
              )}
              {person.linkedin_url && (
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground w-24 shrink-0">LinkedIn:</span>
                  <a href={person.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline flex items-center gap-1">
                    <Linkedin className="h-3 w-3" /> Profilo LinkedIn
                  </a>
                </div>
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
                <span className="text-muted-foreground">Azienda:</span>{" "}
                {person.company_id ? (
                  <button
                    className="text-primary hover:underline"
                    onClick={() => onCompanyClick?.(person.company_id!)}
                  >
                    {person.company_name || "—"}
                  </button>
                ) : (
                  <span>{person.company_name || "—"}</span>
                )}
              </div>
              <div>
                <span className="text-muted-foreground">Settore:</span>{" "}
                <span>{person.industry || "—"}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Location:</span>{" "}
                <span>{person.location || "—"}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Client/Progetto:</span>{" "}
                <span>{person.client_tag || "—"}</span>
              </div>
            </div>
            {/* Tags */}
            {person.tags && person.tags.length > 0 && (
              <div className="mt-2 flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Tags:</span>
                <div className="flex flex-wrap gap-1">
                  {person.tags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="text-[10px]">{tag}</Badge>
                  ))}
                </div>
              </div>
            )}
            {/* Conversion info */}
            {person.converted_at && (
              <div className="mt-2 flex items-center gap-2 text-xs">
                <Trophy className="h-3 w-3 text-emerald-500" />
                <span className="text-muted-foreground">Convertito il:</span>
                <span>{new Date(person.converted_at).toLocaleDateString()}</span>
              </div>
            )}
          </section>

          <Separator />

          {/* Campaigns Section */}
          <section>
            <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
              <Megaphone className="h-4 w-4" /> Campagne ({loading ? "..." : campaigns.length})
            </h3>
            {loading ? (
              <div className="flex items-center gap-2 py-3 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Caricamento...
              </div>
            ) : campaigns.length === 0 ? (
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

          {/* Edit Button */}
          {onEdit && (
            <>
              <Separator />
              <div className="flex justify-end">
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1.5"
                  onClick={() => {
                    onOpenChange(false);
                    onEdit(person);
                  }}
                >
                  <Pencil className="h-3.5 w-3.5" /> Modifica
                </Button>
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
