"use client";

import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { Check, X, Pencil } from "lucide-react";

interface EditableFieldProps {
  value: string | null | undefined;
  onSave: (value: string) => Promise<void> | void;
  label: string;
  type?: "text" | "textarea" | "url";
  placeholder?: string;
  icon?: React.ReactNode;
}

export function EditableField({
  value,
  onSave,
  label,
  type = "text",
  placeholder,
  icon,
}: EditableFieldProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value ?? "");
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);

  useEffect(() => {
    if (editing) {
      setDraft(value ?? "");
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [editing, value]);

  const handleSave = async () => {
    const trimmed = draft.trim();
    if (trimmed === (value ?? "")) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      await onSave(trimmed);
      setEditing(false);
    } catch (err) {
      console.error("Save failed:", err);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setDraft(value ?? "");
    setEditing(false);
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter" && type !== "textarea") {
      e.preventDefault();
      handleSave();
    } else if (e.key === "Escape") {
      handleCancel();
    }
  };

  if (editing) {
    return (
      <div className="flex items-start gap-1.5 w-full">
        <span className="text-muted-foreground text-xs w-28 shrink-0 pt-1.5">{label}</span>
        <div className="flex-1 flex items-start gap-1">
          {type === "textarea" ? (
            <textarea
              ref={inputRef as React.RefObject<HTMLTextAreaElement>}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={handleKeyDown}
              onBlur={() => {
                // Small delay to allow button clicks
                setTimeout(() => {
                  if (document.activeElement !== inputRef.current) handleSave();
                }, 150);
              }}
              placeholder={placeholder}
              rows={3}
              className="flex-1 px-2 py-1 text-sm border border-primary rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-primary resize-y min-h-[60px]"
              disabled={saving}
            />
          ) : (
            <input
              ref={inputRef as React.RefObject<HTMLInputElement>}
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={handleKeyDown}
              onBlur={() => {
                setTimeout(() => {
                  if (document.activeElement !== inputRef.current) handleSave();
                }, 150);
              }}
              placeholder={placeholder}
              className="flex-1 px-2 py-0.5 text-sm border border-primary rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-primary h-7"
              disabled={saving}
            />
          )}
        </div>
      </div>
    );
  }

  const displayValue = value?.trim();

  return (
    <div
      className="flex items-start gap-1.5 w-full group cursor-pointer rounded-md px-1 -mx-1 py-0.5 hover:bg-accent/50 transition-colors"
      onClick={() => setEditing(true)}
    >
      <span className="text-muted-foreground text-xs w-28 shrink-0 pt-0.5">{label}</span>
      <div className="flex-1 flex items-start gap-1 min-w-0">
        {icon && <span className="shrink-0 mt-0.5">{icon}</span>}
        {displayValue ? (
          <span className={`text-sm break-words ${type === "url" ? "text-primary" : ""}`}>
            {displayValue}
          </span>
        ) : (
          <span className="text-sm text-muted-foreground/50 italic">
            {placeholder || `Aggiungi ${label.toLowerCase()}...`}
          </span>
        )}
        <Pencil className="h-3 w-3 text-muted-foreground/0 group-hover:text-muted-foreground/50 shrink-0 ml-auto mt-0.5 transition-colors" />
      </div>
    </div>
  );
}
