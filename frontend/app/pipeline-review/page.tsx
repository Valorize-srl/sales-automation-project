"use client";

import { useState, useEffect, useCallback } from "react";
import {
  CheckCircle,
  XCircle,
  Clock,
  RefreshCw,
  Edit3,
  Save,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PaginationControls } from "@/components/ui/pagination-controls";
import { api } from "@/lib/api";
import type { PipelineLead } from "@/types";

const SCORE_COLORS: Record<string, string> = {
  A: "bg-green-100 text-green-800",
  B: "bg-yellow-100 text-yellow-800",
  C: "bg-orange-100 text-orange-800",
};

export default function PipelineReviewPage() {
  const [leads, setLeads] = useState<PipelineLead[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [scoreFilter, setScoreFilter] = useState<string>("all");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState("");
  const pageSize = 50;

  const loadQueue = useCallback(async () => {
    try {
      const params: { score?: string; page?: number; page_size?: number } = {
        page,
        page_size: pageSize,
      };
      if (scoreFilter !== "all") params.score = scoreFilter;
      const data = await api.getPipelineReviewQueue(params);
      setLeads(data.leads);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (error) {
      console.error("Failed to load review queue:", error);
    } finally {
      setLoading(false);
    }
  }, [page, scoreFilter]);

  useEffect(() => {
    setLoading(true);
    loadQueue();
  }, [loadQueue]);

  const handleApprove = async (leadId: number) => {
    try {
      await api.approvePipelineLead(leadId);
      loadQueue();
    } catch (error) {
      console.error("Failed to approve lead:", error);
    }
  };

  const handleDiscard = async (leadId: number) => {
    try {
      await api.discardPipelineLead(leadId);
      loadQueue();
    } catch (error) {
      console.error("Failed to discard lead:", error);
    }
  };

  const handlePostpone = async (leadId: number) => {
    try {
      await api.postponePipelineLead(leadId);
      loadQueue();
    } catch (error) {
      console.error("Failed to postpone lead:", error);
    }
  };

  const startEdit = (lead: PipelineLead) => {
    setEditingId(lead.id);
    setEditValue(lead.first_line_email || "");
  };

  const saveEdit = async () => {
    if (editingId === null) return;
    try {
      await api.editPipelineLeadFirstLine(editingId, editValue);
      setEditingId(null);
      loadQueue();
    } catch (error) {
      console.error("Failed to save first line:", error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-48px)]">
        <p className="text-muted-foreground">Loading review queue...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Review Queue</h1>
          <p className="text-muted-foreground">
            {total} lead{total !== 1 ? "s" : ""} awaiting review
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select
            value={scoreFilter}
            onValueChange={(v) => { setScoreFilter(v); setPage(1); }}
          >
            <SelectTrigger className="w-[140px]">
              <SelectValue placeholder="Filter score" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All scores</SelectItem>
              <SelectItem value="A">Score A</SelectItem>
              <SelectItem value="B">Score B</SelectItem>
              <SelectItem value="C">Score C</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={() => { setLoading(true); loadQueue(); }} variant="outline" size="icon">
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {leads.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No Leads in Review</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              Run a pipeline to generate scored leads for review.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Company</TableHead>
                    <TableHead>P.IVA</TableHead>
                    <TableHead>Decision Maker</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Score</TableHead>
                    <TableHead>First Line</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {leads.map((lead) => (
                    <TableRow key={lead.id}>
                      <TableCell>
                        <div>
                          <p className="font-medium">{lead.ragione_sociale || "—"}</p>
                          {lead.provincia && (
                            <p className="text-xs text-muted-foreground">{lead.provincia}</p>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        {lead.partita_iva || "—"}
                      </TableCell>
                      <TableCell>
                        {lead.dm_first_name ? (
                          <div>
                            <p className="text-sm">
                              {lead.dm_first_name} {lead.dm_last_name}
                            </p>
                            {lead.dm_job_title && (
                              <p className="text-xs text-muted-foreground">{lead.dm_job_title}</p>
                            )}
                          </div>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-sm">{lead.email || "—"}</TableCell>
                      <TableCell>
                        {lead.icp_score ? (
                          <Badge className={SCORE_COLORS[lead.icp_score] || ""}>
                            {lead.icp_score}
                          </Badge>
                        ) : (
                          "—"
                        )}
                      </TableCell>
                      <TableCell className="max-w-[250px]">
                        {editingId === lead.id ? (
                          <div className="flex items-start gap-1">
                            <Textarea
                              value={editValue}
                              onChange={(e) => setEditValue(e.target.value)}
                              className="text-sm min-h-[60px]"
                            />
                            <div className="flex flex-col gap-1">
                              <Button size="icon" variant="ghost" onClick={saveEdit}>
                                <Save className="h-3 w-3" />
                              </Button>
                              <Button size="icon" variant="ghost" onClick={() => setEditingId(null)}>
                                <X className="h-3 w-3" />
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <div
                            className="text-sm text-muted-foreground truncate cursor-pointer hover:text-foreground"
                            onClick={() => startEdit(lead)}
                            title={lead.first_line_email || "Click to add first line"}
                          >
                            {lead.first_line_email || (
                              <span className="flex items-center gap-1 text-xs">
                                <Edit3 className="h-3 w-3" /> Add first line
                              </span>
                            )}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            size="icon"
                            variant="ghost"
                            className="text-green-600 hover:text-green-700 hover:bg-green-50"
                            onClick={() => handleApprove(lead.id)}
                            title="Approve"
                          >
                            <CheckCircle className="h-4 w-4" />
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="text-orange-600 hover:text-orange-700 hover:bg-orange-50"
                            onClick={() => handlePostpone(lead.id)}
                            title="Postpone"
                          >
                            <Clock className="h-4 w-4" />
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="text-red-600 hover:text-red-700 hover:bg-red-50"
                            onClick={() => handleDiscard(lead.id)}
                            title="Discard"
                          >
                            <XCircle className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <PaginationControls
            page={page}
            totalPages={totalPages}
            total={total}
            pageSize={pageSize}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}
