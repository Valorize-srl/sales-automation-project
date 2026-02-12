"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import Link from "next/link";
import { FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MessageBubble } from "@/components/chat/message-bubble";
import { ChatInput } from "@/components/chat/chat-input";
import { ICPPreviewCard } from "@/components/chat/icp-preview-card";
import { api } from "@/lib/api";
import { ChatMessage, ICPExtracted } from "@/types";

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [extractedIcp, setExtractedIcp] = useState<ICPExtracted | null>(null);
  const [uploadedFileContent, setUploadedFileContent] = useState<string | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed && !uploadedFileContent) return;
    if (isStreaming) return;

    const userContent = uploadedFileName
      ? `${trimmed}\n\n[Attached file: ${uploadedFileName}]`
      : trimmed;

    const userMessage: ChatMessage = { role: "user", content: userContent };
    const newMessages = [...messages, userMessage];

    setMessages([...newMessages, { role: "assistant", content: "" }]);
    setInput("");
    setIsStreaming(true);
    setExtractedIcp(null);

    // Send only clean content to API (without file attachment text)
    const apiMessages = [
      ...messages.map((m) => ({ role: m.role, content: m.content })),
      { role: "user", content: trimmed || "Please analyze the uploaded document." },
    ];

    await api.streamChat(
      apiMessages,
      uploadedFileContent,
      // onText
      (text) => {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          updated[updated.length - 1] = {
            ...last,
            content: last.content + text,
          };
          return updated;
        });
      },
      // onIcpExtracted
      (data) => {
        setExtractedIcp(data as unknown as ICPExtracted);
      },
      // onDone
      () => {
        setIsStreaming(false);
        setUploadedFileContent(null);
        setUploadedFileName(null);
      },
      // onError
      (err) => {
        console.error("Chat error:", err);
        setIsStreaming(false);
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          updated[updated.length - 1] = {
            ...last,
            content: `Error: ${err.message}. Please try again.`,
          };
          return updated;
        });
      }
    );
  };

  const handleFileSelect = async (file: File) => {
    setUploading(true);
    try {
      const result = await api.uploadFile(file);
      setUploadedFileContent(result.text);
      setUploadedFileName(result.filename);
    } catch (err) {
      console.error("Upload error:", err);
    } finally {
      setUploading(false);
    }
  };

  const handleFileClear = () => {
    setUploadedFileContent(null);
    setUploadedFileName(null);
  };

  const rawInput = messages
    .map((m) => `${m.role}: ${m.content}`)
    .join("\n");

  return (
    <div className="flex flex-col h-[calc(100vh-48px)]">
      <div className="flex items-center justify-between px-1 pb-4">
        <div>
          <h1 className="text-2xl font-bold">AI Chat</h1>
          <p className="text-sm text-muted-foreground">
            Define your Ideal Customer Profile through conversation
          </p>
        </div>
        <Link href="/chat/icp">
          <Button variant="outline" size="sm" className="gap-1">
            <FileText className="h-4 w-4" />
            Saved ICPs
          </Button>
        </Link>
      </div>

      <ScrollArea className="flex-1 px-1">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full min-h-[300px]">
            <div className="text-center">
              <p className="text-muted-foreground mb-2">
                Start a conversation to define your ICP.
              </p>
              <p className="text-sm text-muted-foreground">
                Describe your ideal customer, or upload a document.
              </p>
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble
            key={i}
            message={msg}
            isStreaming={isStreaming && i === messages.length - 1}
          />
        ))}
        {extractedIcp && (
          <ICPPreviewCard data={extractedIcp} rawInput={rawInput} />
        )}
        <div ref={bottomRef} />
      </ScrollArea>

      <ChatInput
        input={input}
        onInputChange={setInput}
        onSend={handleSend}
        onFileSelect={handleFileSelect}
        onFileClear={handleFileClear}
        uploadedFileName={uploading ? "Uploading..." : uploadedFileName}
        isStreaming={isStreaming || uploading}
      />
    </div>
  );
}
