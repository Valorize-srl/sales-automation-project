"use client";

import { useState, useEffect } from "react";
import { Play, XCircle, RefreshCw, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";
import type { PipelineRun, PipelineRunStatus, AIAgent } from "@/types";

const STATUS_COLORS: Record<PipelineRunStatus, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  running: "bg-blue-100 text-blue-800",
  paused: "bg-orange-100 text-orange-800",
  completed: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  cancelled: "bg-gray-100 text-gray-800",
};

const STEP_LABELS: Record<number, string> = {
  0: "Not started",
  1: "Scraping portals",
  2: "ICP filtering",
  3: "LinkedIn company",
  4: "Finding DM",
  5: "Finding emails",
  6: "Verifying emails",
  7: "Collecting signals",
  8: "Claude scoring",
  9: "Push to Instantly",
};

export default function PipelinePage() {
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [showNewDialog, setShowNewDialog] = useState(false);
  const [agents, setAgents] = useState<AIAgent[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadRuns();
  }, [filterStatus]);

  const loadRuns = async () => {
    try {
      const params: { status?: string } = {};
      if (filterStatus !== "all") params.status = filterStatus;
      const data = await api.getPipelineRuns(params);
      setRuns(data.runs);
      setTotal(data.total);
    } catch (error) {
      console.error("Failed to load pipeline runs:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadAgents = async () => {
    try {
      const data = await api.getAIAgents();
      setAgents(data.agents.filter((a: AIAgent) => a.is_active));
    } catch (error) {
      console.error("Failed to load agents:", error);
    }
  };

  const handleNewPipeline = () => {
    loadAgents();
    setSelectedAgentId("");
    setShowNewDialog(true);
  };

  const handleStartRun = async () => {
    if (!selectedAgentId) return;
    const agent = agents.find((a) => a.id === Number(selectedAgentId));
    if (!agent) return;

    setCreating(true);
    try {
      await api.startPipelineRun({
        ai_agent_id: agent.id,
        client_tag: agent.client_tag,
      });
      setShowNewDialog(false);
      loadRuns();
    } catch (error) {
      console.error("Failed to start pipeline:", error);
    } finally {
      setCreating(false);
    }
  };

  const handleCancel = async (runId: string) => {
    try {
      await api.cancelPipelineRun(runId);
      loadRuns();
    } catch (error) {
      console.error("Failed to cancel run:", error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-48px)]">
        <p className="text-muted-foreground">Loading pipeline runs...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Pipeline</h1>
          <p className="text-muted-foreground">
            Waterfall lead generation pipeline — {total} run{total !== 1 ? "s" : ""}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder="Filter status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="running">Running</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
              <SelectItem value="cancelled">Cancelled</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={() => { setLoading(true); loadRuns(); }} variant="outline" size="icon">
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button onClick={handleNewPipeline}>
            <Play className="h-4 w-4 mr-2" />
            New Pipeline
          </Button>
        </div>
      </div>

      {runs.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No Pipeline Runs</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground mb-4">
              Start a new pipeline run to begin prospecting leads for a client.
            </p>
            <Button onClick={handleNewPipeline}>
              <Play className="h-4 w-4 mr-2" />
              Start First Pipeline
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {runs.map((run) => (
            <Card key={run.id}>
              <CardContent className="py-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono text-sm text-muted-foreground">
                          {run.run_id.slice(0, 8)}
                        </span>
                        <Badge className={STATUS_COLORS[run.status]}>
                          {run.status}
                        </Badge>
                        <Badge variant="outline">{run.client_tag}</Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        Step {run.current_step}/9: {STEP_LABELS[run.current_step] || "Unknown"}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    {/* Counters */}
                    <div className="grid grid-cols-3 gap-x-4 gap-y-1 text-sm text-right">
                      <div>
                        <span className="text-muted-foreground">Raw: </span>
                        <span className="font-medium">{run.leads_raw_count}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Filtered: </span>
                        <span className="font-medium">{run.leads_filtered_count}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Verified: </span>
                        <span className="font-medium">{run.leads_verified_count}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Scored: </span>
                        <span className="font-medium">{run.leads_scored_count}</span>
                      </div>
                      <div>
                        <span className="text-green-600 font-medium">A: {run.leads_score_a}</span>
                        {" / "}
                        <span className="text-yellow-600 font-medium">B: {run.leads_score_b}</span>
                        {" / "}
                        <span className="text-orange-600 font-medium">C: {run.leads_score_c}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Cost: </span>
                        <span className="font-medium">${run.cost_total_usd.toFixed(2)}</span>
                      </div>
                    </div>

                    {/* Actions */}
                    {(run.status === "pending" || run.status === "running") && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleCancel(run.run_id)}
                      >
                        <XCircle className="h-4 w-4 mr-1" />
                        Cancel
                      </Button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* New Pipeline Dialog */}
      <Dialog open={showNewDialog} onOpenChange={setShowNewDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Start New Pipeline Run</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <label className="text-sm font-medium mb-2 block">AI Agent</label>
              <Select value={selectedAgentId} onValueChange={setSelectedAgentId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select an AI Agent" />
                </SelectTrigger>
                <SelectContent>
                  {agents.map((agent) => (
                    <SelectItem key={agent.id} value={String(agent.id)}>
                      {agent.name} ({agent.client_tag})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {selectedAgentId && (() => {
              const agent = agents.find((a) => a.id === Number(selectedAgentId));
              return agent ? (
                <div className="rounded-md border p-3 text-sm space-y-1">
                  <p><strong>Client:</strong> {agent.client_tag}</p>
                  {agent.icp_config.industry && <p><strong>Industry:</strong> {agent.icp_config.industry}</p>}
                  {agent.icp_config.geography && <p><strong>Geography:</strong> {agent.icp_config.geography}</p>}
                </div>
              ) : null;
            })()}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowNewDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleStartRun} disabled={!selectedAgentId || creating}>
              {creating && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Start Pipeline
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
