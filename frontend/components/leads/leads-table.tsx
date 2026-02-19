"use client";

import { Trash2 } from "lucide-react";
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
import { Lead } from "@/types";

interface LeadsTableProps {
  leads: Lead[];
  onDelete: (id: number) => void;
  loading: boolean;
}

const sourceColors: Record<string, string> = {
  csv: "bg-blue-100 text-blue-800",
  manual: "bg-gray-100 text-gray-800",
  apollo: "bg-purple-100 text-purple-800",
};

export function LeadsTable({ leads, onDelete, loading }: LeadsTableProps) {
  if (loading) {
    return <p className="text-muted-foreground py-8 text-center">Loading...</p>;
  }

  if (leads.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">
          No leads yet. Import a CSV to get started.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-md border overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Company</TableHead>
            <TableHead>Job Title</TableHead>
            <TableHead>Industry</TableHead>
            <TableHead>Phone</TableHead>
            <TableHead>Address</TableHead>
            <TableHead>City</TableHead>
            <TableHead>State</TableHead>
            <TableHead>ZIP Code</TableHead>
            <TableHead>Country</TableHead>
            <TableHead>Website</TableHead>
            <TableHead>LinkedIn</TableHead>
            <TableHead>Source</TableHead>
            <TableHead className="w-[50px]"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {leads.map((lead) => (
            <TableRow key={lead.id}>
              <TableCell className="font-medium whitespace-nowrap">
                {lead.first_name} {lead.last_name}
              </TableCell>
              <TableCell>{lead.email}</TableCell>
              <TableCell>{lead.company || "—"}</TableCell>
              <TableCell>{lead.job_title || "—"}</TableCell>
              <TableCell>{lead.industry || "—"}</TableCell>
              <TableCell>{lead.phone || "—"}</TableCell>
              <TableCell>{lead.address || "—"}</TableCell>
              <TableCell>{lead.city || "—"}</TableCell>
              <TableCell>{lead.state || "—"}</TableCell>
              <TableCell>{lead.zip_code || "—"}</TableCell>
              <TableCell>{lead.country || "—"}</TableCell>
              <TableCell>
                {lead.website ? (
                  <a
                    href={lead.website.startsWith("http") ? lead.website : `https://${lead.website}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline truncate max-w-[150px] block"
                  >
                    {lead.website}
                  </a>
                ) : "—"}
              </TableCell>
              <TableCell>
                {lead.linkedin_url ? (
                  <a
                    href={lead.linkedin_url.startsWith("http") ? lead.linkedin_url : `https://${lead.linkedin_url}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline truncate max-w-[150px] block"
                  >
                    LinkedIn
                  </a>
                ) : "—"}
              </TableCell>
              <TableCell>
                <Badge
                  variant="outline"
                  className={sourceColors[lead.source] || ""}
                >
                  {lead.source}
                </Badge>
              </TableCell>
              <TableCell>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-destructive"
                  onClick={() => onDelete(lead.id)}
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
