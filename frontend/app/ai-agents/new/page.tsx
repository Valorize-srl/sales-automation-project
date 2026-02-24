"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Save } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";

export default function NewAIAgentPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);

  const [formData, setFormData] = useState({
    name: "",
    client_tag: "",
    description: "",
    industry: "",
    company_size: "",
    job_titles: "",
    geography: "",
    keywords: "",
    apollo_credits_allocated: 1000,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const agent = await api.createAIAgent({
        name: formData.name,
        client_tag: formData.client_tag,
        description: formData.description || undefined,
        icp_config: {
          industry: formData.industry,
          company_size: formData.company_size,
          job_titles: formData.job_titles,
          geography: formData.geography,
          keywords: formData.keywords,
        },
        apollo_credits_allocated: formData.apollo_credits_allocated,
      });

      toast({
        title: "Success",
        description: `AI Agent "${agent.name}" created successfully`,
      });

      router.push(`/ai-agents/${agent.id}/dashboard`);
    } catch (error) {
      console.error("Failed to create agent:", error);
      toast({
        title: "Error",
        description: "Failed to create AI Agent",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/ai-agents">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-3xl font-bold">Create AI Agent</h1>
          <p className="text-muted-foreground">
            Set up a new AI agent for client prospecting
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Info */}
        <Card>
          <CardHeader>
            <CardTitle>Basic Information</CardTitle>
            <CardDescription>Agent name and identification</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="name">Agent Name *</Label>
              <Input
                id="name"
                placeholder="e.g., Cliente XYZ Wine Prospecting"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
              />
            </div>

            <div>
              <Label htmlFor="client_tag">Client Tag *</Label>
              <Input
                id="client_tag"
                placeholder="e.g., cliente_xyz"
                value={formData.client_tag}
                onChange={(e) =>
                  setFormData({ ...formData, client_tag: e.target.value.toLowerCase().replace(/\s/g, "_") })
                }
                required
              />
              <p className="text-xs text-muted-foreground mt-1">
                Unique identifier for tagging leads (lowercase, no spaces)
              </p>
            </div>

            <div>
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                placeholder="Optional description of this agent's purpose"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
            </div>
          </CardContent>
        </Card>

        {/* ICP Configuration */}
        <Card>
          <CardHeader>
            <CardTitle>ICP Configuration</CardTitle>
            <CardDescription>Define the Ideal Customer Profile</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="industry">Industry</Label>
              <Input
                id="industry"
                placeholder="e.g., Wine Production, SaaS, E-commerce"
                value={formData.industry}
                onChange={(e) => setFormData({ ...formData, industry: e.target.value })}
              />
            </div>

            <div>
              <Label htmlFor="company_size">Company Size</Label>
              <Input
                id="company_size"
                placeholder="e.g., 10-50, 51-200"
                value={formData.company_size}
                onChange={(e) => setFormData({ ...formData, company_size: e.target.value })}
              />
            </div>

            <div>
              <Label htmlFor="job_titles">Job Titles</Label>
              <Input
                id="job_titles"
                placeholder="e.g., CEO, Founder, Head of Marketing"
                value={formData.job_titles}
                onChange={(e) => setFormData({ ...formData, job_titles: e.target.value })}
              />
            </div>

            <div>
              <Label htmlFor="geography">Geography</Label>
              <Input
                id="geography"
                placeholder="e.g., Tuscany Italy, San Francisco CA"
                value={formData.geography}
                onChange={(e) => setFormData({ ...formData, geography: e.target.value })}
              />
            </div>

            <div>
              <Label htmlFor="keywords">Keywords</Label>
              <Input
                id="keywords"
                placeholder="e.g., organic wine, export, digital transformation"
                value={formData.keywords}
                onChange={(e) => setFormData({ ...formData, keywords: e.target.value })}
              />
            </div>
          </CardContent>
        </Card>

        {/* Budget */}
        <Card>
          <CardHeader>
            <CardTitle>Budget Configuration</CardTitle>
            <CardDescription>Set Apollo credits allocation</CardDescription>
          </CardHeader>
          <CardContent>
            <div>
              <Label htmlFor="credits">Apollo Credits Allocated</Label>
              <Input
                id="credits"
                type="number"
                min="0"
                value={formData.apollo_credits_allocated}
                onChange={(e) =>
                  setFormData({ ...formData, apollo_credits_allocated: parseInt(e.target.value) || 0 })
                }
              />
              <p className="text-xs text-muted-foreground mt-1">
                Monthly budget for Apollo API operations ($0.10 per credit)
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <Link href="/ai-agents">
            <Button type="button" variant="outline">
              Cancel
            </Button>
          </Link>
          <Button type="submit" disabled={loading}>
            <Save className="h-4 w-4 mr-2" />
            {loading ? "Creating..." : "Create Agent"}
          </Button>
        </div>
      </form>
    </div>
  );
}
