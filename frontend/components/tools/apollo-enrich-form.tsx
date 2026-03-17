"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Loader2, Zap } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

interface PersonRow {
  id: number;
  first_name: string;
  last_name: string;
  email: string | null;
  company_name: string | null;
  phone: string | null;
}

interface Props {
  clientTag?: string;
}

export function ApolloEnrichForm({ clientTag }: Props) {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [enriching, setEnriching] = useState(false);
  const [people, setPeople] = useState<PersonRow[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [search, setSearch] = useState("");

  const loadPeople = async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = { limit: "50" };
      if (search) params.search = search;
      if (clientTag) params.client_tag = clientTag;
      const data = await api.getPeople(params);
      setPeople(
        (data.people || []).map((p: any) => ({
          id: p.id,
          first_name: p.first_name,
          last_name: p.last_name,
          email: p.email,
          company_name: p.company_name,
          phone: p.phone,
        }))
      );
    } catch {
      toast({ title: "Errore caricamento contatti", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPeople();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleAll = () => {
    if (selected.size === people.length) setSelected(new Set());
    else setSelected(new Set(people.map((p) => p.id)));
  };

  const toggle = (id: number) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  };

  const handleEnrich = async () => {
    if (selected.size === 0) return;
    setEnriching(true);
    try {
      const result = await api.toolsEnrichPeople(Array.from(selected), clientTag);
      toast({
        title: "Arricchimento completato",
        description: result.message,
      });
      setSelected(new Set());
      await loadPeople();
    } catch (err: any) {
      toast({ title: "Errore", description: err?.message || "Arricchimento fallito", variant: "destructive" });
    } finally {
      setEnriching(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Input
          placeholder="Cerca per nome o email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && loadPeople()}
          className="flex-1"
        />
        <Button variant="outline" onClick={loadPeople} disabled={loading} size="sm">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Cerca"}
        </Button>
      </div>

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {people.length} contatti{selected.size > 0 && ` (${selected.size} selezionati)`}
        </p>
        <Button onClick={handleEnrich} disabled={selected.size === 0 || enriching} className="gap-1" size="sm">
          {enriching ? <Loader2 className="h-3 w-3 animate-spin" /> : <Zap className="h-3 w-3" />}
          Arricchisci {selected.size > 0 ? `${selected.size}` : ""} con Apollo
        </Button>
      </div>

      <p className="text-xs text-muted-foreground">1 credito Apollo per contatto. Aggiunge email, telefono, LinkedIn.</p>

      <div className="border rounded-md overflow-auto max-h-[350px]">
        <table className="w-full text-xs">
          <thead className="bg-muted/50 sticky top-0">
            <tr>
              <th className="p-2 w-8">
                <Checkbox checked={selected.size === people.length && people.length > 0} onCheckedChange={toggleAll} />
              </th>
              <th className="p-2 text-left font-medium">Nome</th>
              <th className="p-2 text-left font-medium">Azienda</th>
              <th className="p-2 text-left font-medium">Email</th>
              <th className="p-2 text-left font-medium">Telefono</th>
            </tr>
          </thead>
          <tbody>
            {people.map((p) => (
              <tr key={p.id} className={`border-t hover:bg-muted/30 ${selected.has(p.id) ? "bg-primary/5" : ""}`}>
                <td className="p-2">
                  <Checkbox checked={selected.has(p.id)} onCheckedChange={() => toggle(p.id)} />
                </td>
                <td className="p-2">{p.first_name} {p.last_name}</td>
                <td className="p-2 max-w-[150px] truncate">{p.company_name || ""}</td>
                <td className="p-2 max-w-[180px] truncate">{p.email || ""}</td>
                <td className="p-2">{p.phone || ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
