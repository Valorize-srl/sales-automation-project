"use client";

import { Trash2, ExternalLink, Users, UserSearch } from "lucide-react";
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
import { Company } from "@/types";
import { EmailListDisplay } from "@/components/companies/email-list-display";
import { EnrichButton } from "@/components/companies/enrich-button";

interface CompaniesTableProps {
  companies: Company[];
  loading: boolean;
  selectedIds?: Set<number>;
  onToggleSelect?: (id: number) => void;
  onToggleSelectAll?: () => void;
  onDelete: (id: number) => void;
  onPeopleClick: (companyId: number) => void;
  onFindPeople?: (company: Company) => void;
  onRefresh?: () => void;
}

export function CompaniesTable({ companies, loading, selectedIds, onToggleSelect, onToggleSelectAll, onDelete, onPeopleClick, onFindPeople, onRefresh }: CompaniesTableProps) {
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
            {onToggleSelect && (
              <TableHead className="w-[40px]">
                <Checkbox
                  checked={companies.length > 0 && companies.every((c) => selectedIds?.has(c.id))}
                  onCheckedChange={onToggleSelectAll}
                />
              </TableHead>
            )}
            <TableHead>Company</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Phone</TableHead>
            <TableHead>LinkedIn</TableHead>
            <TableHead>Industry</TableHead>
            <TableHead>Location</TableHead>
            <TableHead>Signals</TableHead>
            <TableHead>Client/Project</TableHead>
            <TableHead className="text-center">People</TableHead>
            <TableHead>Actions</TableHead>
            <TableHead className="w-[50px]"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {companies.map((company) => (
            <TableRow key={company.id}>
              {onToggleSelect && (
                <TableCell>
                  <Checkbox
                    checked={selectedIds?.has(company.id)}
                    onCheckedChange={() => onToggleSelect(company.id)}
                  />
                </TableCell>
              )}
              <TableCell className="font-medium">{company.name}</TableCell>
              <TableCell className="text-sm">
                <EmailListDisplay
                  primaryEmail={company.email}
                  genericEmails={company.generic_emails}
                  enrichmentSource={company.enrichment_source}
                  enrichmentDate={company.enrichment_date}
                />
              </TableCell>
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
              <TableCell className="space-x-1">
                {onFindPeople && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-1 h-7 text-xs"
                    onClick={() => onFindPeople(company)}
                  >
                    <UserSearch className="h-3 w-3" />
                    Find People
                  </Button>
                )}
                {company.website && (
                  <EnrichButton
                    companyId={company.id}
                    onEnrichComplete={onRefresh}
                  />
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
