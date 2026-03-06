"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { ProspectingTool } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Loader2, Wrench, Save } from "lucide-react";

export default function ProspectingToolsSettings() {
  const [tools, setTools] = useState<ProspectingTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<Partial<ProspectingTool>>({});

  useEffect(() => {
    loadTools();
  }, []);

  const loadTools = async () => {
    try {
      const res = await api.getProspectingTools();
      setTools(res.tools);
    } catch (err) {
      console.error("Failed to load tools:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (tool: ProspectingTool) => {
    setSaving(tool.id);
    try {
      const updated = await api.updateProspectingTool(tool.id, { is_enabled: !tool.is_enabled });
      setTools((prev) => prev.map((t) => (t.id === tool.id ? updated : t)));
    } catch (err) {
      console.error("Failed to toggle tool:", err);
    } finally {
      setSaving(null);
    }
  };

  const startEditing = (tool: ProspectingTool) => {
    setEditingId(tool.id);
    setEditForm({
      when_to_use: tool.when_to_use || "",
      cost_info: tool.cost_info || "",
    });
  };

  const handleSave = async (toolId: number) => {
    setSaving(toolId);
    try {
      const updated = await api.updateProspectingTool(toolId, editForm);
      setTools((prev) => prev.map((t) => (t.id === toolId ? updated : t)));
      setEditingId(null);
    } catch (err) {
      console.error("Failed to save tool:", err);
    } finally {
      setSaving(null);
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Wrench className="h-5 w-5" />
          Prospecting Tools
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          Gestisci gli strumenti Apify disponibili per l&apos;agente di prospecting.
          Le schede vengono iniettate nel system prompt di Claude.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {tools.map((tool) => (
          <div key={tool.id} className="border rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Checkbox
                  checked={tool.is_enabled}
                  onCheckedChange={() => handleToggle(tool)}
                  disabled={saving === tool.id}
                />
                <div>
                  <p className="font-medium text-sm">{tool.display_name}</p>
                  <p className="text-xs text-muted-foreground">{tool.description}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {tool.cost_info && (
                  <span className="text-xs bg-muted px-2 py-1 rounded">{tool.cost_info}</span>
                )}
                {editingId !== tool.id ? (
                  <Button variant="ghost" size="sm" onClick={() => startEditing(tool)} className="h-7 text-xs">
                    Modifica
                  </Button>
                ) : (
                  <Button
                    variant="default"
                    size="sm"
                    onClick={() => handleSave(tool.id)}
                    disabled={saving === tool.id}
                    className="h-7 text-xs gap-1"
                  >
                    {saving === tool.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
                    Salva
                  </Button>
                )}
              </div>
            </div>

            {editingId === tool.id && (
              <div className="grid gap-3 pt-2 border-t">
                <div>
                  <Label className="text-xs">Quando usare (guida per Claude)</Label>
                  <Input
                    value={editForm.when_to_use || ""}
                    onChange={(e) => setEditForm({ ...editForm, when_to_use: e.target.value })}
                    placeholder="Descrivi quando Claude deve usare questo tool..."
                    className="text-xs"
                  />
                </div>
                <div>
                  <Label className="text-xs">Info costo</Label>
                  <Input
                    value={editForm.cost_info || ""}
                    onChange={(e) => setEditForm({ ...editForm, cost_info: e.target.value })}
                    placeholder="es. ~$2.10 per 1000 risultati"
                    className="text-xs"
                  />
                </div>
              </div>
            )}

            {tool.sectors_strong && tool.sectors_strong.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {tool.sectors_strong.map((s) => (
                  <span key={s} className="text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded">
                    {s}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}

        {tools.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-4">
            Nessun tool configurato. Esegui la migration per aggiungere i tool predefiniti.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
