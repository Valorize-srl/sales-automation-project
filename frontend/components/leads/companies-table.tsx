"use client";

import { Trash2, ExternalLink, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Company } from "@/types";

interface CompaniesTableProps {
  companies: Company[];
  loading: boolean;
  onDelete: (id: number) => void;
  onPeopleClick: (companyId: number) => void;
}

export function CompaniesTable({ companies, loading, onDelete, onPeopleClick }: CompaniesTableProps) {
  if (loading) {
    return <p className="text-muted-foreground py-8 text-center">Loading...</p>;
  }

  if (companies.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">
          No companies yet. Import a CSV to get started.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-md border overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Company</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Phone</TableHead>
            <TableHead>LinkedIn</TableHead>
            <TableHead>Industry</TableHead>
            <TableHead>Location</TableHead>
            <TableHead>Signals</TableHead>
            <TableHead>Client/Project</TableHead>
            <TableHead className="text-center">People</TableHead>
            <TableHead className="w-[50px]"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {companies.map((company) => (
            <TableRow key={company.id}>
              <TableCell className="font-medium">{company.name}</TableCell>
              <TableCell className="text-sm">{company.email || "—"}</TableCell>
              <TableCell className="text-sm">{company.phone || "—"}</TableCell>
              <TableCell>
                {company.linkedin_url ? (
                  <a
                    href={company.linkedin_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline flex items-center gap-1 text-sm"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <ExternalLink className="h-3 w-3" />
                    LinkedIn
                  </a>
                ) : (
                  <span className="text-muted-foreground text-sm">—</span>
                )}
              </TableCell>
              <TableCell className="text-sm">{company.industry || "—"}</TableCell>
              <TableCell className="text-sm">{company.location || "—"}</TableCell>
              <TableCell className="max-w-[200px]">
                {company.signals ? (
                  <p className="text-sm truncate" title={company.signals}>
                    {company.signals}
                  </p>
                ) : (
                  <span className="text-muted-foreground text-sm">—</span>
                )}
              </TableCell>
              <TableCell className="text-sm">{company.client_tag || "—"}</TableCell>
              <TableCell className="text-center">
                {company.people_count > 0 ? (
                  <button onClick={() => onPeopleClick(company.id)}>
                    <Badge
                      variant="outline"
                      className="cursor-pointer hover:bg-accent gap-1"
                    >
                      <Users className="h-3 w-3" />
                      {company.people_count}
                    </Badge>
                  </button>
                ) : (
                  <span className="text-muted-foreground text-sm">—</span>
                )}
              </TableCell>
              <TableCell>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-destructive hover:text-destructive"
                  onClick={() => onDelete(company.id)}
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
