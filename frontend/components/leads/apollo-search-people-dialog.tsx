"use client";

import { useEffect, useState } from "react";
import {
  Users, Loader2, Search, Linkedin, Mail, MapPin, Briefcase,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import type { LeadList, ToolSearchResponse } from "@/types";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Refresh the lead lists sidebar + companies table after import. */
  onCompleted?: () => void;
}

const SENIORITY_OPTIONS = [
  { value: "c_suite", label: "C-Suite" },
  { value: "vp", label: "VP" },
  { value: "director", label: "Director" },
  { value: "manager", label: "Manager" },
  { value: "senior", label: "Senior" },
  { value: "owner", label: "Owner" },
  { value: "founder", label: "Founder" },
];

const NEW_LIST_VALUE = "__new__";

export function ApolloSearchPeopleDialog({ open, onOpenChange, onCompleted }: Props) {
  // Filters
  const [titles, setTitles] = useState("");
  const [locations, setLocations] = useState("");
  const [seniorities, setSeniorities] = useState<string[]>([]);
  const [orgKeywords, setOrgKeywords] = useState("");
  const [orgSizes, setOrgSizes] = useState("");
  const [perPage, setPerPage] = useState(25);

  // Destination list
  const [allLists, setAllLists] = useState<LeadList[]>([]);
  const [listChoice, setListChoice] = useState<string>(""); // "", "<id>", or NEW_LIST_VALUE
  const [newListName, setNewListName] = useState("");

  // Search state
  const [searching, setSearching] = useState(false);
  const [importing, setImporting] = useState(false);
  const [results, setResults] = useState<ToolSearchResponse | null>(null);
  const [selectedIdx, setSelectedIdx] = useState<Set<number>>(new Set());

  // Load lead lists when opening
  useEffect(() => {
    if (!open) return;
    api.listLeadLists()
      .then((r) => setAllLists(r.lists || []))
      .catch(() => setAllLists([]));
  }, [open]);

  const reset = () => {
    setResults(null);
    setSelectedIdx(new Set());
    setSearching(false);
    setImporting(false);
  };

  const handleOpen = (isOpen: boolean) => {
    if (!isOpen) {
      reset();
      setTitles("");
      setLocations("");
      setSeniorities([]);
      setOrgKeywords("");
      setOrgSizes("");
      setListChoice("");
      setNewListName("");
    }
    onOpenChange(isOpen);
  };

  const toggleSeniority = (s: string) =>
    setSeniorities((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]));

  const split = (s: string) =>
    s.split(/[,\n;]+/).map((t) => t.trim()).filter(Boolean);

  const titlesParsed = split(titles);
  const locsParsed = split(locations);
  const canSearch =
    !searching &&
    (titlesParsed.length > 0 || locsParsed.length > 0 || seniorities.length > 0 || orgKeywords.trim().length > 0);

  const handleSearch = async () => {
    if (!canSearch) return;
    setSearching(true);
    setResults(null);
    setSelectedIdx(new Set());
    try {
      const data = await api.toolsSearchPeople({
        person_titles: titlesParsed.length ? titlesParsed : undefined,
        person_locations: locsParsed.length ? locsParsed : undefined,
        person_seniorities: seniorities.length ? seniorities : undefined,
        organization_keywords: orgKeywords ? split(orgKeywords) : undefined,
        organization_sizes: orgSizes ? split(orgSizes) : undefined,
        per_page: Math.max(1, Math.min(100, perPage)),
      });
      setResults(data);
      // Preselect all results — user can de-tick what they don't want.
      setSelectedIdx(new Set(data.results.map((_, i) => i)));
    } catch (e) {
      alert(`Errore ricerca Apollo: ${e instanceof Error ? e.message : e}`);
    } finally {
      setSearching(false);
    }
  };

  const toggleRow = (idx: number) =>
    setSelectedIdx((prev) => {
      const n = new Set(prev);
      if (n.has(idx)) n.delete(idx); else n.add(idx);
      return n;
    });

  const toggleAll = () => {
    if (!results) return;
    if (selectedIdx.size === results.results.length) setSelectedIdx(new Set());
    else setSelectedIdx(new Set(results.results.map((_, i) => i)));
  };

  /** Resolve `listChoice` + `newListName` to a concrete list_id, creating
   * the list on the fly if the user chose "+ nuova lista". Returns null if
   * no destination was specified (caller imports into the unlisted pool). */
  const resolveTargetListId = async (): Promise<number | null> => {
    if (listChoice === NEW_LIST_VALUE) {
      const name = newListName.trim();
      if (!name) {
        alert("Inserisci un nome per la nuova lista");
        throw new Error("missing_name");
      }
      const created = await api.createLeadList({ name });
      return created.id;
    }
    if (listChoice && listChoice !== "") return parseInt(listChoice, 10);
    return null;
  };

  const handleImport = async () => {
    if (!results || selectedIdx.size === 0) return;
    setImporting(true);
    try {
      const listId = await resolveTargetListId();
      const items = Array.from(selectedIdx).sort((a, b) => a - b).map((i) => results.results[i]);
      await api.toolsImportLeads({
        results: items as Record<string, unknown>[],
        import_type: "people",
        list_id: listId ?? undefined,
      });
      onCompleted?.();
      handleOpen(false);
    } catch (e) {
      if (e instanceof Error && e.message === "missing_name") return; // already alerted
      alert(`Errore import: ${e instanceof Error ? e.message : e}`);
    } finally {
      setImporting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogContent className="sm:max-w-[780px] max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Users className="h-5 w-5 text-purple-600" />
            Cerca nuove persone
            <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-purple-100 text-purple-800 border border-purple-200">
              Apollo
            </span>
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-4 flex-1 overflow-hidden">
          {!results && (
            <div className="space-y-3">
              <div className="rounded-md border bg-muted/40 p-3 text-xs text-muted-foreground">
                <p>
                  Cerca decision maker su Apollo per ruolo, location, seniorità o settore aziendale.
                  I risultati vengono importati come <strong>Person</strong> nella lead list scelta.
                </p>
                <p className="mt-1.5">
                  Costo: <span className="font-medium">1 credito Apollo per contatto restituito</span>.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs">Job title <span className="text-muted-foreground">(virgola)</span></Label>
                  <Input
                    placeholder="es. CEO, CTO, Sales Director"
                    value={titles}
                    onChange={(e) => setTitles(e.target.value)}
                    className="mt-1 text-sm"
                  />
                </div>
                <div>
                  <Label className="text-xs">Location <span className="text-muted-foreground">(virgola)</span></Label>
                  <Input
                    placeholder="es. Italy, Milan"
                    value={locations}
                    onChange={(e) => setLocations(e.target.value)}
                    className="mt-1 text-sm"
                  />
                </div>
                <div>
                  <Label className="text-xs">Settore azienda <span className="text-muted-foreground">(keyword)</span></Label>
                  <Input
                    placeholder="es. software, fintech, hospitality"
                    value={orgKeywords}
                    onChange={(e) => setOrgKeywords(e.target.value)}
                    className="mt-1 text-sm"
                  />
                </div>
                <div>
                  <Label className="text-xs">Dimensione azienda <span className="text-muted-foreground">(employee bands)</span></Label>
                  <Input
                    placeholder="es. 1-10, 11-50, 51-200"
                    value={orgSizes}
                    onChange={(e) => setOrgSizes(e.target.value)}
                    className="mt-1 text-sm"
                  />
                </div>
              </div>

              <div>
                <Label className="text-xs">Seniority</Label>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {SENIORITY_OPTIONS.map((s) => (
                    <button
                      key={s.value}
                      type="button"
                      onClick={() => toggleSeniority(s.value)}
                      className={`px-2.5 py-1 rounded-md text-xs border transition-colors ${
                        seniorities.includes(s.value)
                          ? "bg-purple-600 text-white border-purple-600"
                          : "bg-background hover:bg-muted border-input"
                      }`}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs">Lista di destinazione</Label>
                  <select
                    value={listChoice}
                    onChange={(e) => setListChoice(e.target.value)}
                    className="mt-1 w-full h-9 px-2 text-sm rounded-md border border-input bg-background"
                  >
                    <option value="">Nessuna (pool senza lista)</option>
                    {allLists.map((ll) => (
                      <option key={ll.id} value={String(ll.id)}>
                        {ll.name} ({ll.companies_count ?? 0})
                      </option>
                    ))}
                    <option value={NEW_LIST_VALUE}>+ Nuova lista…</option>
                  </select>
                </div>
                <div>
                  <Label className="text-xs">Max risultati <span className="text-muted-foreground">(1–100)</span></Label>
                  <Input
                    type="number"
                    min={1}
                    max={100}
                    value={perPage}
                    onChange={(e) => setPerPage(parseInt(e.target.value, 10) || 25)}
                    className="mt-1 text-sm h-9"
                  />
                </div>
              </div>

              {listChoice === NEW_LIST_VALUE && (
                <div>
                  <Label className="text-xs">Nome della nuova lista</Label>
                  <Input
                    placeholder="es. CEOs fintech Milano"
                    value={newListName}
                    onChange={(e) => setNewListName(e.target.value)}
                    className="mt-1 text-sm"
                    autoFocus
                  />
                </div>
              )}

              <Button
                onClick={handleSearch}
                disabled={!canSearch}
                className="gap-2 bg-purple-600 hover:bg-purple-700 text-white"
              >
                {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                {searching ? "Ricerca in corso…" : "Cerca su Apollo"}
              </Button>
            </div>
          )}

          {results && (
            <>
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>
                  <strong className="text-foreground">{results.total}</strong> risultati totali — mostrati {results.results.length}
                  {results.credits_used > 0 && (
                    <> · <strong>{results.credits_used}</strong> crediti consumati (${results.cost_usd.toFixed(2)})</>
                  )}
                </span>
                <button
                  onClick={() => setResults(null)}
                  className="text-primary hover:underline"
                >
                  ← nuova ricerca
                </button>
              </div>

              <div className="flex-1 overflow-y-auto border rounded-md">
                <table className="w-full text-sm">
                  <thead className="bg-muted/40 sticky top-0">
                    <tr className="text-left">
                      <th className="px-2 py-1.5 w-8">
                        <input
                          type="checkbox"
                          checked={selectedIdx.size === results.results.length}
                          onChange={toggleAll}
                          className="h-4 w-4"
                        />
                      </th>
                      <th className="px-2 py-1.5">Nome</th>
                      <th className="px-2 py-1.5">Ruolo</th>
                      <th className="px-2 py-1.5">Azienda</th>
                      <th className="px-2 py-1.5">Email</th>
                      <th className="px-2 py-1.5">Località</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.results.map((p, i) => (
                      <tr
                        key={i}
                        className={`border-t hover:bg-accent/30 cursor-pointer ${
                          selectedIdx.has(i) ? "bg-accent/40" : ""
                        }`}
                        onClick={() => toggleRow(i)}
                      >
                        <td className="px-2 py-1.5">
                          <input
                            type="checkbox"
                            checked={selectedIdx.has(i)}
                            onChange={() => toggleRow(i)}
                            onClick={(e) => e.stopPropagation()}
                            className="h-4 w-4"
                          />
                        </td>
                        <td className="px-2 py-1.5 font-medium">
                          {String(p.first_name || "")} {String(p.last_name || "")}
                        </td>
                        <td className="px-2 py-1.5 text-xs text-muted-foreground">
                          {p.title ? (
                            <span className="inline-flex items-center gap-1">
                              <Briefcase className="h-3 w-3" /> {String(p.title)}
                            </span>
                          ) : "—"}
                        </td>
                        <td className="px-2 py-1.5">{String(p.company || "—")}</td>
                        <td className="px-2 py-1.5">
                          {p.email ? (
                            <a
                              href={`mailto:${p.email}`}
                              className="text-emerald-700 hover:underline inline-flex items-center gap-1"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <Mail className="h-3 w-3" /> {String(p.email)}
                            </a>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </td>
                        <td className="px-2 py-1.5 text-xs text-muted-foreground">
                          {p.location ? (
                            <span className="inline-flex items-center gap-1">
                              <MapPin className="h-3 w-3" /> {String(p.location)}
                            </span>
                          ) : "—"}
                          {p.linkedin_url ? (
                            <a
                              href={String(p.linkedin_url)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="ml-1 text-[#0A66C2] hover:underline inline-flex items-center"
                              onClick={(e) => e.stopPropagation()}
                              title="LinkedIn"
                            >
                              <Linkedin className="h-3 w-3" />
                            </a>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="border-t pt-3 flex items-center justify-between gap-3 shrink-0">
                <div className="text-sm text-muted-foreground">
                  <Badge variant="secondary" className="mr-2">{selectedIdx.size} selezionati</Badge>
                  {listChoice === NEW_LIST_VALUE && newListName.trim() ? (
                    <>→ verranno creati in <strong>{newListName.trim()}</strong></>
                  ) : listChoice && listChoice !== "" ? (
                    <>→ lista <strong>{allLists.find((ll) => String(ll.id) === listChoice)?.name}</strong></>
                  ) : (
                    <>→ pool senza lista</>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" onClick={() => handleOpen(false)}>Annulla</Button>
                  <Button
                    size="sm"
                    onClick={handleImport}
                    disabled={importing || selectedIdx.size === 0}
                    className="gap-1.5 bg-purple-600 hover:bg-purple-700 text-white"
                  >
                    {importing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Users className="h-3.5 w-3.5" />}
                    {importing ? "Importazione…" : `Importa ${selectedIdx.size}`}
                  </Button>
                </div>
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
