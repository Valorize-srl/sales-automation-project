"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Search, Filter as FilterIcon, ArrowUpDown, MoreHorizontal,
  UserPlus, Sparkles, Trash2, ExternalLink, Plus, Loader2, X, Users, Mail, Type, Hash, Linkedin, Pencil,
  GripVertical,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Company, LeadList } from "@/types";

type ActionId = "find_dm" | "enrich" | "push_to_campaign" | "delete";

export type EditableCompanyField =
  | "name"
  | "website"
  | "linkedin_url"
  | "industry"
  | "province"
  | "location"
  | "revenue"
  | "employee_count"
  | "zip_code"
  | "vat_number"
  | "tax_id"
  | "source_company_id";

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
  onPersonClick?: (personId: number) => void;
  onAction: (companyId: number, action: ActionId) => Promise<void> | void;
  onCustomFieldSave: (companyId: number, key: string, value: string) => Promise<void> | void;
  /** Inline edit of a top-level Company field (name/website/industry/...). */
  onCompanyFieldSave: (
    companyId: number,
    field: EditableCompanyField,
    value: string | number | null,
  ) => Promise<void> | void;
  /** Replace a company's primary email + generic_emails list. */
  onCompanyEmailsSave: (
    companyId: number,
    primary: string | null,
    generic: string[],
  ) => Promise<void> | void;
  /** Create a new Person linked to the company (used by the "+ Nuovo DM" button). */
  onCreateCompanyPerson: (
    companyId: number,
    payload: { first_name: string; last_name: string; email?: string | null; title?: string | null; linkedin_url?: string | null },
  ) => Promise<void> | void;
  onAddCustomFieldKey: () => void;
  rowsPerPage: number;
  pageIndex: number;
  total: number;
  allLists?: LeadList[];
  selectAllMatching?: boolean;
  onSelectAllMatching?: (v: boolean) => void;
}

// ---- formatting helpers ----------------------------------------------------

const fmtRevenue = (n: number | null | undefined) =>
  n == null ? "—" : new Intl.NumberFormat("it-IT", {
    style: "currency", currency: "EUR", maximumFractionDigits: 0,
  }).format(n);

const fmtCount = (n: number | null | undefined) =>
  n == null ? "—" : new Intl.NumberFormat("it-IT").format(n);

type IconKind = "text" | "number" | "multi" | "tag" | "people";
type Align = "left" | "right" | "center";

function TypeIcon({ kind }: { kind: IconKind }) {
  const cls = "h-3 w-3 text-muted-foreground/70";
  switch (kind) {
    case "number": return <Hash className={cls} />;
    case "people": return <Users className={cls} />;
    case "multi": return <Mail className={cls} />;
    default: return <Type className={cls} />;
  }
}

// ---- column definitions ----------------------------------------------------

interface CellCtx {
  listsById: Map<number, LeadList>;
  onCompanyClick: (c: Company) => void;
  onPersonClick?: (personId: number) => void;
  onCustomFieldSave: (companyId: number, key: string, value: string) => void;
  onCompanyFieldSave: (
    companyId: number,
    field: EditableCompanyField,
    value: string | number | null,
  ) => Promise<void> | void;
  /** Save a company's primary email + generic_emails list as a whole. */
  onCompanyEmailsSave: (
    companyId: number,
    primary: string | null,
    generic: string[],
  ) => Promise<void> | void;
  /** Create a Person record linked to the company; UI refreshes after save. */
  onCreateCompanyPerson: (
    companyId: number,
    payload: { first_name: string; last_name: string; email?: string | null; title?: string | null; linkedin_url?: string | null },
  ) => Promise<void> | void;
}

interface ColumnDef {
  id: string;          // unique id, "cf:<key>" for custom fields
  label: string;
  iconKind: IconKind;
  align?: Align;
  maxWidth?: string;
  renderCell: (c: Company, ctx: CellCtx) => React.ReactNode;
}

const COMPANY_EMAILS = (c: Company): string[] => {
  const generic = c.generic_emails && c.generic_emails.length > 0 ? c.generic_emails : [];
  return generic.length > 0 ? generic : (c.email ? [c.email] : []);
};

