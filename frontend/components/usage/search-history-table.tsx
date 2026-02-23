import { SearchHistory } from "@/types";
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
import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

interface SearchHistoryTableProps {
  history: SearchHistory[];
}

export default function SearchHistoryTable({ history }: SearchHistoryTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  const toggleRow = (id: number) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  if (history.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No search history found for the selected filters.
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[50px]"></TableHead>
            <TableHead>Date/Time</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Client Tag</TableHead>
            <TableHead className="text-right">Results</TableHead>
            <TableHead className="text-right">Credits</TableHead>
            <TableHead className="text-right">Tokens</TableHead>
            <TableHead className="text-right">Cost (USD)</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {history.map((search) => {
            const isExpanded = expandedRows.has(search.id);
            return (
              <>
                <TableRow key={search.id} className="cursor-pointer hover:bg-muted/50">
                  <TableCell onClick={() => toggleRow(search.id)}>
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                  </TableCell>
                  <TableCell>
                    {format(new Date(search.created_at), "MMM d, yyyy HH:mm")}
                  </TableCell>
                  <TableCell>
                    <Badge variant={search.search_type === "people" ? "default" : "secondary"}>
                      {search.search_type}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {search.client_tag ? (
                      <span className="text-sm">{search.client_tag}</span>
                    ) : (
                      <span className="text-muted-foreground text-sm">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">{search.results_count}</TableCell>
                  <TableCell className="text-right">{search.apollo_credits_consumed}</TableCell>
                  <TableCell className="text-right">
                    {((search.claude_input_tokens + search.claude_output_tokens) / 1000).toFixed(1)}k
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    ${search.cost_total_usd.toFixed(4)}
                  </TableCell>
                </TableRow>

                {isExpanded && (
                  <TableRow>
                    <TableCell colSpan={8} className="bg-muted/30">
                      <div className="p-4 space-y-2">
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <p className="text-sm font-medium">Cost Breakdown</p>
                            <p className="text-sm text-muted-foreground">
                              Apollo: ${search.cost_apollo_usd.toFixed(4)}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              Claude: ${search.cost_claude_usd.toFixed(4)}
                            </p>
                          </div>
                          <div>
                            <p className="text-sm font-medium">Token Details</p>
                            <p className="text-sm text-muted-foreground">
                              Input: {search.claude_input_tokens.toLocaleString()}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              Output: {search.claude_output_tokens.toLocaleString()}
                            </p>
                          </div>
                        </div>
                        {search.search_query && (
                          <div>
                            <p className="text-sm font-medium">Search Query</p>
                            <p className="text-sm text-muted-foreground">{search.search_query}</p>
                          </div>
                        )}
                        {search.filters_applied && Object.keys(search.filters_applied).length > 0 && (
                          <div>
                            <p className="text-sm font-medium">Filters Applied</p>
                            <pre className="text-xs bg-muted p-2 rounded mt-1 overflow-auto max-h-40">
                              {JSON.stringify(search.filters_applied, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                )}
              </>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
