"use client";

import { Check, X, Eye, Send, Trash2 } from "lucide-react";
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
  onDelete: (id: number) => void;
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

/** Strip HTML tags + decode the most common entities for clean previews.
 * Reply bodies arrive as HTML from Smartlead; rendering them as plaintext
 * in the table column dumps `<div>` etc. into the cell. */
function htmlToPreview(html: string | null): string {
  if (!html) return "";
  return html
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<\/?[a-z][^>]*>/gi, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/\s+/g, " ")
    .trim();
}

function truncate(text: string | null, max: number): string {
  const clean = htmlToPreview(text);
  if (!clean) return "\u2014";
  return clean.length > max ? clean.slice(0, max) + "\u2026" : clean;
}

export function ResponsesTable({
  responses,
  loading,
  onViewDetail,
  onApprove,
  onSend,
  onIgnore,
  onDelete,
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
            <TableHead>Status</TableHead>
            <TableHead>Received</TableHead>
            <TableHead className="w-[160px]">Actions</TableHead>
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
                    {resp.lead_email || resp.from_email || "\u2014"}
                  </p>
                </div>
              </TableCell>
              <TableCell className="text-sm">
                {resp.campaign_name || "\u2014"}
              </TableCell>
              <TableCell className="text-sm max-w-[200px]">
                {truncate(resp.message_body, 60)}
              </TableCell>
              <TableCell>
                <div className="flex flex-col gap-1 items-start">
                  {resp.lead_category ? (
                    <Badge
                      variant="outline"
                      className={`${resp.sentiment ? sentimentColors[resp.sentiment] : ""} font-medium`}
                      title="Smartlead category"
                    >
                      {resp.lead_category}
                    </Badge>
                  ) : resp.sentiment ? (
                    <Badge
                      variant="outline"
                      className={sentimentColors[resp.sentiment]}
                    >
                      {resp.sentiment}
                    </Badge>
                  ) : (
                    <span className="text-xs text-muted-foreground">{"\u2014"}</span>
                  )}
                </div>
              </TableCell>
              <TableCell>
                <Badge
                  variant="outline"
                  className={statusColors[resp.status]}
                >
                  {resp.status.replace("_", " ")}
                </Badge>
              </TableCell>
              <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                {resp.received_at
                  ? new Date(resp.received_at).toLocaleDateString("it-IT", {
                      day: "2-digit",
                      month: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : new Date(resp.created_at).toLocaleDateString("it-IT", {
                      day: "2-digit",
                      month: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
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
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-destructive hover:text-destructive"
                    title="Delete"
                    onClick={() => onDelete(resp.id)}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
