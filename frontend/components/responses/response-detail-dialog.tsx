"use client";

import { useState } from "react";
import { Check, Send, X, Loader2, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  EmailResponseWithDetails,
  Sentiment,
  ResponseStatus,
} from "@/types";

interface ResponseDetailDialogProps {
  response: EmailResponseWithDetails | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApprove: (id: number, editedReply?: string) => Promise<void>;
  onSend: (id: number) => Promise<void>;
  onIgnore: (id: number) => Promise<void>;
  onResponseUpdated: (response: EmailResponseWithDetails) => void;
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

export function ResponseDetailDialog({
  response,
  open,
  onOpenChange,
  onApprove,
  onSend,
  onIgnore,
}: ResponseDetailDialogProps) {
  const [editedReply, setEditedReply] = useState("");
  const [editing, setEditing] = useState(false);
  const [sending, setSending] = useState(false);
  const [approving, setApproving] = useState(false);

  if (!response) return null;

  const handleStartEdit = () => {
    setEditedReply(
      response.human_approved_reply ||
        response.ai_suggested_reply ||
        ""
    );
    setEditing(true);
  };

  const handleApproveWithEdit = async () => {
    setApproving(true);
    try {
      await onApprove(
        response.id,
        editing ? editedReply : undefined
      );
      setEditing(false);
    } finally {
      setApproving(false);
    }
  };

  const handleSend = async () => {
    setSending(true);
    try {
      await onSend(response.id);
    } finally {
      setSending(false);
    }
  };

  const isActionable =
    response.status !== "sent" && response.status !== "ignored";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[700px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 flex-wrap">
            Response from{" "}
            {response.lead_name || response.lead_email || "Unknown"}
            <Badge
              variant="outline"
              className={statusColors[response.status]}
            >
              {response.status.replace("_", " ")}
            </Badge>
          </DialogTitle>
        </DialogHeader>

        {/* Metadata */}
        <div className="text-sm text-muted-foreground space-y-1">
          <p>
            Email: {response.lead_email || response.from_email || "—"}
          </p>
          {response.lead_company && (
            <p>Company: {response.lead_company}</p>
          )}
          <p>Campaign: {response.campaign_name || "—"}</p>
          {response.subject && <p>Subject: {response.subject}</p>}
          <p>
            Received:{" "}
            {new Date(
              response.received_at || response.created_at
            ).toLocaleString()}
          </p>
        </div>

        <Separator />

        {/* Sentiment */}
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium">Sentiment:</span>
          {response.sentiment ? (
            <Badge
              variant="outline"
              className={sentimentColors[response.sentiment]}
            >
              {response.sentiment}{" "}
              {response.sentiment_score !== null &&
                `(${(response.sentiment_score * 100).toFixed(0)}%)`}
            </Badge>
          ) : (
            <span className="text-sm text-muted-foreground">
              Not analyzed
            </span>
          )}
        </div>

        <Separator />

        {/* Original Message */}
        <div>
          <h4 className="font-medium mb-2">Original Message</h4>
          <div className="bg-muted p-3 rounded text-sm whitespace-pre-wrap max-h-[200px] overflow-y-auto">
            {response.message_body || "No message body"}
          </div>
        </div>

        <Separator />

        {/* AI Suggested Reply */}
        <div>
          <h4 className="font-medium mb-2">
            {editing ? "Edit Reply" : "AI Suggested Reply"}
          </h4>
          {editing ? (
            <Textarea
              value={editedReply}
              onChange={(e) => setEditedReply(e.target.value)}
              rows={5}
              className="text-sm"
            />
          ) : (
            <div className="bg-muted p-3 rounded text-sm whitespace-pre-wrap">
              {response.human_approved_reply ||
                response.ai_suggested_reply ||
                "No reply generated"}
            </div>
          )}
        </div>

        {/* Action buttons */}
        {isActionable && (
          <>
            <Separator />
            <div className="flex flex-wrap gap-2">
              {!editing ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleStartEdit}
                  className="gap-1"
                >
                  <Pencil className="h-3 w-3" />
                  Edit Reply
                </Button>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setEditing(false)}
                >
                  Cancel Edit
                </Button>
              )}
              <Button
                size="sm"
                className="gap-1"
                onClick={handleApproveWithEdit}
                disabled={approving}
              >
                {approving ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Check className="h-3 w-3" />
                )}
                {editing ? "Approve Edited" : "Approve"}
              </Button>
              <Button
                size="sm"
                variant="default"
                className="gap-1"
                onClick={handleSend}
                disabled={sending}
              >
                {sending ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Send className="h-3 w-3" />
                )}
                Send
              </Button>
              <Button
                variant="destructive"
                size="sm"
                className="gap-1 ml-auto"
                onClick={() => onIgnore(response.id)}
              >
                <X className="h-3 w-3" />
                Ignore
              </Button>
            </div>
          </>
        )}

        {response.status === "sent" && (
          <p className="text-sm text-green-600 font-medium">
            Reply has been sent.
          </p>
        )}
        {response.status === "ignored" && (
          <p className="text-sm text-muted-foreground">
            This response has been ignored.
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}
