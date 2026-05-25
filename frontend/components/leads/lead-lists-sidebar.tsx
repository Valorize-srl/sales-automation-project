"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2, Users, Tag, Loader2, Edit2, Mail, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { LeadList } from "@/types";

interface Props {
  selectedListId: number | null;
  onSelectList: (listId: number | null) => void;
  refreshKey?: number; // bump from parent to trigger reload
  /** When true, render a narrow rail with only the toggle + a dot per list.
   * Persisted state lives in the parent. */
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
}

const PRESET_COLORS = ["#10b981", "#f59e0b", "#3b82f6", "#a855f7", "#ec4899", "#ef4444", "#6366f1"];

export function LeadListsSidebar({
  selectedListId, onSelectList, refreshKey, collapsed = false, onToggleCollapsed,
}: Props) {
  const [lists, setLists] = useState<LeadList[]>([]);
  const [loading, setLoading] = useState(false);

  const reload = async () => {
    setLoading(true);
    try {
      const r = await api.listLeadLists();
      setLists(r.lists || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { reload(); }, [refreshKey]);

  const create = async () => {
    const name = prompt("Nome della nuova lista:")?.trim();
    if (!name) return;
    const color = PRESET_COLORS[Math.floor(Math.random() * PRESET_COLORS.length)];
    try {
      const ll = await api.createLeadList({ name });
      // Apply color in second call (createLeadList payload doesn't accept it)
      await api.updateLeadList(ll.id, { color });
      await reload();
      onSelectList(ll.id);
    } catch (e) {
      alert(`Errore creazione lista: ${e instanceof Error ? e.message : e}`);
    }
  };

  const renameList = async (ll: LeadList) => {
    const name = prompt("Nuovo nome:", ll.name)?.trim();
    if (!name || name === ll.name) return;
    await api.updateLeadList(ll.id, { name });
    await reload();
  };

  const deleteList = async (ll: LeadList) => {
    if (!confirm(`Eliminare la lista "${ll.name}"? (Le aziende NON vengono eliminate)`)) return;
    await api.deleteLeadList(ll.id);
    if (selectedListId === ll.id) onSelectList(null);
    await reload();
  };

  const cycleColor = async (ll: LeadList) => {
    const idx = PRESET_COLORS.indexOf(ll.color || "");
    const next = PRESET_COLORS[(idx + 1) % PRESET_COLORS.length];
    await api.updateLeadList(ll.id, { color: next });
    await reload();
  };

  if (collapsed) {
    return (
      <aside className="w-10 shrink-0 border-r bg-card/50 flex flex-col items-center py-2 gap-1">
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={onToggleCollapsed}
          title="Espandi liste"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
        <div className="h-px w-6 bg-border my-1" />
        <button
          onClick={() => onSelectList(null)}
          className={`h-7 w-7 rounded-md flex items-center justify-center transition-colors ${
            selectedListId === null ? "bg-accent text-primary" : "hover:bg-accent/50 text-muted-foreground"
          }`}
          title="All companies"
        >
          <Users className="h-3.5 w-3.5" />
        </button>
        <div className="flex-1 overflow-y-auto flex flex-col items-center gap-1 w-full">
          {lists.map((ll) => (
            <button
              key={ll.id}
              onClick={() => onSelectList(ll.id)}
              className={`h-7 w-7 rounded-md flex items-center justify-center transition-colors ${
                selectedListId === ll.id ? "bg-accent ring-2 ring-primary" : "hover:bg-accent/50"
              }`}
              title={`${ll.name} (${ll.companies_count})`}
            >
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: ll.color || "#9ca3af" }}
              />
            </button>
          ))}
        </div>
        <div className="h-px w-6 bg-border my-1" />
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={create} title="Crea nuova lista">
          <Plus className="h-3.5 w-3.5" />
        </Button>
      </aside>
    );
  }

  return (
    <aside className="w-56 shrink-0 border-r bg-card/50 flex flex-col">
      <div className="px-3 py-2 border-b flex items-center justify-between">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
          <Tag className="h-3 w-3" /> Liste
        </h3>
        <div className="flex items-center gap-0.5">
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={create} title="Crea nuova lista">
            <Plus className="h-3.5 w-3.5" />
          </Button>
          {onToggleCollapsed && (
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={onToggleCollapsed}
              title="Comprimi liste"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      <button
        className={`flex items-center gap-2 px-3 py-1.5 text-sm border-l-2 transition-colors w-full text-left ${
          selectedListId === null
            ? "bg-accent border-primary text-primary font-medium"
            : "border-transparent hover:bg-accent/50"
        }`}
        onClick={() => onSelectList(null)}
      >
        <Users className="h-3.5 w-3.5 shrink-0" />
        <span className="flex-1 truncate">All companies</span>
      </button>

      <div className="overflow-y-auto flex-1">
        {loading ? (
          <div className="px-3 py-4 text-center text-muted-foreground text-xs">
            <Loader2 className="h-3 w-3 animate-spin inline mr-1" /> Caricamento…
          </div>
        ) : lists.length === 0 ? (
          <p className="px-3 py-4 text-center text-muted-foreground text-xs italic">
            Nessuna lista. Click + per crearne una.
          </p>
        ) : (
          lists.map((ll) => (
            <div
              key={ll.id}
              className={`group flex items-center gap-2 px-3 py-1.5 text-sm border-l-2 transition-colors cursor-pointer ${
                selectedListId === ll.id
                  ? "bg-accent border-primary"
                  : "border-transparent hover:bg-accent/50"
              }`}
              onClick={() => onSelectList(ll.id)}
            >
              <button
                onClick={(e) => { e.stopPropagation(); cycleColor(ll); }}
                className="h-2.5 w-2.5 rounded-full shrink-0"
                style={{ backgroundColor: ll.color || "#9ca3af" }}
                title="Click per cambiare colore"
              />
              <span className="flex-1 truncate">{ll.name}</span>
              <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground tabular-nums shrink-0">
                <span title={`${ll.companies_count} aziende`}>{ll.companies_count}</span>
                {(ll.dm_with_email_count ?? 0) > 0 && (
                  <span
                    className="inline-flex items-center gap-0.5 px-1 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 border border-emerald-200/60 dark:border-emerald-800/60"
                    title={`${ll.dm_with_email_count} decision maker con email`}
                  >
                    <Mail className="h-2.5 w-2.5" />
                    {ll.dm_with_email_count}
                  </span>
                )}
              </div>
              <div className="hidden group-hover:flex items-center">
                <button
                  className="text-muted-foreground hover:text-foreground p-0.5"
                  onClick={(e) => { e.stopPropagation(); renameList(ll); }}
                  title="Rinomina"
                >
                  <Edit2 className="h-3 w-3" />
                </button>
                <button
                  className="text-muted-foreground hover:text-destructive p-0.5"
                  onClick={(e) => { e.stopPropagation(); deleteList(ll); }}
                  title="Elimina lista"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
