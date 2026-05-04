"use client";

import { useState } from "react";
import {
  Search, Filter as FilterIcon, ArrowUpDown, MoreHorizontal,
  UserPlus, Sparkles, Trash2, ExternalLink, Plus, Loader2, X, Users, Mail, Type, Hash,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Company } from "@/types";

type ActionId = "find_dm" | "enrich" | "score" | "delete";

interface Props {
  companies: Company[];
  loading: boolean;
  search: string;
  onSearchChange: (v: string) => void;
  selectedIds: Set<number>;
  onToggleSelect: (id: number) => void;
  onToggleSelectAll: () => void;
  customFieldKeys: string[];
  onCompanyClick: (company: Company) => void;
  onAction: (companyId: number, action: ActionId) => Promise<void> | void;
  onCustomFieldSave: (companyId: number, key: string, value: string) => Promise<void> | void;
  onAddCustomFieldKey: () => void;
  rowsPerPage: number;
  pageIndex: number; // 0-indexed page (for row number offset)
  total: number;
}

const fmtRevenue = (n: number | null | undefined) =>
  n == null ? "—" : new Intl.NumberFormat("it-IT", {
    style: "currency", currency: "EUR", maximumFractionDigits: 0,
  }).format(n);

const fmtCount = (n: number | null | undefined) =>
  n == null ? "—" : new Intl.NumberFormat("it-IT").format(n);

function TypeIcon({ kind }: { kind: "text" | "number" | "multi" | "tag" | "people" }) {
  const cls = "h-3 w-3 text-muted-foreground/70";
  switch (kind) {
    case "number": return <Hash className={cls} />;
    case "people": return <Users className={cls} />;
    case "multi": return <Mail className={cls} />;
    default: return <Type className={cls} />;
  }
}

function TierBadge({ tier }: { tier?: string | null }) {
  if (!tier) return <span className="text-muted-foreground text-xs">—</span>;
  return (
    <Badge
      variant="outline"
      className={
        tier === "A"
          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
          : tier === "B"
          ? "bg-amber-50 text-amber-700 border-amber-200"
          : "bg-muted text-muted-foreground"
      }
    >
      {tier}
    </Badge>
  );
}

