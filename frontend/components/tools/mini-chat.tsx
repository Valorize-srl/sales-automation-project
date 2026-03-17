"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, Send, Bot, User, ChevronDown, ChevronUp } from "lucide-react";
import { useChatSession } from "@/hooks/useChatSession";
import ReactMarkdown from "react-markdown";

interface Props {
  agentId?: number;
  toolContext?: string;
}

export function MiniChat({ agentId, toolContext }: Props) {
  const { context, sendMessage, createNewSession } = useChatSession();
  const [input, setInput] = useState("");
  const [expanded, setExpanded] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [context?.messages, scrollToBottom]);

  // Create session on first expand
  useEffect(() => {
    if (expanded && !context?.sessionUuid) {
      createNewSession(agentId ? { ai_agent_id: agentId } : undefined);
    }
  }, [expanded]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSend = async () => {
    if (!input.trim() || context?.isStreaming) return;
    const msg = toolContext
      ? `[Sto usando il tool: ${toolContext}]\n\n${input}`
      : input;
    setInput("");
    await sendMessage(msg);
  };

  const messages = context?.messages || [];

  return (
    <div className="border rounded-lg bg-muted/30 mt-4">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <Bot className="h-3 w-3" />
          Chiedi a Claude
        </span>
        {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>

      {expanded && (
        <div className="border-t">
          <div className="max-h-[200px] overflow-y-auto p-2 space-y-2">
            {messages.length === 0 && (
              <p className="text-xs text-muted-foreground text-center py-3">
                Chiedimi consigli su come usare questo tool
              </p>
            )}
            {messages.map((msg, i) => (
              <div key={i} className={`flex gap-1.5 ${msg.role === "user" ? "justify-end" : ""}`}>
                {msg.role === "assistant" && (
                  <Bot className="h-3 w-3 text-primary mt-1 flex-shrink-0" />
                )}
                <div
                  className={`rounded px-2 py-1 text-xs max-w-[90%] ${
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-background"
                  }`}
                >
                  {msg.role === "assistant" ? (
                    <div className="prose prose-xs dark:prose-invert max-w-none [&>p]:my-0.5 [&>ul]:my-0.5">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  ) : (
                    msg.content.replace(`[Sto usando il tool: ${toolContext}]\n\n`, "")
                  )}
                </div>
                {msg.role === "user" && (
                  <User className="h-3 w-3 text-primary mt-1 flex-shrink-0" />
                )}
              </div>
            ))}
            {context?.isStreaming && (
              <div className="flex gap-1.5">
                <Bot className="h-3 w-3 text-primary mt-1 flex-shrink-0" />
                <div className="rounded px-2 py-1 bg-background">
                  <Loader2 className="h-3 w-3 animate-spin" />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="p-2 border-t flex gap-1.5">
            <Input
              placeholder="Chiedi consiglio..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
              disabled={context?.isStreaming}
              className="text-xs h-7"
            />
            <Button size="icon" className="h-7 w-7" onClick={handleSend} disabled={!input.trim() || context?.isStreaming}>
              <Send className="h-3 w-3" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
