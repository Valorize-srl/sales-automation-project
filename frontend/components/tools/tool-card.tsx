"use client";

import { LucideIcon } from "lucide-react";

interface ToolCardProps {
  name: string;
  description: string;
  icon: LucideIcon;
  cost: string;
  onClick: () => void;
}

export function ToolCard({ name, description, icon: Icon, cost, onClick }: ToolCardProps) {
  return (
    <button
      onClick={onClick}
      className="border rounded-lg p-5 text-left hover:bg-muted/50 hover:border-primary/30 transition-all group"
    >
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-md bg-primary/10 text-primary group-hover:bg-primary/20 transition-colors">
          <Icon className="h-5 w-5" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-sm">{name}</h3>
          <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{description}</p>
          <p className="text-xs text-muted-foreground mt-2 font-mono">{cost}</p>
        </div>
      </div>
    </button>
  );
}
