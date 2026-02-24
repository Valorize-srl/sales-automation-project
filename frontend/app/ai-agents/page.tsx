"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Plus, Bot, TrendingUp, Users, CreditCard } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import type { AIAgent } from "@/types";

export default function AIAgentsPage() {
  const [agents, setAgents] = useState<AIAgent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAgents();
  }, []);

  const loadAgents = async () => {
    try {
      const data = await api.getAIAgents();
      setAgents(data.agents);
    } catch (error) {
      console.error("Failed to load AI agents:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-48px)]">
        <div className="text-center">
          <p className="text-muted-foreground">Loading AI Agents...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">AI Agents</h1>
          <p className="text-muted-foreground">
            Manage client-specific AI agents for prospecting and auto-reply
          </p>
        </div>
        <Link href="/ai-agents/new">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Create Agent
          </Button>
        </Link>
      </div>

      {agents.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No AI Agents Yet</CardTitle>
            <CardDescription>
              Create your first AI Agent to start prospecting for a client
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/ai-agents/new">
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Create First Agent
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => (
            <Link key={agent.id} href={`/ai-agents/${agent.id}/dashboard`}>
              <Card className="hover:shadow-lg transition-shadow cursor-pointer">
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-2">
                      <Bot className="h-5 w-5 text-primary" />
                      <CardTitle className="text-lg">{agent.name}</CardTitle>
                    </div>
                    <Badge variant={agent.is_active ? "default" : "secondary"}>
                      {agent.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                  <CardDescription>
                    <Badge variant="outline" className="text-xs">
                      {agent.client_tag}
                    </Badge>
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Credits */}
                  <div>
                    <div className="flex items-center justify-between text-sm mb-2">
                      <span className="flex items-center gap-1">
                        <CreditCard className="h-4 w-4" />
                        Apollo Credits
                      </span>
                      <span className="font-medium">
                        {agent.credits_remaining} / {agent.apollo_credits_allocated}
                      </span>
                    </div>
                    <Progress value={agent.credits_percentage_used} className="h-2" />
                    <p className="text-xs text-muted-foreground mt-1">
                      {agent.credits_percentage_used.toFixed(1)}% used
                    </p>
                  </div>

                  {/* ICP Summary */}
                  <div className="space-y-1 text-sm">
                    {agent.icp_config.industry && (
                      <p className="text-muted-foreground">
                        <strong>Industry:</strong> {agent.icp_config.industry}
                      </p>
                    )}
                    {agent.icp_config.company_size && (
                      <p className="text-muted-foreground">
                        <strong>Size:</strong> {agent.icp_config.company_size}
                      </p>
                    )}
                    {agent.icp_config.geography && (
                      <p className="text-muted-foreground">
                        <strong>Location:</strong> {agent.icp_config.geography}
                      </p>
                    )}
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
