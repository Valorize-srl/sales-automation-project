"use client";

import { useRef, useState } from "react";
import { Upload, Loader2, ArrowRight, ArrowLeft, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api";
import { PersonCSVMapping, PersonCSVUploadResponse } from "@/types";

const PERSON_FIELDS: { key: keyof PersonCSVMapping; label: string; required?: boolean }[] = [
  { key: "email", label: "Email", required: true },
  { key: "first_name", label: "First Name" },
  { key: "last_name", label: "Last Name" },
  { key: "company_name", label: "Company" },
  { key: "linkedin_url", label: "LinkedIn" },
  { key: "phone", label: "Phone" },
  { key: "industry", label: "Industry" },
  { key: "location", label: "Location" },
];

const EMPTY_MAPPING: PersonCSVMapping = {
  first_name: null, last_name: null, company_name: null, email: null,
  linkedin_url: null, phone: null, industry: null, location: null,
};

interface PeopleCSVDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImportComplete: () => void;
}

export function PeopleCSVDialog({ open, onOpenChange, onImportComplete }: PeopleCSVDialogProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadData, setUploadData] = useState<PersonCSVUploadResponse | null>(null);
  const [mapping, setMapping] = useState<PersonCSVMapping>(EMPTY_MAPPING);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{ imported: number; duplicates_skipped: number; errors: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setStep(1); setFile(null); setUploading(false);
    setUploadData(null); setMapping(EMPTY_MAPPING);
    setImporting(false); setImportResult(null); setError(null);
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) reset();
    onOpenChange(open);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const data = await api.uploadPeopleCSV(file);
      setUploadData(data);
      setMapping(data.mapping);
      setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleImport = async () => {
    if (!uploadData || !mapping.email) return;
    setImporting(true);
    setError(null);
    try {
      const result = await api.post<{ imported: number; duplicates_skipped: number; errors: number }>(
        "/people/csv/import",
        { mapping, rows: uploadData.rows }
      );
      setImportResult(result);
      setStep(4);
      onImportComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(false);
    }
  };

  const headerOptions = uploadData?.headers ?? [];

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>
            {step === 1 && "Import People — Step 1: Upload"}
            {step === 2 && "Import People — Step 2: Column Mapping"}
            {step === 3 && "Import People — Step 3: Preview"}
            {step === 4 && "Import Complete"}
          </DialogTitle>
        </DialogHeader>
        <Separator />

        {step === 1 && (
          <div className="space-y-4 pt-2">
            <div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={(e) => { setFile(e.target.files?.[0] ?? null); e.target.value = ""; }}
              />
              <div className="flex items-center gap-2">
                <Button variant="outline" onClick={() => fileInputRef.current?.click()} disabled={uploading} className="gap-1">
                  <Upload className="h-4 w-4" />
                  Choose CSV File
                </Button>
                {file && <Badge variant="secondary">{file.name}</Badge>}
              </div>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex justify-end">
              <Button onClick={handleUpload} disabled={!file || uploading} className="gap-1">
                {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
                {uploading ? "Mapping columns..." : "Upload & Map"}
              </Button>
            </div>
          </div>
        )}

        {step === 2 && uploadData && (
          <div className="space-y-3 pt-2">
            <p className="text-sm text-muted-foreground">{uploadData.total_rows} rows found. Map CSV columns to fields:</p>
            <div className="space-y-2 max-h-[320px] overflow-y-auto pr-1">
              {PERSON_FIELDS.map(({ key, label, required }) => (
                <div key={key} className="grid grid-cols-3 items-center gap-2">
                  <span className="text-sm font-medium">
                    {label}{required && <span className="text-destructive ml-1">*</span>}
                  </span>
                  <Select
                    value={mapping[key] ?? "__none__"}
                    onValueChange={(v) => setMapping((m) => ({ ...m, [key]: v === "__none__" ? null : v }))}
                  >
                    <SelectTrigger className="col-span-1 text-xs h-8">
                      <SelectValue placeholder="— skip —" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">— skip —</SelectItem>
                      {headerOptions.map((h) => (
                        <SelectItem key={h} value={h}>{h}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <span className="text-xs text-muted-foreground truncate">
                    {mapping[key] ? (uploadData.preview_rows[0]?.[mapping[key]!] ?? "") : ""}
                  </span>
                </div>
              ))}
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex justify-between pt-1">
              <Button variant="outline" onClick={() => setStep(1)} className="gap-1">
                <ArrowLeft className="h-4 w-4" /> Back
              </Button>
              <Button onClick={() => { if (!mapping.email) { setError("Email is required"); return; } setError(null); setStep(3); }} className="gap-1">
                <ArrowRight className="h-4 w-4" /> Preview
              </Button>
            </div>
          </div>
        )}

        {step === 3 && uploadData && (
          <div className="space-y-4 pt-2">
            <p className="text-sm text-muted-foreground">Preview of first 5 rows ({uploadData.total_rows} total):</p>
            <div className="overflow-x-auto rounded border">
              <table className="text-xs w-full">
                <thead className="bg-muted">
                  <tr>
                    {PERSON_FIELDS.filter((f) => mapping[f.key]).map((f) => (
                      <th key={f.key} className="px-2 py-1 text-left font-medium">{f.label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {uploadData.preview_rows.map((row, i) => (
                    <tr key={i} className="border-t">
                      {PERSON_FIELDS.filter((f) => mapping[f.key]).map((f) => (
                        <td key={f.key} className="px-2 py-1 truncate max-w-[120px]">
                          {row[mapping[f.key]!] || "—"}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(2)} className="gap-1">
                <ArrowLeft className="h-4 w-4" /> Back
              </Button>
              <Button onClick={handleImport} disabled={importing} className="gap-1">
                {importing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                {importing ? "Importing..." : `Import ${uploadData.total_rows} People`}
              </Button>
            </div>
          </div>
        )}

        {step === 4 && importResult && (
          <div className="space-y-4 pt-2 text-center">
            <div className="py-4">
              <div className="mx-auto w-12 h-12 rounded-full bg-green-100 flex items-center justify-center mb-3">
                <Check className="h-6 w-6 text-green-600" />
              </div>
              <p className="text-lg font-medium">Import Successful</p>
            </div>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div><p className="text-2xl font-bold text-green-600">{importResult.imported}</p><p className="text-muted-foreground">Imported</p></div>
              <div><p className="text-2xl font-bold text-yellow-600">{importResult.duplicates_skipped}</p><p className="text-muted-foreground">Duplicates</p></div>
              <div><p className="text-2xl font-bold text-red-600">{importResult.errors}</p><p className="text-muted-foreground">Errors</p></div>
            </div>
            <Button onClick={() => handleOpenChange(false)} className="mt-4">Done</Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
