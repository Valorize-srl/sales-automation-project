"use client";

import { useState } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { Download, Upload, Loader2 } from "lucide-react";

interface ToolResultsTableProps {
  results: Record<string, unknown>[];
  columns: { key: string; label: string }[];
  onImport: (selected: Record<string, unknown>[], importType: "people" | "companies") => void;
  onExportCsv: (selected: Record<string, unknown>[]) => void;
  importType?: "people" | "companies";
  importing?: boolean;
}

export function ToolResultsTable({
  results,
  columns,
  onImport,
  onExportCsv,
  importType = "people",
  importing = false,
}: ToolResultsTableProps) {
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const toggleAll = () => {
    if (selected.size === results.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(results.map((_, i) => i)));
    }
  };

  const toggle = (idx: number) => {
    const next = new Set(selected);
    if (next.has(idx)) next.delete(idx);
    else next.add(idx);
    setSelected(next);
  };

  const selectedItems = results.filter((_, i) => selected.has(i));

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {results.length} risultati{selected.size > 0 && ` (${selected.size} selezionati)`}
        </p>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={selected.size === 0}
            onClick={() => onExportCsv(selectedItems)}
            className="gap-1 text-xs"
          >
            <Download className="h-3 w-3" />
            CSV
          </Button>
          <Button
            size="sm"
            disabled={selected.size === 0 || importing}
            onClick={() => onImport(selectedItems, importType)}
            className="gap-1 text-xs"
          >
            {importing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Upload className="h-3 w-3" />}
            Importa {selected.size > 0 ? selected.size : ""} in {importType === "people" ? "People" : "Companies"}
          </Button>
        </div>
      </div>

      <div className="border rounded-md overflow-auto max-h-[400px]">
        <table className="w-full text-xs">
          <thead className="bg-muted/50 sticky top-0">
            <tr>
              <th className="p-2 w-8">
                <Checkbox
                  checked={selected.size === results.length && results.length > 0}
                  onCheckedChange={toggleAll}
                />
              </th>
              {columns.map((col) => (
                <th key={col.key} className="p-2 text-left font-medium text-muted-foreground">
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.map((row, idx) => (
              <tr
                key={idx}
                className={`border-t hover:bg-muted/30 ${selected.has(idx) ? "bg-primary/5" : ""}`}
              >
                <td className="p-2">
                  <Checkbox checked={selected.has(idx)} onCheckedChange={() => toggle(idx)} />
                </td>
                {columns.map((col) => (
                  <td key={col.key} className="p-2 max-w-[200px] truncate">
                    {String(row[col.key] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
