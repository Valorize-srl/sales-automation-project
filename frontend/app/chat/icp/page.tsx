"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Pencil, Trash2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { ICP, ICPListResponse } from "@/types";

const statusColors: Record<string, string> = {
  draft: "bg-yellow-100 text-yellow-800",
  active: "bg-green-100 text-green-800",
  archived: "bg-gray-100 text-gray-800",
};

export default function ICPListPage() {
  const [icps, setIcps] = useState<ICP[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadIcps();
  }, []);

  const loadIcps = async () => {
    try {
      const data = await api.get<ICPListResponse>("/icps");
      setIcps(data.icps);
    } catch (err) {
      console.error("Failed to load ICPs:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this ICP?")) return;
    try {
      await api.delete(`/icps/${id}`);
      setIcps((prev) => prev.filter((icp) => icp.id !== id));
    } catch (err) {
      console.error("Failed to delete ICP:", err);
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link href="/chat">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold">Saved ICPs</h1>
            <p className="text-sm text-muted-foreground">
              {icps.length} profile{icps.length !== 1 ? "s" : ""}
            </p>
          </div>
        </div>
        <Link href="/chat">
          <Button size="sm" className="gap-1">
            <Plus className="h-4 w-4" />
            New ICP
          </Button>
        </Link>
      </div>

      {loading ? (
        <p className="text-muted-foreground">Loading...</p>
      ) : icps.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-muted-foreground mb-4">
            No ICPs saved yet. Start a chat to create one.
          </p>
          <Link href="/chat">
            <Button>Start Chat</Button>
          </Link>
        </div>
      ) : (
        <div className="grid gap-4">
          {icps.map((icp) => (
            <Card key={icp.id}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{icp.name}</CardTitle>
                  <div className="flex items-center gap-2">
                    <Badge
                      variant="outline"
                      className={statusColors[icp.status] || ""}
                    >
                      {icp.status}
                    </Badge>
                    <Link href={`/chat/icp/${icp.id}/edit`}>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <Pencil className="h-3 w-3" />
                      </Button>
                    </Link>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-destructive"
                      onClick={() => handleDelete(icp.id)}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
                  {icp.industry && (
                    <div>
                      <p className="text-xs text-muted-foreground">Industry</p>
                      <p>{icp.industry}</p>
                    </div>
                  )}
                  {icp.job_titles && (
                    <div>
                      <p className="text-xs text-muted-foreground">Job Titles</p>
                      <p>{icp.job_titles}</p>
                    </div>
                  )}
                  {icp.geography && (
                    <div>
                      <p className="text-xs text-muted-foreground">Geography</p>
                      <p>{icp.geography}</p>
                    </div>
                  )}
                  {icp.company_size && (
                    <div>
                      <p className="text-xs text-muted-foreground">Company Size</p>
                      <p>{icp.company_size}</p>
                    </div>
                  )}
                  {icp.revenue_range && (
                    <div>
                      <p className="text-xs text-muted-foreground">Revenue</p>
                      <p>{icp.revenue_range}</p>
                    </div>
                  )}
                  {icp.keywords && (
                    <div>
                      <p className="text-xs text-muted-foreground">Keywords</p>
                      <p>{icp.keywords}</p>
                    </div>
                  )}
                </div>
                {icp.description && (
                  <p className="text-sm text-muted-foreground mt-3">
                    {icp.description}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
