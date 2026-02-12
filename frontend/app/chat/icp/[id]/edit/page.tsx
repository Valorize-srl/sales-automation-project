"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Save, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api";
import { ICP } from "@/types";

export default function ICPEditPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [icp, setIcp] = useState<ICP | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: "",
    description: "",
    industry: "",
    company_size: "",
    job_titles: "",
    geography: "",
    revenue_range: "",
    keywords: "",
  });

  useEffect(() => {
    loadIcp();
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadIcp = async () => {
    try {
      const data = await api.get<ICP>(`/icps/${id}`);
      setIcp(data);
      setForm({
        name: data.name || "",
        description: data.description || "",
        industry: data.industry || "",
        company_size: data.company_size || "",
        job_titles: data.job_titles || "",
        geography: data.geography || "",
        revenue_range: data.revenue_range || "",
        keywords: data.keywords || "",
      });
    } catch (err) {
      console.error("Failed to load ICP:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await api.put<ICP>(`/icps/${id}`, form);
      setIcp(updated);
    } catch (err) {
      console.error("Failed to save ICP:", err);
    } finally {
      setSaving(false);
    }
  };

  const handleActivate = async () => {
    setSaving(true);
    try {
      const updated = await api.put<ICP>(`/icps/${id}`, {
        ...form,
        status: "active",
      });
      setIcp(updated);
    } catch (err) {
      console.error("Failed to activate ICP:", err);
    } finally {
      setSaving(false);
    }
  };

  const updateField = (field: string, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  if (loading) {
    return <p className="text-muted-foreground">Loading...</p>;
  }

  if (!icp) {
    return <p className="text-destructive">ICP not found.</p>;
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/chat/icp">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">Edit ICP</h1>
        </div>
        <Badge variant="outline">{icp.status}</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">ICP Details</CardTitle>
        </CardHeader>
        <Separator />
        <CardContent className="pt-6 space-y-4">
          <div>
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              value={form.name}
              onChange={(e) => updateField("name", e.target.value)}
            />
          </div>

          <div>
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={form.description}
              onChange={(e) => updateField("description", e.target.value)}
              rows={3}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="industry">Industry</Label>
              <Input
                id="industry"
                value={form.industry}
                onChange={(e) => updateField("industry", e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="company_size">Company Size</Label>
              <Input
                id="company_size"
                value={form.company_size}
                onChange={(e) => updateField("company_size", e.target.value)}
                placeholder="e.g., 50-200 employees"
              />
            </div>
          </div>

          <div>
            <Label htmlFor="job_titles">Job Titles</Label>
            <Textarea
              id="job_titles"
              value={form.job_titles}
              onChange={(e) => updateField("job_titles", e.target.value)}
              placeholder="Comma-separated, e.g., CTO, VP Engineering"
              rows={2}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="geography">Geography</Label>
              <Input
                id="geography"
                value={form.geography}
                onChange={(e) => updateField("geography", e.target.value)}
                placeholder="e.g., Europe, US"
              />
            </div>
            <div>
              <Label htmlFor="revenue_range">Revenue Range</Label>
              <Input
                id="revenue_range"
                value={form.revenue_range}
                onChange={(e) => updateField("revenue_range", e.target.value)}
                placeholder="e.g., $1M-$10M"
              />
            </div>
          </div>

          <div>
            <Label htmlFor="keywords">Keywords</Label>
            <Textarea
              id="keywords"
              value={form.keywords}
              onChange={(e) => updateField("keywords", e.target.value)}
              placeholder="Comma-separated keywords, technologies, pain points"
              rows={2}
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex gap-2 mt-4">
        <Button onClick={handleSave} disabled={saving} className="gap-1">
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          Save Changes
        </Button>
        {icp.status === "draft" && (
          <Button
            variant="outline"
            onClick={handleActivate}
            disabled={saving}
          >
            Activate ICP
          </Button>
        )}
        <Link href="/chat">
          <Button variant="ghost">Back to Chat</Button>
        </Link>
      </div>
    </div>
  );
}
