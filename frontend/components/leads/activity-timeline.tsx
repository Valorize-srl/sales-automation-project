"use client";

import { useEffect, useState } from "react";
import { Activity, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

interface Props {
  targetType: "account" | "contact";
  targetId: number;
  refreshKey?: number;
}

interface Entry {
  id: number;
  action: string;
  payload: Record<string, unknown> | null;
  actor: string | null;
  created_at: string;
}

const ACTION_LABEL: Record<string, string> = {
  field_updated: "Campo aggiornato",
  custom_field_set: "Campo custom impostato",
  custom_field_removed: "Campo custom rimosso",
  scored: "Score con ICP",
  added_to_list: "Aggiunto a lista",
  removed_from_list: "Rimosso da lista",
  email_verified: "Email verificata",
  phone_verified: "Telefono verificato",
  converted: "Convertito",
  unconverted: "Non più convertito",
  deleted: "Eliminato",
};

function summarisePayload(action: string, p: Record<string, unknown> | null): string {
  if (!p) return "";
  if (action === "field_updated") {
    const keys = Object.keys(p);
    if (keys.length === 1) return `${keys[0]}`;
    return `${keys.slice(0, 3).join(", ")}${keys.length > 3 ? `, +${keys.length - 3}` : ""}`;
  }
  if (action === "scored") return `tier ${p.tier ?? "?"} · score ${p.icp_score ?? "?"}`;
  if (action === "added_to_list" || action === "removed_from_list") return `${p.list_name ?? `#${p.list_id}`}`;
  if (action === "email_verified" || action === "phone_verified") return `via ${p.source ?? "?"}`;
  if (action === "custom_field_set") return `${p.key}: ${String(p.to ?? "")}`;
  if (action === "custom_field_removed") return `${p.key}`;
  return "";
}

function formatRelative(iso: string): string {
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "ora";
  if (diff < 3600) return `${Math.floor(diff / 60)}m fa`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h fa`;
  if (diff < 86400 * 14) return `${Math.floor(diff / 86400)}g fa`;
  return d.toLocaleDateString("it-IT");
}

export function ActivityTimeline({ targetType, targetId, refreshKey }: Props) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.listActivity({ target_type: targetType, target_id: targetId, page_size: 50 })
      .then((r) => { if (!cancelled) setEntries(r.activities); })
      .catch((e) => console.error("Failed to load activity", e))
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [targetType, targetId, refreshKey]);

  return (
    <section>
      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
        <Activity className="h-3.5 w-3.5" /> Timeline ({loading ? "…" : entries.length})
      </h3>
      {loading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground py-2">
          <Loader2 className="h-3 w-3 animate-spin" /> Caricamento…
        </div>
      ) : entries.length === 0 ? (
        <p className="text-muted-foreground text-xs italic px-1">Nessuna attività registrata.</p>
      ) : (
        <ul className="space-y-1.5 max-h-[260px] overflow-y-auto pr-1">
          {entries.map((e) => (
            <li key={e.id} className="flex items-start gap-2 text-xs">
              <span className="h-1.5 w-1.5 mt-1.5 rounded-full bg-primary/60 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-2">
                  <span className="font-medium">{ACTION_LABEL[e.action] ?? e.action}</span>
                  <span className="text-muted-foreground text-[10px]">{formatRelative(e.created_at)}</span>
                  {e.actor && <span className="text-muted-foreground text-[10px]">· {e.actor}</span>}
                </div>
                {summarisePayload(e.action, e.payload) && (
                  <p className="text-muted-foreground truncate" title={JSON.stringify(e.payload)}>
                    {summarisePayload(e.action, e.payload)}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
