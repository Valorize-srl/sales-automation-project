"use client";

import { Check, X, Eye, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmailResponseWithDetails, Sentiment, ResponseStatus } from "@/types";

interface ResponsesTableProps {
  responses: EmailResponseWithDetails[];
  loading: boolean;
  onViewDetail: (response: EmailResponseWithDetails) => void;
  onApprove: (id: number) => void;
  onSend: (id: number) => void;
  onIgnore: (id: number) => void;
}

const sentimentColors: Record<Sentiment, string> = {
  interested: "bg-green-100 text-green-800",
  positive: "bg-blue-100 text-blue-800",
  neutral: "bg-gray-100 text-gray-800",
  negative: "bg-red-100 text-red-800",
};

const statusColors: Record<ResponseStatus, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  ai_replied: "bg-purple-100 text-purple-800",
  human_approved: "bg-blue-100 text-blue-800",
  sent: "bg-green-100 text-green-800",
  ignored: "bg-gray-100 text-gray-500",
};

function truncate(text: string | null, max: number): string {
  if (!text) return "—";
  return text.length > max ? text.slice(0, max) + "..." : text;
}

export function ResponsesTable({
  responses,
  loading,
  onViewDetail,
  onApprove,
  onSend,
  onIgnore,
}: ResponsesTableProps) {
  if (loading) {
    return (
      <p className="text-muted-foreground py-8 text-center">Loading...</p>
    );
  }

  if (responses.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">
          No responses yet. Select campaigns and click &quot;Fetch
          Replies&quot; to pull email responses.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-md border overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>From</TableHead>
            <TableHead>Campaign</TableHead>
            <TableHead>Message</TableHead>
            <TableHead>Sentiment</TableHead>
            <TableHead>AI Reply</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="w-[140px]">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {responses.map((resp) => (
            <TableRow
              key={resp.id}
              className="cursor-pointer"
              onClick={() => onViewDetail(resp)}
            >
              <TableCell>
                <div>
                  <p className="font-medium text-sm">
                    {resp.lead_name || "Unknown"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {resp.lead_email || resp.from_email || "—"}
                  </p>
                </div>
              </TableCell>
              <TableCell className="text-sm">
                {resp.campaign_name || "—"}
              </TableCell>
              <TableCell className="text-sm max-w-[200px]">
                {truncate(resp.message_body, 60)}
              </TableCell>
              <TableCell>
                {resp.sentiment ? (
                  <Badge
                    variant="outline"
                    className={sentimentColors[resp.sentiment]}
                  >
                    {resp.sentiment}
                    {resp.sentiment_score !== null &&
                      ` (${(resp.sentiment_score * 100).toFixed(0)}%)`}
                  </Badge>
                ) : (
                  <span className="text-xs text-muted-foreground">—</span>
                )}
              </TableCell>
              <TableCell className="text-sm max-w-[200px]">
                {truncate(resp.ai_suggested_reply, 50)}
              </TableCell>
              <TableCell>
                <Badge
                  variant="outline"
                  className={statusColors[resp.status]}
                >
                  {resp.status.replace("_", " ")}
                </Badge>
              </TableCell>
              <TableCell>
                <div
                  className="flex gap-1"
                  onClick={(e) => e.stopPropagation()}
                >
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    title="View"
                    onClick={() => onViewDetail(resp)}
                  >
                    <Eye className="h-3 w-3" />
                  </Button>
                  {resp.status === "ai_replied" && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      title="Approve"
                      onClick={() => onApprove(resp.id)}
                    >
                      <Check className="h-3 w-3" />
                    </Button>
                  )}
                  {(resp.status === "human_approved" ||
                    resp.status === "ai_replied") && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      title="Send"
                      onClick={() => onSend(resp.id)}
                    >
                      <Send className="h-3 w-3" />
                    </Button>
                  )}
                  {resp.status !== "sent" && resp.status !== "ignored" && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      title="Ignore"
                      onClick={() => onIgnore(resp.id)}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
