"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Sparkles, Trash2, Check, X as Cancel, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import { EnrichmentTask, EnrichmentTaskStatus } from "@/types";
import { PaginationControls } from "@/components/ui/pagination-controls";

const TASK_TYPE_LABELS: Record<string, string> = {
  firmographic_base: "Firmographic",
  hiring_scrape: "Hiring",
  funding_lookup: "Funding",
  techstack_lookup: "Tech Stack",
  contact_discovery: "Contacts",
};

const STATUS_BADGE: Record<EnrichmentTaskStatus, string> = {
  pending: "bg-amber-50 text-amber-700 border-amber-200",
  completed: "bg-emerald-50 text-emerald-700 border-emerald-200",
  failed: "bg-red-50 text-red-700 border-red-200",
  cancelled: "bg-muted text-muted-foreground",
};

export default function EnrichmentTasksPage() {
  const [tasks, setTasks] = useState<EnrichmentTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [filterTaskType, setFilterTaskType] = useState<string>("all");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.listEnrichmentTasks({
        status: filterStatus === "all" ? undefined : filterStatus,
        task_type: filterTaskType === "all" ? undefined : filterTaskType,
        page,
      });
      setTasks(r.tasks);
      setTotal(r.total);
      setTotalPages(r.total_pages);
    } catch (e) {
      console.error("Failed to load enrichment tasks:", e);
    } finally {
      setLoading(false);
    }
  }, [filterStatus, filterTaskType, page]);

  useEffect(() => { load(); }, [load]);

  const updateStatus = async (taskId: number, status: EnrichmentTaskStatus) => {
    try {
      await api.updateEnrichmentTask(taskId, { status });
      load();
    } catch (e) {
      console.error("Update failed:", e);
    }
  };

  const removeTask = async (taskId: number) => {
    if (!confirm("Eliminare questa task?")) return;
    try {
      await api.deleteEnrichmentTask(taskId);
      load();
    } catch (e) {
      console.error("Delete failed:", e);
    }
  };

  return (
    <div className="container mx-auto py-6 px-4 max-w-[1400px]">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-primary" />
            Enrichment Tasks
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Task generate dal Lead Planner & Scorer per arricchire i dati di account A/B
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Stato:</span>
          <Select value={filterStatus} onValueChange={(v) => { setFilterStatus(v); setPage(1); }}>
            <SelectTrigger className="w-[160px] h-8 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tutti</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
              <SelectItem value="cancelled">Cancelled</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Tipo:</span>
          <Select value={filterTaskType} onValueChange={(v) => { setFilterTaskType(v); setPage(1); }}>
            <SelectTrigger className="w-[180px] h-8 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tutti</SelectItem>
              <SelectItem value="firmographic_base">Firmographic</SelectItem>
              <SelectItem value="hiring_scrape">Hiring</SelectItem>
              <SelectItem value="funding_lookup">Funding</SelectItem>
              <SelectItem value="techstack_lookup">Tech Stack</SelectItem>
              <SelectItem value="contact_discovery">Contacts</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <span className="ml-auto text-xs text-muted-foreground">{total} task</span>
      </div>

      <div className="rounded-md border overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[80px] text-center">Priority</TableHead>
              <TableHead>Target</TableHead>
              <TableHead className="w-[140px]">Type</TableHead>
              <TableHead>Reason</TableHead>
              <TableHead className="w-[120px]">Status</TableHead>
              <TableHead className="w-[180px] text-right">Azione</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow><TableCell colSpan={6} className="text-center py-6 text-muted-foreground">Caricamento…</TableCell></TableRow>
            ) : tasks.length === 0 ? (
              <TableRow><TableCell colSpan={6} className="text-center py-12 text-muted-foreground">
                Nessuna task. Lancia uno scoring sulle Companies per generarne.
              </TableCell></TableRow>
            ) : (
              tasks.map((t) => (
                <TableRow key={t.id}>
                  <TableCell className="text-center">
                    <Badge variant="outline" className="font-mono text-xs">P{t.priority}</Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <span className="font-medium">{t.target_name || `${t.target_type} #${t.target_id}`}</span>
                      {t.target_type === "account" && (
                        <Link href="/leads" className="text-muted-foreground hover:text-primary">
                          <ExternalLink className="h-3 w-3" />
                        </Link>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="text-xs">
                      {TASK_TYPE_LABELS[t.task_type] || t.task_type}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground max-w-[400px]">
                    <p className="truncate" title={t.reason || undefined}>{t.reason || "—"}</p>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className={`text-xs ${STATUS_BADGE[t.status]}`}>{t.status}</Badge>
                  </TableCell>
                  <TableCell className="text-right space-x-1">
                    {t.status === "pending" && (
                      <>
                        <Button size="icon" variant="ghost" className="h-7 w-7"
                          title="Marca completata"
                          onClick={() => updateStatus(t.id, "completed")}>
                          <Check className="h-3.5 w-3.5 text-emerald-600" />
                        </Button>
                        <Button size="icon" variant="ghost" className="h-7 w-7"
                          title="Cancella task"
                          onClick={() => updateStatus(t.id, "cancelled")}>
                          <Cancel className="h-3.5 w-3.5 text-muted-foreground" />
                        </Button>
                      </>
                    )}
                    <Button size="icon" variant="ghost" className="h-7 w-7 text-destructive"
                      title="Elimina"
                      onClick={() => removeTask(t.id)}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <PaginationControls
          page={page}
          totalPages={totalPages}
          total={total}
          pageSize={50}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}
