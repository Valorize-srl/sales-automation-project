"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { CSVColumnMapping } from "@/types";

interface CSVPreviewTableProps {
  mapping: CSVColumnMapping;
  rows: Record<string, string>[];
  totalRows: number;
}

const COLUMNS: { key: keyof CSVColumnMapping; label: string }[] = [
  { key: "first_name", label: "First Name" },
  { key: "last_name", label: "Last Name" },
  { key: "email", label: "Email" },
  { key: "company", label: "Company" },
  { key: "job_title", label: "Job Title" },
];

export function CSVPreviewTable({ mapping, rows, totalRows }: CSVPreviewTableProps) {
  const previewRows = rows.slice(0, 5);
  const mappedColumns = COLUMNS.filter((col) => mapping[col.key]);

  const getValue = (row: Record<string, string>, field: keyof CSVColumnMapping) => {
    const col = mapping[field];
    if (!col) return "";
    return row[col] || "";
  };

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Preview of the first {previewRows.length} rows (out of {totalRows} total).
      </p>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {mappedColumns.map((col) => (
                <TableHead key={col.key}>{col.label}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {previewRows.map((row, i) => (
              <TableRow key={i}>
                {mappedColumns.map((col) => (
                  <TableCell key={col.key}>
                    {getValue(row, col.key) || "—"}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {totalRows > 5 && (
        <p className="text-sm text-muted-foreground text-center">
          ... and {totalRows - 5} more rows
        </p>
      )}
    </div>
  );
}
