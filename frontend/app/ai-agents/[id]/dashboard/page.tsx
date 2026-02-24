"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Search, TrendingUp, Users, CreditCard, FileText, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";
import type { AIAgent, AIAgentStats } from "@/types";

export default function AIAgentDashboardPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const agentId = parseInt(params.id as string);

  const [agent, setAgent] = useState<AIAgent | null>(null);
  const [stats, setStats] = useState<AIAgentStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    loadAgent();
    loadStats();
  }, [agentId]);

  const loadAgent = async () => {
    try {
      const data = await api.getAIAgent(agentId);
      setAgent(data);
    } catch (error) {
      console.error("Failed to load agent:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const data = await api.getAIAgentStats(agentId);
      setStats(data);
    } catch (error) {
      console.error("Failed to load stats:", error);
    }
  };

  const handleApolloSearch = async () => {
    setSearching(true);
    try {
      const result = await api.executeApolloSearch(agentId, {
        per_page: 25,
        auto_create_list: true,
      });

      toast({
        title: "Success",
        description: `Found ${result.results_count} leads. Created list: ${result.list_name}`,
      });

      // Reload stats
      await loadStats();
      await loadAgent();
    } catch (error) {
      console.error("Apollo search error:", error);
      toast({
        title: "Error",
        description: "Failed to execute Apollo search",
        variant: "destructive",
      });
    } finally {
      setSearching(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Are you sure you want to delete "${agent?.name}"?`)) return;

    try {
      await api.deleteAIAgent(agentId);
      toast({
        title: "Success",
        description: "AI Agent deleted successfully",
      });
      router.push("/ai-agents");
    } catch (error) {
      console.error("Delete error:", error);
      toast({
        title: "Error",
        description: "Failed to delete agent",
        variant: "destructive",
      });
    }
  };

  if (loading || !agent) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-48px)]">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/ai-agents">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold">{agent.name}</h1>
              <Badge variant={agent.is_active ? "default" : "secondary"}>
                {agent.is_active ? "Active" : "Inactive"}
              </Badge>
            </div>
            <p className="text-muted-foreground">
              <Badge variant="outline">{agent.client_tag}</Badge>
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button onClick={handleApolloSearch} disabled={searching}>
            <Search className="h-4 w-4 mr-2" />
            {searching ? "Searching..." : "Apollo Search"}
          </Button>
          <Button variant="destructive" onClick={handleDelete}>
            <Trash2 className="h-4 w-4 mr-2" />
            Delete
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Leads</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_leads || 0}</div>
            <p className="text-xs text-muted-foreground">
              {stats?.total_people || 0} people, {stats?.total_companies || 0} companies
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Apollo Credits</CardTitle>
            <CreditCard className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{agent.credits_remaining}</div>
            <p className="text-xs text-muted-foreground">
              of {agent.apollo_credits_allocated} allocated
            </p>
            <Progress value={agent.credits_percentage_used} className="h-2 mt-2" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Lead Lists</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.lists_created || 0}</div>
            <p className="text-xs text-muted-foreground">Created by this agent</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Campaigns</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.campaigns_connected || 0}</div>
            <p className="text-xs text-muted-foreground">Connected for auto-reply</p>
          </CardContent>
        </Card>
      </div>

      {/* ICP Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>ICP Configuration</CardTitle>
          <CardDescription>Ideal Customer Profile settings</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-4">
            {agent.icp_config.industry && (
              <>
                <dt className="text-sm font-medium text-muted-foreground">Industry</dt>
                <dd className="text-sm">{agent.icp_config.industry}</dd>
              </>
            )}
            {agent.icp_config.company_size && (
              <>
                <dt className="text-sm font-medium text-muted-foreground">Company Size</dt>
                <dd className="text-sm">{agent.icp_config.company_size}</dd>
              </>
            )}
            {agent.icp_config.job_titles && (
              <>
                <dt className="text-sm font-medium text-muted-foreground">Job Titles</dt>
                <dd className="text-sm">{agent.icp_config.job_titles}</dd>
              </>
            )}
            {agent.icp_config.geography && (
              <>
                <dt className="text-sm font-medium text-muted-foreground">Geography</dt>
                <dd className="text-sm">{agent.icp_config.geography}</dd>
              </>
            )}
            {agent.icp_config.keywords && (
              <>
                <dt className="text-sm font-medium text-muted-foreground">Keywords</dt>
                <dd className="text-sm">{agent.icp_config.keywords}</dd>
              </>
            )}
          </dl>
        </CardContent>
      </Card>

      {/* Knowledge Base */}
      {agent.knowledge_base_text && (
        <Card>
          <CardHeader>
            <CardTitle>Knowledge Base</CardTitle>
            <CardDescription>
              Source: {agent.knowledge_base_source || "Unknown"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-sm whitespace-pre-wrap max-h-96 overflow-y-auto">
              {agent.knowledge_base_text.substring(0, 500)}
              {agent.knowledge_base_text.length > 500 && "..."}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
