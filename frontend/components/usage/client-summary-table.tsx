"use client";

import { ClientSummaryResponse } from "@/types";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { format } from "date-fns";

interface ClientSummaryTableProps {
  data: ClientSummaryResponse;
  onClientClick?: (clientTag: string) => void;
}

export default function ClientSummaryTable({ data, onClientClick }: ClientSummaryTableProps) {
  if (data.clients.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground text-sm">
        No client data yet. Tag your sessions and searches with a client name to track costs.
      </div>
    );
  }

  return (
    <div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Client / Project</TableHead>
            <TableHead className="text-right">Sessions</TableHead>
            <TableHead className="text-right">Searches</TableHead>
            <TableHead className="text-right">Apollo Credits</TableHead>
            <TableHead className="text-right">Claude Tokens</TableHead>
            <TableHead className="text-right">Apollo Cost</TableHead>
            <TableHead className="text-right">Claude Cost</TableHead>
            <TableHead className="text-right">Total Cost</TableHead>
            <TableHead className="text-right">Last Activity</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.clients.map((client) => (
            <TableRow
              key={client.client_tag}
              className={onClientClick ? "cursor-pointer hover:bg-muted/50" : ""}
              onClick={() => onClientClick?.(client.client_tag)}
            >
              <TableCell>
                <Badge variant="outline" className="font-medium">
                  {client.client_tag}
                </Badge>
              </TableCell>
              <TableCell className="text-right">{client.total_sessions}</TableCell>
              <TableCell className="text-right">{client.total_searches}</TableCell>
              <TableCell className="text-right">{client.total_apollo_credits}</TableCell>
              <TableCell className="text-right text-xs">
                {((client.total_claude_input_tokens + client.total_claude_output_tokens) / 1000).toFixed(1)}k
              </TableCell>
              <TableCell className="text-right">${client.cost_apollo_usd.toFixed(2)}</TableCell>
              <TableCell className="text-right">${client.cost_claude_usd.toFixed(2)}</TableCell>
              <TableCell className="text-right font-semibold">${client.total_cost_usd.toFixed(2)}</TableCell>
              <TableCell className="text-right text-xs text-muted-foreground">
                {client.last_activity
                  ? format(new Date(client.last_activity), "dd/MM/yyyy")
                  : "—"}
              </TableCell>
            </TableRow>
          ))}
          {/* Totals row */}
          <TableRow className="bg-muted/30 font-semibold">
            <TableCell>
              Totale ({data.totals.total_clients} clienti)
            </TableCell>
            <TableCell className="text-right">—</TableCell>
            <TableCell className="text-right">—</TableCell>
            <TableCell className="text-right">{data.totals.total_apollo_credits}</TableCell>
            <TableCell className="text-right text-xs">
              {(data.totals.total_claude_tokens / 1000).toFixed(1)}k
            </TableCell>
            <TableCell className="text-right">—</TableCell>
            <TableCell className="text-right">—</TableCell>
            <TableCell className="text-right">${data.totals.total_cost_usd.toFixed(2)}</TableCell>
            <TableCell />
          </TableRow>
        </TableBody>
      </Table>
    </div>
  );
}
