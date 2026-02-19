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
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { CSVColumnMapper } from "./csv-column-mapper";
import { CSVPreviewTable } from "./csv-preview-table";
import { api } from "@/lib/api";
import {
  ICP,
  CSVColumnMapping,
  CSVUploadResponse,
  CSVImportResponse,
} from "@/types";

interface CSVUploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  icps: ICP[];
  onImportComplete: () => void;
}

export function CSVUploadDialog({
  open,
  onOpenChange,
  icps,
  onImportComplete,
}: CSVUploadDialogProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [selectedIcpId, setSelectedIcpId] = useState<string>("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadData, setUploadData] = useState<CSVUploadResponse | null>(null);
  const emptyMapping: CSVColumnMapping = {
    first_name: null, last_name: null, email: null, company: null,
    job_title: null, industry: null, linkedin_url: null, phone: null, address: null,
    city: null, state: null, zip_code: null, country: null, website: null,
  };
  const [mapping, setMapping] = useState<CSVColumnMapping>(emptyMapping);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<CSVImportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setStep(1);
    setSelectedIcpId("");
    setFile(null);
    setUploading(false);
    setUploadData(null);
    setMapping(emptyMapping);
    setImporting(false);
    setImportResult(null);
    setError(null);
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) reset();
    onOpenChange(open);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      setFile(selected);
      setError(null);
    }
    e.target.value = "";
  };

  const handleUpload = async () => {
    if (!file || !selectedIcpId) return;
    setUploading(true);
    setError(null);
    try {
      const data = await api.uploadCSV(file);
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
    if (!uploadData || !selectedIcpId || !mapping.email) return;
    setImporting(true);
    setError(null);
    try {
      const result = await api.post<CSVImportResponse>("/leads/csv/import", {
        icp_id: parseInt(selectedIcpId),
        mapping,
        rows: uploadData.rows,
      });
      setImportResult(result);
      setStep(4);
      onImportComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>
            {step === 1 && "Import CSV — Step 1: Upload"}
            {step === 2 && "Import CSV — Step 2: Column Mapping"}
            {step === 3 && "Import CSV — Step 3: Preview"}
            {step === 4 && "Import Complete"}
          </DialogTitle>
        </DialogHeader>
        <Separator />

        {/* Step 1: Select ICP + Upload File */}
        {step === 1 && (
          <div className="space-y-4 pt-2">
            <div>
              <Label>Target ICP</Label>
              <Select value={selectedIcpId} onValueChange={setSelectedIcpId}>
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="Select an ICP..." />
                </SelectTrigger>
                <SelectContent>
                  {icps.map((icp) => (
                    <SelectItem key={icp.id} value={String(icp.id)}>
                      {icp.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label>CSV File</Label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={handleFileChange}
              />
              <div className="mt-1 flex items-center gap-2">
                <Button
                  variant="outline"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  className="gap-1"
                >
                  <Upload className="h-4 w-4" />
                  Choose File
                </Button>
                {file && (
                  <Badge variant="secondary">{file.name}</Badge>
                )}
              </div>
            </div>

            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}

            <div className="flex justify-end">
              <Button
                onClick={handleUpload}
                disabled={!file || !selectedIcpId || uploading}
                className="gap-1"
              >
                {uploading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ArrowRight className="h-4 w-4" />
                )}
                {uploading ? "Mapping columns..." : "Upload & Map"}
              </Button>
            </div>
          </div>
        )}

        {/* Step 2: Column Mapping */}
        {step === 2 && uploadData && (
          <div className="space-y-4 pt-2">
            <CSVColumnMapper
              headers={uploadData.headers}
              mapping={mapping}
              onMappingChange={setMapping}
              sampleRow={uploadData.preview_rows[0] || null}
            />

            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(1)} className="gap-1">
                <ArrowLeft className="h-4 w-4" />
                Back
              </Button>
              <Button
                onClick={() => {
                  if (!mapping.email) {
                    setError("Email column mapping is required");
                    return;
                  }
                  setError(null);
                  setStep(3);
                }}
                className="gap-1"
              >
                <ArrowRight className="h-4 w-4" />
                Preview
              </Button>
            </div>
          </div>
        )}

        {/* Step 3: Preview & Confirm */}
        {step === 3 && uploadData && (
          <div className="space-y-4 pt-2">
            <CSVPreviewTable
              mapping={mapping}
              rows={uploadData.preview_rows}
              totalRows={uploadData.total_rows}
            />

            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(2)} className="gap-1">
                <ArrowLeft className="h-4 w-4" />
                Back
              </Button>
              <Button
                onClick={handleImport}
                disabled={importing}
                className="gap-1"
              >
                {importing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Check className="h-4 w-4" />
                )}
                {importing ? "Importing..." : `Import ${uploadData.total_rows} Leads`}
              </Button>
            </div>
          </div>
        )}

        {/* Step 4: Result */}
        {step === 4 && importResult && (
          <div className="space-y-4 pt-2 text-center">
            <div className="py-4">
              <div className="mx-auto w-12 h-12 rounded-full bg-green-100 flex items-center justify-center mb-3">
                <Check className="h-6 w-6 text-green-600" />
              </div>
              <p className="text-lg font-medium">Import Successful</p>
            </div>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-2xl font-bold text-green-600">{importResult.imported}</p>
                <p className="text-muted-foreground">Imported</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-yellow-600">{importResult.duplicates_skipped}</p>
                <p className="text-muted-foreground">Duplicates</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-red-600">{importResult.errors}</p>
                <p className="text-muted-foreground">Errors</p>
              </div>
            </div>
            <Button onClick={() => handleOpenChange(false)} className="mt-4">
              Done
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
