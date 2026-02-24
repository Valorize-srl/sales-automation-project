"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Search, TrendingUp, Users, CreditCard, FileText, Trash2, Link2, Unlink, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";
import type { AIAgent, AIAgentStats, Campaign } from "@/types";

export default function AIAgentDashboardPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const agentId = parseInt(params.id as string);

  const [agent, setAgent] = useState<AIAgent | null>(null);
  const [stats, setStats] = useState<AIAgentStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [allCampaigns, setAllCampaigns] = useState<Campaign[]>([]);
  const [associatedCampaigns, setAssociatedCampaigns] = useState<any[]>([]);
  const [selectedCampaignId, setSelectedCampaignId] = useState<string>("");

  useEffect(() => {
    loadAgent();
    loadStats();
    loadCampaigns();
    loadAssociatedCampaigns();
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

  const loadCampaigns = async () => {
    try {
      const data = await api.getCampaigns();
      setAllCampaigns(data.campaigns);
    } catch (error) {
      console.error("Failed to load campaigns:", error);
    }
  };

  const loadAssociatedCampaigns = async () => {
    try {
      const data = await api.getAssociatedCampaigns(agentId);
      setAssociatedCampaigns(data.campaigns);
    } catch (error) {
      console.error("Failed to load associated campaigns:", error);
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

  const handleAssociateCampaign = async () => {
    if (!selectedCampaignId) return;

    try {
      const result = await api.associateCampaigns(agentId, [parseInt(selectedCampaignId)]);
      toast({
        title: "Campaign Connected",
        description: result.message || "Campaign successfully connected for auto-reply",
      });
      setSelectedCampaignId("");
      await loadAssociatedCampaigns();
      await loadStats();
    } catch (error: any) {
      console.error("Association error:", error);
      toast({
        title: "Connection Failed",
        description: error.response?.data?.detail || "Failed to connect campaign",
        variant: "destructive",
      });
    }
  };

  const handleDisassociateCampaign = async (campaignId: number, campaignName: string) => {
    if (!confirm(`Disconnect "${campaignName}" from this AI Agent?`)) return;

    try {
      await api.disassociateCampaign(agentId, campaignId);
      toast({
        title: "Campaign Disconnected",
        description: `"${campaignName}" is no longer using this AI Agent for auto-reply`,
      });
      await loadAssociatedCampaigns();
      await loadStats();
    } catch (error: any) {
      console.error("Disassociation error:", error);
      toast({
        title: "Disconnection Failed",
        description: error.response?.data?.detail || "Failed to disconnect campaign",
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

      {/* Connected Campaigns */}
      <Card>
        <CardHeader>
          <CardTitle>Connected Campaigns</CardTitle>
          <CardDescription>
            Campaigns using this AI Agent for auto-reply functionality
          </CardDescription>
        </CardHeader>
        <CardContent>
          {/* Add Campaign */}
          <div className="flex gap-2 mb-4">
            <Select value={selectedCampaignId} onValueChange={setSelectedCampaignId}>
              <SelectTrigger className="flex-1">
                <SelectValue placeholder="Select campaign to connect..." />
              </SelectTrigger>
              <SelectContent>
                {allCampaigns
                  .filter((c) => !associatedCampaigns.some((ac) => ac.id === c.id))
                  .map((campaign) => (
                    <SelectItem key={campaign.id} value={String(campaign.id)}>
                      {campaign.name} ({campaign.status})
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
            <Button
              onClick={handleAssociateCampaign}
              disabled={!selectedCampaignId}
              className="gap-1"
            >
              <Link2 className="h-4 w-4" />
              Connect
            </Button>
          </div>

          {/* Associated Campaigns List */}
          {associatedCampaigns.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              No campaigns connected yet. Connect a campaign to enable AI auto-reply.
            </p>
          ) : (
            <div className="space-y-2">
              {associatedCampaigns.map((campaign) => (
                <div
                  key={campaign.id}
                  className="flex items-center justify-between p-3 border rounded-lg hover:bg-accent/50 transition-colors"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <p className="font-medium">{campaign.name}</p>
                      <Badge variant="outline" className="text-xs">
                        {campaign.status}
                      </Badge>
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Sent: {campaign.total_sent} · Opened: {campaign.total_opened} · Replied: {campaign.total_replied}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDisassociateCampaign(campaign.id, campaign.name)}
                    className="gap-1"
                  >
                    <Unlink className="h-3 w-3" />
                    Disconnect
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
