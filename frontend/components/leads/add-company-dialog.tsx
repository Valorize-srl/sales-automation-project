"use client";

import { useEffect, useState } from "react";
import { Building2, Loader2, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import type { LeadList } from "@/types";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Refresh the companies table + lists sidebar after a successful create. */
  onCompleted?: () => void;
}

const NEW_LIST_VALUE = "__new__";

export function AddCompanyDialog({ open, onOpenChange, onCompleted }: Props) {
  const [name, setName] = useState("");
  const [website, setWebsite] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [industry, setIndustry] = useState("");
  const [location, setLocation] = useState("");
  const [province, setProvince] = useState("");
  const [zipCode, setZipCode] = useState("");
  const [employeeCount, setEmployeeCount] = useState("");
  const [revenue, setRevenue] = useState("");
  const [vatNumber, setVatNumber] = useState("");
  const [taxId, setTaxId] = useState("");
  const [notes, setNotes] = useState("");

  // Destination list
  const [allLists, setAllLists] = useState<LeadList[]>([]);
  const [listChoice, setListChoice] = useState<string>(""); // "", "<id>", or NEW_LIST_VALUE
  const [newListName, setNewListName] = useState("");

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load lists when opening
  useEffect(() => {
    if (!open) return;
    api.listLeadLists()
      .then((r) => setAllLists(r.lists || []))
      .catch(() => setAllLists([]));
  }, [open]);

  const reset = () => {
    setName(""); setWebsite(""); setLinkedinUrl(""); setEmail(""); setPhone("");
    setIndustry(""); setLocation(""); setProvince(""); setZipCode("");
    setEmployeeCount(""); setRevenue("");
    setVatNumber(""); setTaxId("");
    setNotes(""); setListChoice(""); setNewListName("");
    setSaving(false); setError(null);
  };

  const handleOpen = (isOpen: boolean) => {
    if (!isOpen) reset();
    onOpenChange(isOpen);
  };

  const canSave = name.trim().length > 0 && !saving;

  const resolveListId = async (): Promise<number | null> => {
    if (listChoice === NEW_LIST_VALUE) {
      const lname = newListName.trim();
      if (!lname) {
        setError("Inserisci un nome per la nuova lista");
        throw new Error("missing_list_name");
      }
      const created = await api.createLeadList({ name: lname });
      return created.id;
    }
    if (listChoice) return parseInt(listChoice, 10);
    return null;
  };

  const handleSave = async () => {
    if (!canSave) return;
    setSaving(true);
    setError(null);
    try {
      // Resolve target list FIRST so a list-creation failure doesn't leave
      // an orphan company.
      let listId: number | null = null;
      try {
        listId = await resolveListId();
      } catch (e) {
        if (e instanceof Error && e.message === "missing_list_name") {
          setSaving(false);
          return;
        }
        throw e;
      }

      const company = await api.createCompany({
        name: name.trim(),
        website: website.trim() || null,
        linkedin_url: linkedinUrl.trim() || null,
        email: email.trim() || null,
        phone: phone.trim() || null,
        industry: industry.trim() || null,
        location: location.trim() || null,
        province: province.trim() || null,
        zip_code: zipCode.trim() || null,
        employee_count: employeeCount.trim() ? parseInt(employeeCount, 10) : null,
        revenue: revenue.trim() ? parseInt(revenue.replace(/[^\d]/g, ""), 10) : null,
        vat_number: vatNumber.trim() || null,
        tax_id: taxId.trim() || null,
        // Manual entries always have a null source — this distinguishes them
        // from rows imported from Seikoo (which carry the Seikoo UUID).
        source_company_id: null,
        notes: notes.trim() || null,
      });

      if (listId) {
        try {
          await api.addCompaniesToList(listId, [company.id]);
        } catch (e) {
          console.warn("Could not attach company to list:", e);
        }
      }

      onCompleted?.();
      handleOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Errore durante il salvataggio");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpen}>
      <DialogContent className="sm:max-w-[640px] max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-primary" />
            Aggiungi azienda
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto pr-1 space-y-4">
          <div>
            <Label className="text-xs">Nome azienda <span className="text-destructive">*</span></Label>
            <Input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="es. Acme S.r.l."
              className="mt-1"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">Sito web</Label>
              <Input
                value={website}
                onChange={(e) => setWebsite(e.target.value)}
                placeholder="https://acme.it"
                className="mt-1 text-sm"
              />
            </div>
            <div>
              <Label className="text-xs">LinkedIn azienda</Label>
              <Input
                value={linkedinUrl}
                onChange={(e) => setLinkedinUrl(e.target.value)}
                placeholder="https://linkedin.com/company/acme"
                className="mt-1 text-sm"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">Email generica</Label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="info@acme.it"
                className="mt-1 text-sm"
              />
            </div>
            <div>
              <Label className="text-xs">Telefono</Label>
              <Input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+39 02 1234567"
                className="mt-1 text-sm"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">Settore</Label>
              <Input
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                placeholder="es. SaaS, Hospitality"
                className="mt-1 text-sm"
              />
            </div>
            <div>
              <Label className="text-xs">Provincia (sigla)</Label>
              <Input
                value={province}
                onChange={(e) => setProvince(e.target.value)}
                placeholder="MI"
                maxLength={10}
                className="mt-1 text-sm"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label className="text-xs">Città</Label>
              <Input
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Milano"
                className="mt-1 text-sm"
              />
            </div>
            <div>
              <Label className="text-xs">CAP</Label>
              <Input
                value={zipCode}
                onChange={(e) => setZipCode(e.target.value)}
                placeholder="20100"
                maxLength={20}
                className="mt-1 text-sm"
              />
            </div>
            <div>
              <Label className="text-xs">Dipendenti</Label>
              <Input
                type="number"
                min={0}
                value={employeeCount}
                onChange={(e) => setEmployeeCount(e.target.value)}
                placeholder="50"
                className="mt-1 text-sm"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label className="text-xs">Fatturato (€)</Label>
              <Input
                value={revenue}
                onChange={(e) => setRevenue(e.target.value)}
                placeholder="1000000"
                className="mt-1 text-sm"
              />
            </div>
            <div>
              <Label className="text-xs">P.IVA</Label>
              <Input
                value={vatNumber}
                onChange={(e) => setVatNumber(e.target.value)}
                placeholder="12345678901"
                maxLength={32}
                className="mt-1 text-sm"
              />
            </div>
            <div>
              <Label className="text-xs">Codice Fiscale</Label>
              <Input
                value={taxId}
                onChange={(e) => setTaxId(e.target.value)}
                placeholder="RSSMRA80A01H501Z"
                maxLength={32}
                className="mt-1 text-sm"
              />
            </div>
          </div>

          <p className="text-[10px] text-muted-foreground -mt-2">
            Le aziende create da qui vengono marcate come <strong>origine manuale</strong> (nessun ID Seikoo).
          </p>

          <div>
            <Label className="text-xs">Note</Label>
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Note interne…"
              rows={2}
              className="mt-1 text-sm"
            />
          </div>

          <div>
            <Label className="text-xs">Aggiungi a lista (opzionale)</Label>
            <select
              value={listChoice}
              onChange={(e) => setListChoice(e.target.value)}
              className="mt-1 w-full h-9 px-2 text-sm rounded-md border border-input bg-background"
            >
              <option value="">Nessuna lista</option>
              {allLists.map((ll) => (
                <option key={ll.id} value={String(ll.id)}>
                  {ll.name} ({ll.companies_count ?? 0})
                </option>
              ))}
              <option value={NEW_LIST_VALUE}>+ Nuova lista…</option>
            </select>
            {listChoice === NEW_LIST_VALUE && (
              <Input
                placeholder="Nome della nuova lista"
                value={newListName}
                onChange={(e) => setNewListName(e.target.value)}
                className="mt-2 text-sm"
              />
            )}
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </div>

        <div className="border-t pt-3 flex items-center justify-between gap-3 shrink-0">
          <p className="text-xs text-muted-foreground">
            Il nome è obbligatorio. Tutto il resto puoi compilarlo dopo.
          </p>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => handleOpen(false)}>
              Annulla
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              disabled={!canSave}
              className="gap-1.5"
            >
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
              {saving ? "Salvo…" : "Salva azienda"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
