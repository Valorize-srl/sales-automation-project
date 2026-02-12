"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Pencil, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api";
import { ICPExtracted, ICP } from "@/types";

interface ICPPreviewCardProps {
  data: ICPExtracted;
  rawInput?: string;
}

const FIELD_LABELS: Record<string, string> = {
  industry: "Industry",
  company_size: "Company Size",
  job_titles: "Job Titles",
  geography: "Geography",
  revenue_range: "Revenue Range",
  keywords: "Keywords",
  description: "Description",
};

export function ICPPreviewCard({ data, rawInput }: ICPPreviewCardProps) {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [savedId, setSavedId] = useState<number | null>(null);

  const handleSave = async () => {
    setSaving(true);
    try {
      const icp = await api.post<ICP>("/icps", {
        ...data,
        raw_input: rawInput || null,
      });
      setSaved(true);
      setSavedId(icp.id);
    } catch (err) {
      console.error("Failed to save ICP:", err);
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = () => {
    if (savedId) {
      router.push(`/chat/icp/${savedId}/edit`);
    }
  };

  const fields = Object.entries(FIELD_LABELS)
    .map(([key, label]) => ({
      label,
      value: data[key as keyof ICPExtracted],
    }))
    .filter((f) => f.value);

  return (
    <Card className="my-4 border-primary/20">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">{data.name}</CardTitle>
          <Badge variant="outline">Draft</Badge>
        </div>
      </CardHeader>
      <Separator />
      <CardContent className="pt-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {fields.map((field) => (
            <div key={field.label}>
              <p className="text-xs text-muted-foreground font-medium">
                {field.label}
              </p>
              <p className="text-sm mt-0.5">{field.value}</p>
            </div>
          ))}
        </div>
      </CardContent>
      <Separator />
      <CardFooter className="pt-4 gap-2">
        {saved ? (
          <>
            <Button variant="outline" size="sm" disabled className="gap-1">
              <Check className="h-3 w-3" />
              Saved
            </Button>
            <Button variant="default" size="sm" onClick={handleEdit} className="gap-1">
              <Pencil className="h-3 w-3" />
              Review & Edit
            </Button>
          </>
        ) : (
          <Button
            size="sm"
            onClick={handleSave}
            disabled={saving}
            className="gap-1"
          >
            {saving ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Check className="h-3 w-3" />
            )}
            Save as Draft
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