function ActionMenu({
  companyId,
  onAction,
  busy,
}: {
  companyId: number;
  onAction: Props["onAction"];
  busy: boolean;
}) {
  const [open, setOpen] = useState(false);
  const items: { id: ActionId; label: string; icon: React.ComponentType<{ className?: string }>; cls?: string }[] = [
    { id: "find_dm", label: "Trova decision makers", icon: UserPlus },
    { id: "enrich", label: "Arricchisci email/sito", icon: Sparkles },
    { id: "score", label: "Score con ICP", icon: Sparkles },
    { id: "delete", label: "Elimina", icon: Trash2, cls: "text-destructive" },
  ];
  return (
    <div className="relative inline-block">
      <Button
        variant="ghost" size="icon" className="h-7 w-7"
        onClick={(e) => { e.stopPropagation(); setOpen(!open); }}
        disabled={busy}
      >
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <MoreHorizontal className="h-3.5 w-3.5" />}
      </Button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-7 z-40 w-56 rounded-md border bg-popover shadow-md py-1">
            {items.map(({ id, label, icon: Icon, cls }) => (
              <button
                key={id}
                className={`flex items-center gap-2 px-3 py-1.5 text-sm w-full text-left hover:bg-accent ${cls || ""}`}
                onClick={(e) => { e.stopPropagation(); setOpen(false); onAction(companyId, id); }}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function EditableCustomCell({
  companyId,
  fieldKey,
  initial,
  onSave,
}: {
  companyId: number;
  fieldKey: string;
  initial: string;
  onSave: (cid: number, key: string, value: string) => Promise<void> | void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(initial);
  const [saving, setSaving] = useState(false);

  const commit = async () => {
    if (value === initial) { setEditing(false); return; }
    setSaving(true);
    try { await onSave(companyId, fieldKey, value); }
    finally { setSaving(false); setEditing(false); }
  };

  if (!editing) {
    return (
      <button
        className="text-sm text-left w-full truncate hover:bg-accent/40 px-1.5 py-0.5 rounded"
        title={initial || "Click to edit"}
        onClick={(e) => { e.stopPropagation(); setValue(initial); setEditing(true); }}
      >
        {initial || <span className="text-muted-foreground text-xs">—</span>}
      </button>
    );
  }
  return (
    <Input
      autoFocus
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => { if (e.key === "Enter") commit(); else if (e.key === "Escape") setEditing(false); }}
      onClick={(e) => e.stopPropagation()}
      className="h-7 text-sm"
      disabled={saving}
    />
  );
}

export function ClayCompaniesTable({
  companies, loading, search, onSearchChange,
  selectedIds, onToggleSelect, onToggleSelectAll,
  customFieldKeys, onCompanyClick, onAction, onCustomFieldSave, onAddCustomFieldKey,
  rowsPerPage, pageIndex, total,
}: Props) {
  const [busyRows, setBusyRows] = useState<Set<number>>(new Set());

  const handleAction: Props["onAction"] = async (cid, action) => {
    setBusyRows((s) => new Set(s).add(cid));
    try { await onAction(cid, action); }
    finally { setBusyRows((s) => { const n = new Set(s); n.delete(cid); return n; }); }
  };

  const allOnPageSelected = companies.length > 0 && companies.every((c) => selectedIds.has(c.id));

  // Total visible columns: 8 fixed + 1 per custom + 1 (#) + 1 (checkbox) + 1 (people) + 1 (action menu)
  const baseCols = 8;
  const visibleColCount = baseCols + customFieldKeys.length;

  return (
    <div className="rounded-md border bg-card">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b text-xs">
        <div className="relative flex-1 max-w-sm">
          <Search className="h-3.5 w-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" />
          <Input
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search company name…"
            className="h-7 text-xs pl-8"
          />
          {search && (
            <button
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              onClick={() => onSearchChange("")}
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
        <Button variant="ghost" size="sm" className="h-7 text-xs gap-1.5" disabled>
          <FilterIcon className="h-3 w-3" /> Filter
        </Button>
        <Button variant="ghost" size="sm" className="h-7 text-xs gap-1.5" disabled>
          <ArrowUpDown className="h-3 w-3" /> Sort
        </Button>
        <div className="ml-auto flex items-center gap-3 text-muted-foreground">
          <span>{visibleColCount} columns</span>
          <span>·</span>
          <span>{total.toLocaleString("it-IT")} rows</span>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-[40px] py-1.5">
                <Checkbox
                  checked={allOnPageSelected}
                  onCheckedChange={onToggleSelectAll}
                />
              </TableHead>
              <TableHead className="w-[40px] text-center text-[10px] font-mono text-muted-foreground py-1.5">#</TableHead>
              <ColHeader icon="text">Nome Azienda</ColHeader>
              <ColHeader icon="number" align="right">Fatturato</ColHeader>
              <ColHeader icon="number" align="right">Dipendenti</ColHeader>
              <ColHeader icon="text">Settore</ColHeader>
              <ColHeader icon="text">Provincia</ColHeader>
              <ColHeader icon="text">Città</ColHeader>
              <ColHeader icon="tag" align="center">Tier</ColHeader>
              <ColHeader icon="number" align="right">Score</ColHeader>
              <ColHeader icon="multi">Email Aziendali</ColHeader>
              <ColHeader icon="people" align="center">Decision Makers</ColHeader>
              {customFieldKeys.map((k) => (
                <TableHead key={k} className="py-1.5">
                  <div className="flex items-center gap-1.5">
                    <TypeIcon kind="text" />
                    <span className="text-xs font-medium">{k}</span>
                  </div>
                </TableHead>
              ))}
              <TableHead className="w-[40px] text-center py-1.5">
                <Button variant="ghost" size="icon" className="h-6 w-6"
                  title="Aggiungi colonna custom"
                  onClick={onAddCustomFieldKey}>
                  <Plus className="h-3.5 w-3.5" />
                </Button>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow><TableCell colSpan={visibleColCount + 4} className="text-center py-6 text-muted-foreground text-sm">
                <Loader2 className="h-4 w-4 animate-spin inline mr-2" /> Caricamento…
              </TableCell></TableRow>
            ) : companies.length === 0 ? (
              <TableRow><TableCell colSpan={visibleColCount + 4} className="text-center py-12 text-muted-foreground text-sm">
                Nessuna azienda. Importa un CSV per iniziare.
              </TableCell></TableRow>
            ) : companies.map((c, idx) => {
              const rowNum = pageIndex * rowsPerPage + idx + 1;
              const generic = c.generic_emails && c.generic_emails.length > 0 ? c.generic_emails : (c.email ? [c.email] : []);
              return (
                <TableRow
                  key={c.id}
                  className={`group ${selectedIds.has(c.id) ? "bg-primary/5" : ""}`}
                >
                  <TableCell className="py-1.5">
                    <Checkbox
                      checked={selectedIds.has(c.id)}
                      onCheckedChange={() => onToggleSelect(c.id)}
                    />
                  </TableCell>
                  <TableCell className="text-center font-mono text-[10px] text-muted-foreground py-1.5">{rowNum}</TableCell>
                  <TableCell className="font-medium py-1.5">
                    <button
                      className="text-primary hover:underline text-left flex items-center gap-1.5 max-w-[260px] truncate"
                      onClick={() => onCompanyClick(c)}
                      title={c.name}
                    >
                      <span className="truncate">{c.name}</span>
                      {c.website && <ExternalLink className="h-3 w-3 text-muted-foreground shrink-0" />}
                    </button>
                  </TableCell>
                  <TableCell className="text-right tabular-nums py-1.5">{fmtRevenue(c.revenue)}</TableCell>
                  <TableCell className="text-right tabular-nums py-1.5">{fmtCount(c.employee_count)}</TableCell>
                  <TableCell className="text-sm py-1.5 max-w-[200px] truncate" title={c.industry || undefined}>
                    {c.industry || "—"}
                  </TableCell>
                  <TableCell className="text-sm py-1.5">{c.province || "—"}</TableCell>
                  <TableCell className="text-sm py-1.5">{c.location || "—"}</TableCell>
                  <TableCell className="text-center py-1.5">
                    <span title={c.reason_summary || undefined}>
                      <TierBadge tier={c.priority_tier} />
                    </span>
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-sm py-1.5">
                    {typeof c.icp_score === "number" ? c.icp_score : "—"}
                  </TableCell>
                  <TableCell className="py-1.5 max-w-[260px]">
                    {generic.length === 0 ? (
                      <span className="text-muted-foreground text-xs">—</span>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {generic.slice(0, 2).map((e) => (
                          <Badge key={e} variant="secondary" className="text-[10px] font-normal px-1.5">{e}</Badge>
                        ))}
                        {generic.length > 2 && (
                          <Badge variant="outline" className="text-[10px]">+{generic.length - 2}</Badge>
                        )}
                      </div>
                    )}
                  </TableCell>
                  <TableCell className="text-center py-1.5">
                    {c.people_count > 0 ? (
                      <button onClick={() => onCompanyClick(c)}>
                        <Badge variant="outline" className="cursor-pointer hover:bg-accent gap-1">
                          <Users className="h-3 w-3" /> {c.people_count}
                        </Badge>
                      </button>
                    ) : (
                      <span className="text-muted-foreground text-xs">—</span>
                    )}
                  </TableCell>
                  {customFieldKeys.map((k) => (
                    <TableCell key={k} className="py-1.5 max-w-[200px]">
                      <EditableCustomCell
                        companyId={c.id}
                        fieldKey={k}
                        initial={(c.custom_fields && c.custom_fields[k]) || ""}
                        onSave={onCustomFieldSave}
                      />
                    </TableCell>
                  ))}
                  <TableCell className="text-center py-1.5">
                    <ActionMenu companyId={c.id} onAction={handleAction} busy={busyRows.has(c.id)} />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function ColHeader({
  children, icon, align,
}: {
  children: React.ReactNode;
  icon: "text" | "number" | "multi" | "tag" | "people";
  align?: "left" | "right" | "center";
}) {
  const kind = icon === "tag" ? "text" : (icon as "text" | "number" | "multi" | "people");
  return (
    <TableHead className={`py-1.5 ${align === "right" ? "text-right" : align === "center" ? "text-center" : ""}`}>
      <div className={`flex items-center gap-1.5 ${align === "right" ? "justify-end" : align === "center" ? "justify-center" : ""}`}>
        <TypeIcon kind={kind} />
        <span className="text-xs font-medium">{children}</span>
      </div>
    </TableHead>
  );
}
