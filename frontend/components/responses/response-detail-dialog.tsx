"use client";

import { useState, useEffect } from "react";
import { Check, Send, X, Loader2, Pencil, Brain, Trash2, Trophy } from "lucide-react";
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
  PersonListResponse,
} from "@/types";
import { api } from "@/lib/api";

/** Minimal sanitizer for reply bodies before rendering with dangerouslySetInnerHTML.
 * Strips scripts/styles/iframes, inline event handlers, and javascript: URLs.
 * Bodies come from external senders, so we never trust them — but this is an
 * authenticated admin surface so the risk is bounded. */
function sanitizeHtml(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, "")
    .replace(/<object[\s\S]*?<\/object>/gi, "")
    .replace(/<embed[^>]*>/gi, "")
    .replace(/\son[a-z]+\s*=\s*"[^"]*"/gi, "")
    .replace(/\son[a-z]+\s*=\s*'[^']*'/gi, "")
    .replace(/\son[a-z]+\s*=\s*[^\s>]+/gi, "")
    .replace(/javascript:/gi, "blocked:");
}

interface ResponseDetailDialogProps {
  response: EmailResponseWithDetails | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApprove: (id: number, editedReply?: string) => Promise<void>;
  onSend: (id: number) => Promise<void>;
  onIgnore: (id: number) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
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
  onDelete,
  onResponseUpdated,
}: ResponseDetailDialogProps) {
  const [editedReply, setEditedReply] = useState("");
  const [editing, setEditing] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [convertedState, setConvertedState] = useState<boolean | null>(null);
  const [convertingLead, setConvertingLead] = useState(false);
  // Thread = all messages in the same conversation (campaign + lead email).
  // Loaded lazily when the dialog opens; older messages are shown collapsed
  // above the "current" anchor message.
  const [threadMessages, setThreadMessages] = useState<EmailResponseWithDetails[] | null>(null);

  useEffect(() => {
    if (!response || !open) {
      setThreadMessages(null);
      return;
    }
    const count = (response.thread_count ?? 1);
    if (count <= 1) {
      setThreadMessages(null);
      return;
    }
    (async () => {
      try {
        const data = await api.getResponseThread(response.id);
        setThreadMessages(data.responses as EmailResponseWithDetails[]);
      } catch {
        setThreadMessages(null);
      }
    })();
  }, [response?.id, response?.thread_count, open]);

  // Load converted status when dialog opens with a new response
  useEffect(() => {
    if (!response || !open) {
      setConvertedState(null);
      return;
    }
    const email = response.lead_email || response.from_email;
    if (!email) return;
    (async () => {
      try {
        const data = await api.get<PersonListResponse>(`/people?search=${encodeURIComponent(email)}`);
        const person = data.people.find((p) => p.email.toLowerCase() === email.toLowerCase());
        if (person) {
          setConvertedState(!!person.converted_at);
        }
      } catch {
        // ignore
      }
    })();
  }, [response?.id, open]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleToggleConverted = async () => {
    const email = response?.lead_email || response?.from_email;
    if (!email) return;
    setConvertingLead(true);
    try {
      const data = await api.get<PersonListResponse>(`/people?search=${encodeURIComponent(email)}`);
      const person = data.people.find((p) => p.email.toLowerCase() === email.toLowerCase());
      if (person) {
        await api.updatePerson(person.id, { converted: !person.converted_at });
        setConvertedState(person.converted_at ? false : true);
      }
    } catch (err) {
      console.error("Failed to toggle converted:", err);
    } finally {
      setConvertingLead(false);
    }
  };

  if (!response) return null;

  const handleStartEdit = () => {
    setEditedReply(
      response.human_approved_reply ||
        response.ai_suggested_reply ||
        ""
    );
    setEditing(true);
  };

  const handleGenerateReply = async () => {
    setGenerating(true);
    try {
      const updated = await api.post<EmailResponseWithDetails>(
        `/responses/${response.id}/generate-reply`,
        {}
      );
      onResponseUpdated(updated);
    } catch (err) {
      console.error("Failed to generate reply:", err);
      alert("Failed to generate AI reply.");
    } finally {
      setGenerating(false);
    }
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
    setSendError(null);
    try {
      await onSend(response.id);
    } catch (e: unknown) {
      // Estrai un messaggio human-readable dall'errore: api.ts lancia un
      // Error con `.message` che già contiene il `detail` del backend.
      const msg = e instanceof Error ? e.message : "Errore sconosciuto";
      setSendError(msg);
    } finally {
      setSending(false);
    }
  };

  const isActionable =
    response.status !== "sent" && response.status !== "ignored";

  const hasReply = !!(response.human_approved_reply || response.ai_suggested_reply);

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
            Email: {response.lead_email || response.from_email || "\u2014"}
          </p>
          {response.lead_company && (
            <p>Company: {response.lead_company}</p>
          )}
          <p>Campaign: {response.campaign_name || "\u2014"}</p>
          {response.subject && <p>Subject: {response.subject}</p>}
          <p>
            Received:{" "}
            {new Date(
              response.received_at || response.created_at
            ).toLocaleString()}
          </p>
        </div>

        <Separator />

        {/* Sentiment + Converted */}
        <div className="flex items-center justify-between">
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
                Not available
              </span>
            )}
          </div>
          <Button
            variant={convertedState ? "default" : "outline"}
            size="sm"
            className={`gap-1.5 ${convertedState ? "bg-emerald-600 hover:bg-emerald-700" : ""}`}
            onClick={handleToggleConverted}
            disabled={convertingLead || !(response.lead_email || response.from_email)}
          >
            {convertingLead ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Trophy className="h-3 w-3" />
            )}
            {convertedState ? "Converted" : "Mark Converted"}
          </Button>
        </div>

        <Separator />

        {/* Conversation history — when the lead has replied multiple times,
            show every inbound message in chronological order. Each message
            is sanitized HTML. Single-reply threads collapse to one panel
            labelled "Original Message" for back-compat with the previous UI. */}
        <div>
          <h4 className="font-medium mb-2">
            {threadMessages && threadMessages.length > 1
              ? `Conversation (${threadMessages.length} messages)`
              : "Original Message"}
          </h4>
          {threadMessages && threadMessages.length > 1 ? (
            <div className="space-y-3 max-h-[400px] overflow-y-auto">
              {threadMessages.map((m, idx) => {
                const isLatest = idx === threadMessages.length - 1;
                const when = m.received_at || m.created_at;
                return (
                  <div
                    key={m.id}
                    className={`rounded border ${isLatest ? "border-primary/40 bg-primary/5" : "border-border bg-muted"} p-3`}
                  >
                    <div className="flex items-center justify-between mb-1.5 text-xs text-muted-foreground">
                      <span>
                        {idx + 1} of {threadMessages.length}
                        {isLatest ? " · latest" : ""}
                      </span>
                      <span>
                        {when ? new Date(when).toLocaleString("it-IT", {
                          day: "2-digit", month: "2-digit", year: "2-digit",
                          hour: "2-digit", minute: "2-digit",
                        }) : ""}
                      </span>
                    </div>
                    {m.message_body ? (
                      <div
                        className="rich-email text-sm"
                        dangerouslySetInnerHTML={{ __html: sanitizeHtml(m.message_body) }}
                      />
                    ) : (
                      <p className="text-sm text-muted-foreground italic">No body</p>
                    )}
                  </div>
                );
              })}
            </div>
          ) : response.message_body ? (
            <div
              className="rich-email bg-muted p-3 rounded text-sm max-h-[300px] overflow-y-auto"
              dangerouslySetInnerHTML={{ __html: sanitizeHtml(response.message_body) }}
            />
          ) : (
            <div className="bg-muted p-3 rounded text-sm text-muted-foreground italic">
              No message body
            </div>
          )}
        </div>

        <Separator />

        {/* AI Reply Section */}
        <div>
          <h4 className="font-medium mb-2">
            {editing ? "Edit Reply" : "Reply"}
          </h4>
          {editing ? (
            <Textarea
              value={editedReply}
              onChange={(e) => setEditedReply(e.target.value)}
              rows={5}
              className="text-sm"
            />
          ) : hasReply ? (
            <div className="bg-muted p-3 rounded text-sm whitespace-pre-wrap">
              {response.human_approved_reply || response.ai_suggested_reply}
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">
              No reply generated yet.{" "}
              {isActionable && (
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1 ml-2"
                  onClick={handleGenerateReply}
                  disabled={generating}
                >
                  {generating ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Brain className="h-3 w-3" />
                  )}
                  {generating ? "Generating..." : "Generate AI Reply"}
                </Button>
              )}
            </div>
          )}
        </div>

        {/* Sender hint: la reply parte dalla stessa casella che ha ricevuto
            il messaggio originale (requisito utente). Visibile solo se
            abbiamo identificato il sender_email. */}
        {isActionable && response.sender_email && (
          <>
            <Separator />
            <div className="text-xs flex items-center gap-1.5 text-muted-foreground bg-muted/40 rounded px-2.5 py-1.5 border">
              <Send className="h-3 w-3 shrink-0" />
              <span>Risponderà da:</span>
              <strong className="text-foreground">{response.sender_email}</strong>
              <span className="text-[10px] hidden sm:inline">
                (stessa casella che ha ricevuto il messaggio)
              </span>
            </div>
          </>
        )}

        {/* Banner errore Send: mostra il vero detail HTTP del backend
            invece di swallowarlo silenziosamente. Senza questo banner
            l'utente non capisce mai perché il Send non parte. */}
        {sendError && (
          <div className="text-xs rounded border border-red-300 bg-red-50 dark:bg-red-950/30 text-red-900 dark:text-red-200 px-3 py-2">
            <strong>Invio fallito:</strong> {sendError}
          </div>
        )}

        {/* Action buttons */}
        {isActionable && (
          <>
            <Separator />
            <div className="flex flex-wrap gap-2">
              {hasReply && !editing && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleStartEdit}
                  className="gap-1"
                >
                  <Pencil className="h-3 w-3" />
                  Edit Reply
                </Button>
              )}
              {editing && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setEditing(false)}
                >
                  Cancel Edit
                </Button>
              )}
              {!hasReply && !generating && (
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1"
                  onClick={handleGenerateReply}
                  disabled={generating}
                >
                  {generating ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Brain className="h-3 w-3" />
                  )}
                  Generate AI Reply
                </Button>
              )}
              {(hasReply || editing) && (
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
              )}
              {(hasReply || response.status === "human_approved") && (
                <Button
                  size="sm"
                  variant="default"
                  className="gap-1"
                  onClick={handleSend}
                  disabled={
                    sending
                    || !response.smartlead_message_stats_id
                    || !response.smartlead_lead_id
                    || !response.sender_email
                  }
                  title={
                    !response.smartlead_message_stats_id ? "Reply importata prima dell'aggancio webhook Smartlead — manca l'email_stats_id. Lancia /admin/enrich-responses oppure rispondi via Gmail/Outlook." :
                    !response.smartlead_lead_id ? "Smartlead lead_id mancante. Lancia /admin/enrich-responses." :
                    !response.sender_email ? "Mittente non identificato — non è sicuro inviare senza sapere da quale casella partirà." :
                    ""
                  }
                >
                  {sending ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Send className="h-3 w-3" />
                  )}
                  Send
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                className="gap-1"
                onClick={() => onIgnore(response.id)}
              >
                <X className="h-3 w-3" />
                Ignore
              </Button>
              <Button
                variant="destructive"
                size="sm"
                className="gap-1 ml-auto"
                onClick={() => onDelete(response.id)}
              >
                <Trash2 className="h-3 w-3" />
                Delete
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
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              This response has been ignored.
            </p>
            <Button
              variant="destructive"
              size="sm"
              className="gap-1"
              onClick={() => onDelete(response.id)}
            >
              <Trash2 className="h-3 w-3" />
              Delete
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
