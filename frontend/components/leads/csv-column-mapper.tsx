"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { CSVColumnMapping } from "@/types";

interface CSVColumnMapperProps {
  headers: string[];
  mapping: CSVColumnMapping;
  onMappingChange: (mapping: CSVColumnMapping) => void;
  sampleRow: Record<string, string> | null;
}

const LEAD_FIELDS: { key: keyof CSVColumnMapping; label: string; required?: boolean }[] = [
  { key: "email", label: "Email", required: true },
  { key: "first_name", label: "First Name" },
  { key: "last_name", label: "Last Name" },
  { key: "company", label: "Company" },
  { key: "job_title", label: "Job Title" },
  { key: "industry", label: "Industry" },
  { key: "phone", label: "Phone" },
  { key: "address", label: "Address" },
  { key: "city", label: "City" },
  { key: "state", label: "State" },
  { key: "zip_code", label: "ZIP Code" },
  { key: "country", label: "Country" },
  { key: "website", label: "Website" },
  { key: "linkedin_url", label: "LinkedIn URL" },
];

const NOT_MAPPED = "__not_mapped__";

export function CSVColumnMapper({
  headers,
  mapping,
  onMappingChange,
  sampleRow,
}: CSVColumnMapperProps) {
  const updateField = (field: keyof CSVColumnMapping, value: string) => {
    onMappingChange({
      ...mapping,
      [field]: value === NOT_MAPPED ? null : value,
    });
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Review the column mapping below. Claude suggested these mappings based on your CSV headers.
      </p>
      <div className="space-y-3">
        {LEAD_FIELDS.map((field) => {
          const currentValue = mapping[field.key];
          const sampleValue = currentValue && sampleRow ? sampleRow[currentValue] : null;

          return (
            <div key={field.key} className="grid grid-cols-3 gap-3 items-center">
              <Label className={field.required && !currentValue ? "text-destructive" : ""}>
                {field.label}
                {field.required && <span className="text-destructive ml-1">*</span>}
              </Label>
              <Select
                value={currentValue || NOT_MAPPED}
                onValueChange={(v) => updateField(field.key, v)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Not mapped" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NOT_MAPPED}>Not mapped</SelectItem>
                  {headers.map((header) => (
                    <SelectItem key={header} value={header}>
                      {header}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <span className="text-sm text-muted-foreground truncate">
                {sampleValue || "—"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
