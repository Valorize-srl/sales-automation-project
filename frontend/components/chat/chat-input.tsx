"use client";

import { useRef } from "react";
import { Paperclip, SendHorizontal, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";

interface ChatInputProps {
  input: string;
  onInputChange: (value: string) => void;
  onSend: () => void;
  onFileSelect: (file: File) => void;
  onFileClear: () => void;
  uploadedFileName: string | null;
  isStreaming: boolean;
}

export function ChatInput({
  input,
  onInputChange,
  onSend,
  onFileSelect,
  onFileClear,
  uploadedFileName,
  isStreaming,
}: ChatInputProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onFileSelect(file);
      // Reset input so the same file can be selected again
      e.target.value = "";
    }
  };

  return (
    <div className="border-t bg-background p-4">
      {uploadedFileName && (
        <div className="mb-2 flex items-center gap-2">
          <Badge variant="secondary" className="gap-1">
            <Paperclip className="h-3 w-3" />
            {uploadedFileName}
            <button onClick={onFileClear} className="ml-1 hover:text-destructive">
              <X className="h-3 w-3" />
            </button>
          </Badge>
        </div>
      )}
      <div className="flex items-end gap-2">
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          className="hidden"
          onChange={handleFileChange}
        />
        <Button
          variant="ghost"
          size="icon"
          className="shrink-0"
          onClick={() => fileInputRef.current?.click()}
          disabled={isStreaming}
        >
          <Paperclip className="h-4 w-4" />
        </Button>
        <Textarea
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe your ideal customer..."
          className="min-h-[44px] max-h-[120px] resize-none"
          rows={1}
          disabled={isStreaming}
        />
        <Button
          size="icon"
          className="shrink-0"
          onClick={onSend}
          disabled={isStreaming || (!input.trim() && !uploadedFileName)}
        >
          <SendHorizontal className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