const FIXED_COLUMNS: ColumnDef[] = [
  {
    id: "name", label: "Nome Azienda", iconKind: "text",
    renderCell: (c, ctx) => (
      <EditableCell
        mode="pencil"
        value={c.name}
        onSave={(v) => ctx.onCompanyFieldSave(c.id, "name", v)}
        pencilTitle="Rinomina"
        display={
          <button
            className="text-primary hover:underline text-left flex items-center gap-1.5 max-w-[260px] truncate font-medium"
            onClick={(e) => { e.stopPropagation(); ctx.onCompanyClick(c); }}
            title={c.name}
          >
            <span className="truncate">{c.name}</span>
            {c.website && <ExternalLink className="h-3 w-3 text-muted-foreground shrink-0" />}
          </button>
        }
      />
    ),
  },
  {
    id: "revenue", label: "Fatturato", iconKind: "number", align: "right",
    renderCell: (c, ctx) => (
      <EditableCell
        type="number"
        value={c.revenue ?? null}
        onSave={(v) => ctx.onCompanyFieldSave(c.id, "revenue", v)}
        display={<span className="tabular-nums">{fmtRevenue(c.revenue)}</span>}
      />
    ),
  },
  {
    id: "employee_count", label: "Dipendenti", iconKind: "number", align: "right",
    renderCell: (c, ctx) => (
      <EditableCell
        type="number"
        value={c.employee_count ?? null}
        onSave={(v) => ctx.onCompanyFieldSave(c.id, "employee_count", v)}
        display={<span className="tabular-nums">{fmtCount(c.employee_count)}</span>}
      />
    ),
  },
  {
    id: "industry", label: "Settore", iconKind: "text", maxWidth: "200px",
    renderCell: (c, ctx) => (
      <EditableCell
        value={c.industry ?? null}
        onSave={(v) => ctx.onCompanyFieldSave(c.id, "industry", v)}
        display={
          <span className="text-sm truncate block" title={c.industry || undefined}>
            {c.industry || <span className="text-muted-foreground text-xs">—</span>}
          </span>
        }
      />
    ),
  },
  {
    id: "website", label: "Sito Web", iconKind: "text", maxWidth: "220px",
    renderCell: (c, ctx) => {
      let displayUrl = c.website || "";
      if (c.website) {
        try {
          const u = new URL(c.website.startsWith("http") ? c.website : `https://${c.website}`);
          displayUrl = u.hostname.replace(/^www\./, "") + (u.pathname !== "/" ? u.pathname : "");
        } catch {
          // keep raw display
        }
      }
      const display = c.website ? (
        <a
          href={c.website.startsWith("http") ? c.website : `https://${c.website}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline text-sm flex items-center gap-1 max-w-full truncate"
          title={c.website}
          onClick={(e) => e.stopPropagation()}
        >
          <span className="truncate">{displayUrl}</span>
          <ExternalLink className="h-3 w-3 shrink-0" />
        </a>
      ) : (
        <span className="text-muted-foreground text-xs">—</span>
      );
      return (
        <EditableCell
          mode="pencil"
          value={c.website ?? null}
          onSave={(v) => ctx.onCompanyFieldSave(c.id, "website", v)}
          display={display}
        />
      );
    },
  },
  {
    id: "linkedin_url", label: "LinkedIn azienda", iconKind: "text", maxWidth: "220px",
    renderCell: (c, ctx) => {
      let displayUrl = c.linkedin_url || "";
      if (c.linkedin_url) {
        try {
          const u = new URL(c.linkedin_url.startsWith("http") ? c.linkedin_url : `https://${c.linkedin_url}`);
          displayUrl = (u.pathname.replace(/^\/+|\/+$/g, "") || u.hostname).replace(/^company\//, "");
        } catch {
          // keep raw display
        }
      }
      const display = c.linkedin_url ? (
        <a
          href={c.linkedin_url.startsWith("http") ? c.linkedin_url : `https://${c.linkedin_url}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[#0A66C2] hover:underline text-sm flex items-center gap-1 max-w-full truncate"
          title={c.linkedin_url}
          onClick={(e) => e.stopPropagation()}
        >
          <Linkedin className="h-3 w-3 shrink-0" />
          <span className="truncate">{displayUrl}</span>
        </a>
      ) : (
        <span className="text-muted-foreground text-xs">—</span>
      );
      return (
        <EditableCell
          mode="pencil"
          value={c.linkedin_url ?? null}
          onSave={(v) => ctx.onCompanyFieldSave(c.id, "linkedin_url", v)}
          display={display}
        />
      );
    },
  },
  {
    id: "province", label: "Provincia", iconKind: "text",
    renderCell: (c, ctx) => (
      <EditableCell
        value={c.province ?? null}
        onSave={(v) => ctx.onCompanyFieldSave(c.id, "province", v)}
        display={<span className="text-sm">{c.province || <span className="text-muted-foreground text-xs">—</span>}</span>}
      />
    ),
  },
  {
    id: "location", label: "Città", iconKind: "text",
    renderCell: (c, ctx) => (
      <EditableCell
        value={c.location ?? null}
        onSave={(v) => ctx.onCompanyFieldSave(c.id, "location", v)}
        display={<span className="text-sm">{c.location || <span className="text-muted-foreground text-xs">—</span>}</span>}
      />
    ),
  },
  {
    id: "company_emails", label: "Email Aziendali", iconKind: "multi", maxWidth: "260px",
    renderCell: (c, ctx) => {
      const emails = COMPANY_EMAILS(c);
      const trigger = emails.length === 0
        ? <span className="text-muted-foreground text-xs">— click per aggiungere</span>
        : (
          <div className="flex flex-wrap gap-1">
            {emails.slice(0, 2).map((e) => (
              <Badge key={e} variant="secondary" className="text-[10px] font-normal px-1.5">{e}</Badge>
            ))}
            {emails.length > 2 && <Badge variant="outline" className="text-[10px]">+{emails.length - 2}</Badge>}
          </div>
        );
      return (
        <EmailListEditor
          companyId={c.id}
          primary={c.email ?? null}
          generic={c.generic_emails ?? []}
          onSave={ctx.onCompanyEmailsSave}
          trigger={trigger}
        />
      );
    },
  },
  {
    id: "decision_makers", label: "Decision Makers", iconKind: "people", maxWidth: "300px",
    renderCell: (c, ctx) => {
      const dms = c.decision_makers || [];
      if (dms.length === 0 && c.people_count > 0) {
        return (
          <div className="flex items-center gap-1">
            <button onClick={() => ctx.onCompanyClick(c)}>
              <Badge variant="outline" className="cursor-pointer hover:bg-accent gap-1">
                <Users className="h-3 w-3" /> {c.people_count}
              </Badge>
            </button>
            <NewDMQuickButton companyId={c.id} onCreate={ctx.onCreateCompanyPerson} />
          </div>
        );
      }
      return (
        <div className="flex flex-wrap items-center gap-1">
          {dms.slice(0, 3).map((dm) => {
            const fullName = `${dm.first_name ?? ""} ${dm.last_name ?? ""}`.trim() || dm.email || `#${dm.id}`;
            return (
              <button
                key={dm.id}
                type="button"
                className="inline-flex items-center gap-1 rounded-md border bg-background px-1.5 py-0.5 text-[10px] hover:bg-accent"
                onClick={(e) => { e.stopPropagation(); ctx.onPersonClick?.(dm.id); }}
                title={dm.title ? `${fullName} · ${dm.title}` : fullName}
              >
                <span className="h-1.5 w-1.5 rounded-full bg-primary/60" />
                <span className="truncate max-w-[120px]">{fullName}</span>
              </button>
            );
          })}
          {dms.length > 3 && <Badge variant="outline" className="text-[10px]">+{dms.length - 3}</Badge>}
          <NewDMQuickButton companyId={c.id} onCreate={ctx.onCreateCompanyPerson} />
        </div>
      );
    },
  },
  {
    id: "dm_linkedin", label: "LinkedIn DM", iconKind: "multi", maxWidth: "260px",
    renderCell: (c) => {
      const dms = (c.decision_makers || []).filter((d) => d.linkedin_url);
      if (dms.length === 0) return <span className="text-muted-foreground text-xs">—</span>;
      const fmtName = (d: typeof dms[0]) =>
        [d.first_name, d.last_name].filter(Boolean).join(" ") || "Profilo";
      return (
        <div className="flex flex-wrap gap-1">
          {dms.slice(0, 2).map((d) => (
            <a
              key={d.id}
              href={d.linkedin_url!}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              title={d.linkedin_url!}
              className="inline-flex items-center gap-1 text-[10px] font-normal px-1.5 py-0.5 rounded border border-[#0A66C2]/30 bg-[#0A66C2]/5 text-[#0A66C2] hover:bg-[#0A66C2]/10 hover:underline max-w-[140px]"
            >
              <Linkedin className="h-2.5 w-2.5 shrink-0" />
              <span className="truncate">{fmtName(d)}</span>
            </a>
          ))}
          {dms.length > 2 && <Badge variant="outline" className="text-[10px]">+{dms.length - 2}</Badge>}
        </div>
      );
    },
  },
  {
    id: "work_emails", label: "Email Lavoro", iconKind: "multi", maxWidth: "260px",
    renderCell: (c) => {
      const emails = c.work_emails || [];
      if (emails.length === 0) return <span className="text-muted-foreground text-xs">—</span>;
      return (
        <div className="flex flex-wrap gap-1">
          {emails.slice(0, 2).map((e) => (
            <Badge key={e} variant="outline" className="text-[10px] font-normal px-1.5 bg-emerald-50 border-emerald-200 text-emerald-900">
              {e}
            </Badge>
          ))}
          {emails.length > 2 && <Badge variant="outline" className="text-[10px]">+{emails.length - 2}</Badge>}
        </div>
      );
    },
  },
  {
    id: "lists", label: "Liste", iconKind: "tag", maxWidth: "220px",
    renderCell: (c, ctx) => {
      const ids = c.list_ids || [];
      if (ids.length === 0) return <span className="text-muted-foreground text-xs">—</span>;
      return (
        <div className="flex flex-wrap gap-1">
          {ids.slice(0, 3).map((id) => {
            const ll = ctx.listsById.get(id);
            if (!ll) return null;
            return (
              <Badge key={id} variant="outline" className="text-[10px] gap-1 font-normal">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: ll.color || "#9ca3af" }} />
                {ll.name}
              </Badge>
            );
          })}
          {ids.length > 3 && <Badge variant="outline" className="text-[10px]">+{ids.length - 3}</Badge>}
        </div>
      );
    },
  },
  {
    id: "zip_code", label: "CAP", iconKind: "text",
    renderCell: (c, ctx) => (
      <EditableCell
        value={c.zip_code ?? null}
        onSave={(v) => ctx.onCompanyFieldSave(c.id, "zip_code", v)}
        display={<span className="text-sm tabular-nums">{c.zip_code || <span className="text-muted-foreground text-xs">—</span>}</span>}
      />
    ),
  },
  {
    id: "vat_number", label: "P.IVA", iconKind: "text", maxWidth: "180px",
    renderCell: (c, ctx) => (
      <EditableCell
        value={c.vat_number ?? null}
        onSave={(v) => ctx.onCompanyFieldSave(c.id, "vat_number", v)}
        display={<span className="text-sm tabular-nums">{c.vat_number || <span className="text-muted-foreground text-xs">—</span>}</span>}
      />
    ),
  },
  {
    id: "tax_id", label: "Codice Fiscale", iconKind: "text", maxWidth: "200px",
    renderCell: (c, ctx) => (
      <EditableCell
        value={c.tax_id ?? null}
        onSave={(v) => ctx.onCompanyFieldSave(c.id, "tax_id", v)}
        display={<span className="text-sm tabular-nums">{c.tax_id || <span className="text-muted-foreground text-xs">—</span>}</span>}
      />
    ),
  },
  {
    // Read-only by design — the column is a Postgres UUID. Manual entries
    // get NULL ("manuale"); Seikoo-imported rows get a UUID we don't want
    // users hand-editing.
    id: "source_company_id", label: "Origine", iconKind: "text", maxWidth: "180px",
    renderCell: (c) =>
      c.source_company_id
        ? (
          <span
            className="text-[11px] tabular-nums text-muted-foreground truncate inline-block max-w-full"
            title={c.source_company_id}
          >
            Seikoo · {c.source_company_id.slice(0, 8)}…
          </span>
        )
        : <Badge variant="outline" className="text-[10px] font-normal text-muted-foreground">manuale</Badge>,
  },
];

