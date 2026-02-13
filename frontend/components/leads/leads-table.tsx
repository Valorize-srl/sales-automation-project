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
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Company</TableHead>
            <TableHead>Job Title</TableHead>
            <TableHead>Source</TableHead>
            <TableHead className="w-[50px]"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {leads.map((lead) => (
            <TableRow key={lead.id}>
              <TableCell className="font-medium">
                {lead.first_name} {lead.last_name}
              </TableCell>
              <TableCell>{lead.email}</TableCell>
              <TableCell>{lead.company || "—"}</TableCell>
              <TableCell>{lead.job_title || "—"}</TableCell>
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
