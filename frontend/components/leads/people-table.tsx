"use client";

import { Trash2, ExternalLink, Trophy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Person } from "@/types";

interface PeopleTableProps {
  people: Person[];
  loading: boolean;
  selectedIds: Set<number>;
  onToggleSelect: (id: number) => void;
  onToggleSelectAll: () => void;
  onDelete: (id: number) => void;
  onCompanyClick: (companyId: number) => void;
  onEdit: (person: Person) => void;
  onPersonClick?: (person: Person) => void;
  onToggleConverted: (person: Person) => void;
}

export function PeopleTable({
  people,
  loading,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
  onDelete,
  onCompanyClick,
  onEdit,
  onToggleConverted,
  onPersonClick,
}: PeopleTableProps) {
  if (loading) {
    return <p className="text-muted-foreground py-8 text-center">Loading...</p>;
  }

  if (people.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">
          No people yet. Import a CSV to get started.
        </p>
      </div>
    );
  }

  const allSelected = people.length > 0 && people.every((p) => selectedIds.has(p.id));
  const someSelected = people.some((p) => selectedIds.has(p.id));

  return (
    <div className="rounded-md border overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[40px]">
              <Checkbox
                checked={allSelected}
                onCheckedChange={onToggleSelectAll}
                aria-label="Select all"
                className={someSelected && !allSelected ? "opacity-50" : ""}
              />
            </TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Company</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>LinkedIn</TableHead>
            <TableHead>Phone</TableHead>
            <TableHead>Industry</TableHead>
            <TableHead>Location</TableHead>
            <TableHead>Client/Project</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="w-[50px]"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {people.map((person) => (
            <TableRow
              key={person.id}
              className={selectedIds.has(person.id) ? "bg-primary/5" : ""}
            >
              <TableCell>
                <Checkbox
                  checked={selectedIds.has(person.id)}
                  onCheckedChange={() => onToggleSelect(person.id)}
                  aria-label={`Select ${person.first_name} ${person.last_name}`}
                />
              </TableCell>
              <TableCell className="font-medium">
                <button
                  className="text-primary hover:underline text-left"
                  onClick={() => (onPersonClick ?? onEdit)(person)}
                >
                  {person.first_name} {person.last_name}
                </button>
              </TableCell>
              <TableCell>
                {person.company_id ? (
                  <button
                    className="text-primary text-sm hover:underline font-medium"
                    onClick={() => onCompanyClick(person.company_id!)}
                  >
                    {person.company_name || "\u2014"}
                  </button>
                ) : (
                  <span className="text-sm text-muted-foreground">
                    {person.company_name || "\u2014"}
                  </span>
                )}
              </TableCell>
              <TableCell className="text-sm">{person.email}</TableCell>
              <TableCell>
                {person.linkedin_url ? (
                  <a
                    href={person.linkedin_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline flex items-center gap-1 text-sm"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <ExternalLink className="h-3 w-3" />
                    LinkedIn
                  </a>
                ) : (
                  <span className="text-muted-foreground text-sm">{"\u2014"}</span>
                )}
              </TableCell>
              <TableCell className="text-sm">{person.phone || "\u2014"}</TableCell>
              <TableCell className="text-sm">{person.industry || "\u2014"}</TableCell>
              <TableCell className="text-sm">{person.location || "\u2014"}</TableCell>
              <TableCell className="text-sm">
                {person.client_tag ? (
                  <div className="flex flex-wrap gap-1">
                    {person.client_tag.split(",").map((tag) => tag.trim()).filter(Boolean).map((tag) => (
                      <Badge key={tag} variant="secondary" className="text-[10px] px-1.5 py-0">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  "\u2014"
                )}
              </TableCell>
              <TableCell>
                <button
                  onClick={() => onToggleConverted(person)}
                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium border transition-colors ${
                    person.converted_at
                      ? "bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100"
                      : "bg-muted text-muted-foreground border-transparent hover:bg-accent"
                  }`}
                  title={person.converted_at ? "Click to remove conversion" : "Click to mark as converted"}
                >
                  <Trophy className="h-3 w-3" />
                  {person.converted_at ? "Converted" : "—"}
                </button>
              </TableCell>
              <TableCell>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-destructive hover:text-destructive"
                  onClick={() => onDelete(person.id)}
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