// User-requested default: Decision Makers immediately before Email Lavoro,
// and both adjacent to Email Aziendali for a clean contact-data block.
const DEFAULT_ORDER: string[] = FIXED_COLUMNS.map((c) => c.id);

const ORDER_STORAGE_KEY = "clay.companies.column.order.v2";

function loadStoredOrder(): string[] | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(ORDER_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed) && parsed.every((x) => typeof x === "string")) {
      return parsed;
    }
  } catch {
    return null;
  }
  return null;
}

function saveStoredOrder(order: string[]): void {
  if (typeof window === "undefined") return;
  try { window.localStorage.setItem(ORDER_STORAGE_KEY, JSON.stringify(order)); } catch { /* noop */ }
}

/** Reconcile a stored order with the runtime set of column ids: drop unknowns,
 *  append new ones (e.g. newly added custom-field columns) at the end. */
function reconcileOrder(stored: string[] | null, allIds: string[]): string[] {
  const known = new Set(allIds);
  const seen = new Set<string>();
  const out: string[] = [];
  if (stored) {
    for (const id of stored) {
      if (known.has(id) && !seen.has(id)) { out.push(id); seen.add(id); }
    }
  }
  for (const id of allIds) {
    if (!seen.has(id)) { out.push(id); seen.add(id); }
  }
  return out;
}

