"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Loader2, Send, Bot, User } from "lucide-react";
import { useChatSession } from "@/hooks/useChatSession";
import ReactMarkdown from "react-markdown";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agentId?: number;
}

export function ClaudePanel({ open, onOpenChange, agentId }: Props) {
  const { context, sendMessage, createNewSession } = useChatSession();
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [context?.messages, scrollToBottom]);

  // Create session when panel opens with agent
  useEffect(() => {
    if (open && !context?.sessionUuid) {
      createNewSession(agentId ? { ai_agent_id: agentId } : undefined);
    }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSend = async () => {
    if (!input.trim() || context?.isStreaming) return;
    const msg = input;
    setInput("");
    await sendMessage(msg);
  };

  const messages = context?.messages || [];

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="left" className="w-[400px] sm:w-[450px] p-0 flex flex-col">
        <SheetHeader className="p-4 border-b">
          <SheetTitle className="text-sm flex items-center gap-2">
            <Bot className="h-4 w-4" />
            Chiedi a Claude
          </SheetTitle>
          <p className="text-xs text-muted-foreground">Consigli su strategia, ICP, quale tool usare</p>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.length === 0 && (
            <div className="text-center text-muted-foreground text-sm py-8">
              <Bot className="h-8 w-8 mx-auto mb-2 opacity-30" />
              <p>Chiedimi consigli su strategia di prospecting, definizione ICP, o quale tool usare.</p>
            </div>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-2 ${msg.role === "user" ? "justify-end" : ""}`}>
              {msg.role === "assistant" && (
                <div className="p-1 rounded bg-primary/10 h-fit">
                  <Bot className="h-3 w-3 text-primary" />
                </div>
              )}
              <div
                className={`rounded-lg px-3 py-2 text-sm max-w-[85%] ${
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                }`}
              >
                {msg.role === "assistant" ? (
                  <div className="prose prose-sm dark:prose-invert max-w-none [&>p]:my-1 [&>ul]:my-1">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                ) : (
                  msg.content
                )}
              </div>
              {msg.role === "user" && (
                <div className="p-1 rounded bg-primary/10 h-fit">
                  <User className="h-3 w-3 text-primary" />
                </div>
              )}
            </div>
          ))}
          {context?.isStreaming && (
            <div className="flex gap-2">
              <div className="p-1 rounded bg-primary/10 h-fit">
                <Bot className="h-3 w-3 text-primary" />
              </div>
              <div className="rounded-lg px-3 py-2 text-sm bg-muted">
                <Loader2 className="h-3 w-3 animate-spin" />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="p-3 border-t flex gap-2">
          <Input
            placeholder="Scrivi un messaggio..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
            disabled={context?.isStreaming}
            className="text-sm"
          />
          <Button size="icon" onClick={handleSend} disabled={!input.trim() || context?.isStreaming}>
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