// ---- ActionMenu, EditableCustomCell (unchanged behaviour) ------------------

function ActionMenu({
  companyId, onAction, busy,
}: {
  companyId: number;
  onAction: Props["onAction"];
  busy: boolean;
}) {
  const [open, setOpen] = useState(false);
  const items: { id: ActionId; label: string; icon: React.ComponentType<{ className?: string }>; cls?: string }[] = [
    { id: "find_dm", label: "Trova decision makers", icon: UserPlus },
    { id: "enrich", label: "Arricchisci email/sito", icon: Sparkles },
    { id: "push_to_campaign", label: "Aggiungi DM a campagna…", icon: UserPlus },
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

/**
 * EditableCell — inline-editable wrapper around a display node.
 *
 * Two modes (auto-detected from the `mode` prop):
 *
 * - "click"   : the entire cell area is the edit trigger. Used when the cell
 *               has no other primary action (industry, province, location,
 *               revenue, employee_count, …). On hover the cell highlights so
 *               the user can see it's clickable.
 * - "pencil"  : the display keeps its own primary action (e.g. open detail
 *               dialog, follow external link); a small pencil appears on
 *               hover and is the explicit edit affordance.
 *
 * For numeric cells (`type="number"`), invalid input is dropped and an empty
 * draft is sent to the backend as `null`.
 */
function EditableCell({
  type = "text",
  mode = "click",
  value,
  display,
  onSave,
  pencilTitle = "Modifica",
}: {
  type?: "text" | "number";
  mode?: "click" | "pencil";
  value: string | number | null | undefined;
  display: React.ReactNode;
  onSave: (newValue: string | number | null) => Promise<void> | void;
  pencilTitle?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string>(
    value === null || value === undefined ? "" : String(value)
  );
  const [saving, setSaving] = useState(false);

  const startEditing = (e: React.MouseEvent | React.KeyboardEvent) => {
    e.stopPropagation();
    setDraft(value === null || value === undefined ? "" : String(value));
    setEditing(true);
  };

  const commit = async () => {
    let parsed: string | number | null;
    if (type === "number") {
      const t = draft.trim();
      if (t === "") parsed = null;
      else {
        const n = Number(t.replace(",", "."));
        parsed = Number.isFinite(n) ? n : null;
      }
    } else {
      parsed = draft.trim() || null;
    }
    if (parsed === (value ?? null)) { setEditing(false); return; }
    setSaving(true);
    try {
      await onSave(parsed);
    } finally {
      setSaving(false);
      setEditing(false);
    }
  };

  if (editing) {
    return (
      <Input
        autoFocus
        type={type === "number" ? "number" : "text"}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          else if (e.key === "Escape") setEditing(false);
        }}
        onClick={(e) => e.stopPropagation()}
        className="h-7 text-sm w-full"
        disabled={saving}
      />
    );
  }

  if (mode === "click") {
    // Whole-cell click target. Hover highlight + small pencil hint on the right.
    return (
      <button
        type="button"
        className="group relative w-full text-left min-h-[24px] flex items-center hover:bg-accent/40 rounded px-1.5 -mx-1.5 -my-0.5 py-0.5"
        onClick={startEditing}
        title={pencilTitle}
      >
        <div className="flex-1 min-w-0">{display}</div>
        <Pencil className="h-3 w-3 ml-1 shrink-0 opacity-0 group-hover:opacity-50 text-muted-foreground transition-opacity" />
      </button>
    );
  }

  // pencil mode — display keeps its own onClick; pencil is the only edit trigger.
  return (
    <div className="group relative w-full flex items-center min-h-[24px]">
      <div className="flex-1 min-w-0">{display}</div>
      <button
        type="button"
        title={pencilTitle}
        className="opacity-30 group-hover:opacity-100 ml-1 p-0.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground transition-opacity"
        onClick={startEditing}
      >
        <Pencil className="h-3 w-3" />
      </button>
    </div>
  );
}

/**
 * EmailListEditor — popover trigger for the "Email Aziendali" cell.
 *
 * Click the trigger area → opens an absolute-positioned panel with:
 *   - the primary `email` field (the one stored on Company.email)
 *   - the additional `generic_emails` as removable chips
 *   - an input to add a new email
 *   - "Salva" button → commits via onSave(primary, generic[])
 */
function EmailListEditor({
  companyId,
  primary,
  generic,
  onSave,
  trigger,
}: {
  companyId: number;
  primary: string | null;
  generic: string[];
  onSave: (companyId: number, primary: string | null, generic: string[]) => Promise<void> | void;
  trigger: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [draftPrimary, setDraftPrimary] = useState(primary ?? "");
  const [draftGeneric, setDraftGeneric] = useState<string[]>(generic);
  const [newEmail, setNewEmail] = useState("");
  const [saving, setSaving] = useState(false);

  const reset = () => {
    setDraftPrimary(primary ?? "");
    setDraftGeneric(generic);
    setNewEmail("");
  };

  const openPanel = (e: React.MouseEvent) => {
    e.stopPropagation();
    reset();
    setOpen(true);
  };

  const addEmail = () => {
    const t = newEmail.trim();
    if (!t) return;
    if (draftGeneric.some((e) => e.toLowerCase() === t.toLowerCase()) || (draftPrimary && draftPrimary.toLowerCase() === t.toLowerCase())) {
      setNewEmail("");
      return;
    }
    setDraftGeneric([...draftGeneric, t]);
    setNewEmail("");
  };

  const commit = async () => {
    setSaving(true);
    try {
      await onSave(companyId, draftPrimary.trim() || null, draftGeneric);
      setOpen(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="relative w-full">
      <button
        type="button"
        className="text-left w-full hover:bg-accent/40 rounded px-1.5 -mx-1.5 -my-0.5 py-0.5 group flex items-center"
        onClick={openPanel}
        title="Modifica email aziendali"
      >
        <div className="flex-1 min-w-0">{trigger}</div>
        <Pencil className="h-3 w-3 ml-1 shrink-0 opacity-0 group-hover:opacity-50 text-muted-foreground transition-opacity" />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-9 z-40 w-80 rounded-md border bg-popover shadow-md p-3 space-y-2.5">
            <div className="space-y-1">
              <label className="text-[11px] font-medium text-muted-foreground">Email primaria</label>
              <Input
                value={draftPrimary}
                onChange={(e) => setDraftPrimary(e.target.value)}
                placeholder="info@azienda.it"
                className="h-8 text-sm"
                onClick={(e) => e.stopPropagation()}
              />
            </div>
            {draftGeneric.length > 0 && (
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-muted-foreground">Altre email</label>
                <div className="flex flex-wrap gap-1">
                  {draftGeneric.map((em) => (
                    <span
                      key={em}
                      className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-muted border"
                    >
                      {em}
                      <button
                        type="button"
                        className="text-muted-foreground hover:text-destructive"
                        onClick={(e) => { e.stopPropagation(); setDraftGeneric(draftGeneric.filter((x) => x !== em)); }}
                      >
                        <X className="h-2.5 w-2.5" />
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            )}
            <div className="flex gap-1.5">
              <Input
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                placeholder="Aggiungi email"
                className="h-8 text-sm flex-1"
                onClick={(e) => e.stopPropagation()}
                onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addEmail(); } }}
              />
              <Button size="sm" variant="outline" className="h-8 px-2.5 text-xs"
                onClick={(e) => { e.stopPropagation(); addEmail(); }}>
                Aggiungi
              </Button>
            </div>
            <div className="flex justify-end gap-2 pt-1 border-t">
              <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setOpen(false)} disabled={saving}>
                Annulla
              </Button>
              <Button size="sm" className="h-7 text-xs" onClick={commit} disabled={saving}>
                {saving ? "Salvo…" : "Salva"}
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/**
 * NewDMQuickButton — small "+ DM" button inline at the end of the
 * Decision Makers chip list. Opens a popover with first/last/email/title/li
 * and creates a Person record on save.
 */
function NewDMQuickButton({
  companyId,
  onCreate,
}: {
  companyId: number;
  onCreate: (
    companyId: number,
    payload: { first_name: string; last_name: string; email?: string | null; title?: string | null; linkedin_url?: string | null },
  ) => Promise<void> | void;
}) {
  const [open, setOpen] = useState(false);
  const [first, setFirst] = useState("");
  const [last, setLast] = useState("");
  const [email, setEmail] = useState("");
  const [title, setTitle] = useState("");
  const [linkedin, setLinkedin] = useState("");
  const [saving, setSaving] = useState(false);

  const reset = () => {
    setFirst(""); setLast(""); setEmail(""); setTitle(""); setLinkedin("");
  };
  const canSave = first.trim().length > 0 && last.trim().length > 0;

  const commit = async () => {
    if (!canSave) return;
    setSaving(true);
    try {
      await onCreate(companyId, {
        first_name: first.trim(),
        last_name: last.trim(),
        email: email.trim() || null,
        title: title.trim() || null,
        linkedin_url: linkedin.trim() || null,
      });
      reset();
      setOpen(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <span className="relative inline-block">
      <button
        type="button"
        title="Aggiungi decision maker"
        className="inline-flex items-center gap-0.5 rounded-md border border-dashed bg-background px-1.5 py-0.5 text-[10px] text-muted-foreground hover:bg-accent hover:text-foreground"
        onClick={(e) => { e.stopPropagation(); reset(); setOpen(true); }}
      >
        <Plus className="h-2.5 w-2.5" /> DM
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-7 z-40 w-72 rounded-md border bg-popover shadow-md p-3 space-y-2">
            <p className="text-xs font-medium">Nuovo decision maker</p>
            <div className="grid grid-cols-2 gap-1.5">
              <Input placeholder="Nome" value={first} onChange={(e) => setFirst(e.target.value)} className="h-8 text-xs" onClick={(e) => e.stopPropagation()} />
              <Input placeholder="Cognome" value={last} onChange={(e) => setLast(e.target.value)} className="h-8 text-xs" onClick={(e) => e.stopPropagation()} />
            </div>
            <Input placeholder="Ruolo (es. CEO)" value={title} onChange={(e) => setTitle(e.target.value)} className="h-8 text-xs" onClick={(e) => e.stopPropagation()} />
            <Input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} className="h-8 text-xs" onClick={(e) => e.stopPropagation()} />
            <Input placeholder="LinkedIn URL" value={linkedin} onChange={(e) => setLinkedin(e.target.value)} className="h-8 text-xs" onClick={(e) => e.stopPropagation()} />
            <div className="flex justify-end gap-2 pt-1 border-t">
              <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setOpen(false)} disabled={saving}>
                Annulla
              </Button>
              <Button size="sm" className="h-7 text-xs" onClick={commit} disabled={!canSave || saving}>
                {saving ? "Salvo…" : "Crea"}
              </Button>
            </div>
          </div>
        </>
      )}
    </span>
  );
}

function EditableCustomCell({
  companyId, fieldKey, initial, onSave,
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

// ---- main component --------------------------------------------------------

export function ClayCompaniesTable({
  companies, loading, search, onSearchChange,
  selectedIds, onToggleSelect, onToggleSelectAll,
  customFieldKeys, onCompanyClick, onPersonClick, onAction, onCustomFieldSave, onCompanyFieldSave,
  onCompanyEmailsSave, onCreateCompanyPerson, onAddCustomFieldKey,
  rowsPerPage, pageIndex, total, allLists,
  selectAllMatching, onSelectAllMatching,
}: Props) {
  const listsById = useMemo(
    () => new Map((allLists || []).map((l) => [l.id, l])),
    [allLists],
  );
  const ctx: CellCtx = useMemo(
    () => ({ listsById, onCompanyClick, onPersonClick, onCustomFieldSave, onCompanyFieldSave, onCompanyEmailsSave, onCreateCompanyPerson }),
    [listsById, onCompanyClick, onPersonClick, onCustomFieldSave, onCompanyFieldSave, onCompanyEmailsSave, onCreateCompanyPerson],
  );

  const [busyRows, setBusyRows] = useState<Set<number>>(new Set());
  const handleAction: Props["onAction"] = async (cid, action) => {
    setBusyRows((s) => new Set(s).add(cid));
    try { await onAction(cid, action); }
    finally { setBusyRows((s) => { const n = new Set(s); n.delete(cid); return n; }); }
  };

  // Build the runtime set of columns (fixed + one per custom field key)
  const allColumns: ColumnDef[] = useMemo(() => {
    const cfCols: ColumnDef[] = customFieldKeys.map((k) => ({
      id: `cf:${k}`,
      label: k,
      iconKind: "text",
      maxWidth: "200px",
      renderCell: (c, c2) => (
        <EditableCustomCell
          companyId={c.id}
          fieldKey={k}
          initial={(c.custom_fields && c.custom_fields[k]) || ""}
          onSave={c2.onCustomFieldSave}
        />
      ),
    }));
    return [...FIXED_COLUMNS, ...cfCols];
  }, [customFieldKeys]);

  // Order state (with localStorage persistence + reconciliation)
  const [columnOrder, setColumnOrder] = useState<string[]>(() =>
    reconcileOrder(loadStoredOrder() ?? DEFAULT_ORDER, FIXED_COLUMNS.map((c) => c.id))
  );

  useEffect(() => {
    const allIds = allColumns.map((c) => c.id);
    setColumnOrder((prev) => reconcileOrder(prev, allIds));
  }, [allColumns]);

  const orderedColumns: ColumnDef[] = useMemo(() => {
    const byId = new Map(allColumns.map((c) => [c.id, c]));
    return columnOrder.map((id) => byId.get(id)).filter(Boolean) as ColumnDef[];
  }, [columnOrder, allColumns]);

  // ---- drag-and-drop reordering --------------------------------------------

  const [dragId, setDragId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);

  const onHeaderDragStart = (id: string) => (e: React.DragEvent<HTMLTableCellElement>) => {
    setDragId(id);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", id);
  };
  const onHeaderDragOver = (id: string) => (e: React.DragEvent<HTMLTableCellElement>) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setOverId(id);
  };
  const onHeaderDragLeave = () => setOverId(null);
  const onHeaderDrop = (targetId: string) => (e: React.DragEvent<HTMLTableCellElement>) => {
    e.preventDefault();
    const sourceId = e.dataTransfer.getData("text/plain") || dragId;
    setDragId(null); setOverId(null);
    if (!sourceId || sourceId === targetId) return;
    setColumnOrder((prev) => {
      const next = prev.filter((id) => id !== sourceId);
      const targetIdx = next.indexOf(targetId);
      if (targetIdx < 0) return prev;
      next.splice(targetIdx, 0, sourceId);
      saveStoredOrder(next);
      return next;
    });
  };

  // ---- header / cell renderers ---------------------------------------------

  const allOnPageSelected = companies.length > 0 && companies.every((c) => selectedIds.has(c.id));
  const showAllMatchingBanner =
    allOnPageSelected && total > companies.length && !selectAllMatching;

  // Total visible columns: 3 leading (checkbox, #, ID) + ordered + 1 (action menu) + 1 (+ add column)
  const visibleColCount = 3 + orderedColumns.length + 2;

  return (
    <div className="rounded-md border bg-card">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b text-xs">
        <div className="relative flex-1 max-w-sm">
          <Search className="h-3.5 w-3.5 text-muted-foreground absolute left-2.5 top-1/2 -translate-y-1/2" />
          <Input
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Cerca per nome…"
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
          <span>{orderedColumns.length} columns</span>
          <span>·</span>
          <span>{total.toLocaleString("it-IT")} rows</span>
          <button
            className="ml-2 text-[10px] uppercase tracking-wider hover:text-foreground"
            title="Ripristina ordine colonne di default"
            onClick={() => {
              const allIds = allColumns.map((c) => c.id);
              const fresh = reconcileOrder(DEFAULT_ORDER, allIds);
              setColumnOrder(fresh);
              saveStoredOrder(fresh);
            }}
          >
            reset order
          </button>
        </div>
      </div>

      {/* Cross-page selection banner */}
      {showAllMatchingBanner && (
        <div className="flex items-center justify-center gap-3 px-3 py-1.5 text-xs bg-amber-50 border-b border-amber-200">
          <span>Hai selezionato {selectedIds.size} aziende in questa pagina.</span>
          <button
            className="font-medium text-amber-900 hover:underline"
            onClick={() => onSelectAllMatching?.(true)}
          >
            Seleziona tutte le {total.toLocaleString("it-IT")} aziende che rispettano i filtri
          </button>
        </div>
      )}
      {selectAllMatching && (
        <div className="flex items-center justify-center gap-3 px-3 py-1.5 text-xs bg-primary/10 border-b border-primary/20">
          <span className="font-medium">
            Tutte le {total.toLocaleString("it-IT")} aziende che rispettano i filtri sono selezionate.
          </span>
          <button className="text-primary hover:underline" onClick={() => onSelectAllMatching?.(false)}>
            Deseleziona
          </button>
        </div>
      )}

      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              {/* Fixed leading columns: checkbox, #, ID */}
              <TableHead className="w-[40px] py-1.5">
                <Checkbox checked={allOnPageSelected} onCheckedChange={onToggleSelectAll} />
              </TableHead>
              <TableHead className="w-[40px] text-center text-[10px] font-mono text-muted-foreground py-1.5">#</TableHead>
              <TableHead className="w-[60px] py-1.5">
                <span className="text-[10px] font-mono text-muted-foreground">ID</span>
              </TableHead>

              {/* Reorderable columns */}
              {orderedColumns.map((col) => (
                <TableHead
                  key={col.id}
                  draggable
                  onDragStart={onHeaderDragStart(col.id)}
                  onDragOver={onHeaderDragOver(col.id)}
                  onDragLeave={onHeaderDragLeave}
                  onDrop={onHeaderDrop(col.id)}
                  onDragEnd={() => { setDragId(null); setOverId(null); }}
                  className={
                    "py-1.5 cursor-grab active:cursor-grabbing select-none " +
                    (overId === col.id && dragId !== col.id ? "bg-primary/5 border-l-2 border-primary " : "") +
                    (dragId === col.id ? "opacity-50 " : "") +
                    (col.align === "right" ? "text-right " : col.align === "center" ? "text-center " : "")
                  }
                >
                  <div className={
                    "flex items-center gap-1.5 group/header " +
                    (col.align === "right" ? "justify-end" : col.align === "center" ? "justify-center" : "")
                  }>
                    <GripVertical className="h-3 w-3 text-muted-foreground/40 opacity-0 group-hover/header:opacity-100 transition-opacity" />
                    <TypeIcon kind={col.iconKind} />
                    <span className="text-xs font-medium">{col.label}</span>
                  </div>
                </TableHead>
              ))}

              {/* + Add column */}
              <TableHead className="w-[40px] text-center py-1.5">
                <Button
                  variant="ghost" size="icon" className="h-6 w-6"
                  title="Aggiungi colonna custom"
                  onClick={onAddCustomFieldKey}
                >
                  <Plus className="h-3.5 w-3.5" />
                </Button>
              </TableHead>
              {/* Trailing action-menu column header (kept narrow, no label) */}
              <TableHead className="w-[40px] py-1.5" />
            </TableRow>
          </TableHeader>

          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={visibleColCount} className="text-center py-6 text-muted-foreground text-sm">
                  <Loader2 className="h-4 w-4 animate-spin inline mr-2" /> Caricamento…
                </TableCell>
              </TableRow>
            ) : companies.length === 0 ? (
              <TableRow>
                <TableCell colSpan={visibleColCount} className="text-center py-12 text-muted-foreground text-sm">
                  Nessuna azienda. Importa un CSV per iniziare.
                </TableCell>
              </TableRow>
            ) : companies.map((c, idx) => {
              const rowNum = pageIndex * rowsPerPage + idx + 1;
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
                  <TableCell className="py-1.5">
                    <button
                      type="button"
                      className="font-mono text-[10px] text-muted-foreground hover:text-primary hover:underline"
                      title={`Click per copiare l'account_id ${c.id}`}
                      onClick={(e) => { e.stopPropagation(); navigator.clipboard?.writeText(String(c.id)); }}
                    >
                      {c.id}
                    </button>
                  </TableCell>

                  {orderedColumns.map((col) => (
                    <TableCell
                      key={col.id}
                      className={
                        "py-1.5 " +
                        (col.align === "right" ? "text-right " : col.align === "center" ? "text-center " : "") +
                        (col.maxWidth ? "" : "")
                      }
                      style={col.maxWidth ? { maxWidth: col.maxWidth } : undefined}
                    >
                      {col.renderCell(c, ctx)}
                    </TableCell>
                  ))}

                  {/* placeholder cell aligned with "+ Add column" header */}
                  <TableCell className="py-1.5" />
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
