"use client";

import { useState, useEffect, KeyboardEvent } from "react";
import { Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { api } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { Person, PersonUpdate } from "@/types";

interface EditPersonDialogProps {
  person: Person | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdated: () => void;
}

export function EditPersonDialog({ person, open, onOpenChange, onUpdated }: EditPersonDialogProps) {
  const { toast } = useToast();
  const [saving, setSaving] = useState(false);

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [phone, setPhone] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [industry, setIndustry] = useState("");
  const [location, setLocation] = useState("");

  // Client tags as array (stored comma-separated)
  const [clientTags, setClientTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");

  useEffect(() => {
    if (person && open) {
      setFirstName(person.first_name || "");
      setLastName(person.last_name || "");
      setEmail(person.email || "");
      setCompanyName(person.company_name || "");
      setPhone(person.phone || "");
      setLinkedinUrl(person.linkedin_url || "");
      setIndustry(person.industry || "");
      setLocation(person.location || "");
      // Parse comma-separated client_tag into array
      const tags = person.client_tag
        ? person.client_tag.split(",").map((t) => t.trim()).filter(Boolean)
        : [];
      setClientTags(tags);
      setTagInput("");
    }
  }, [person, open]);

  const addTag = (value: string) => {
    const tag = value.trim();
    if (tag && !clientTags.includes(tag)) {
      setClientTags((prev) => [...prev, tag]);
    }
    setTagInput("");
  };

  const removeTag = (tag: string) => {
    setClientTags((prev) => prev.filter((t) => t !== tag));
  };

  const handleTagKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTag(tagInput);
    }
    if (e.key === "Backspace" && !tagInput && clientTags.length > 0) {
      setClientTags((prev) => prev.slice(0, -1));
    }
  };

  const handleSave = async () => {
    if (!person) return;
    setSaving(true);
    try {
      const data: PersonUpdate = {
        first_name: firstName,
        last_name: lastName,
        email,
        company_name: companyName || undefined,
        phone: phone || undefined,
        linkedin_url: linkedinUrl || undefined,
        industry: industry || undefined,
        location: location || undefined,
        client_tag: clientTags.length > 0 ? clientTags.join(", ") : undefined,
      };
      await api.updatePerson(person.id, data);
      toast({ title: "Person Updated", description: `${firstName} ${lastName} saved.` });
      onUpdated();
      onOpenChange(false);
    } catch (err) {
      toast({
        title: "Update Failed",
        description: err instanceof Error ? err.message : "Failed to update person",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Edit Person</DialogTitle>
        </DialogHeader>
        <Separator />
        <div className="space-y-3 pt-1 max-h-[60vh] overflow-y-auto pr-1">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">First Name</Label>
              <Input value={firstName} onChange={(e) => setFirstName(e.target.value)} className="h-8 text-sm" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Last Name</Label>
              <Input value={lastName} onChange={(e) => setLastName(e.target.value)} className="h-8 text-sm" />
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Email</Label>
            <Input value={email} onChange={(e) => setEmail(e.target.value)} className="h-8 text-sm" />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Company</Label>
            <Input value={companyName} onChange={(e) => setCompanyName(e.target.value)} className="h-8 text-sm" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">Phone</Label>
              <Input value={phone} onChange={(e) => setPhone(e.target.value)} className="h-8 text-sm" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">LinkedIn URL</Label>
              <Input value={linkedinUrl} onChange={(e) => setLinkedinUrl(e.target.value)} className="h-8 text-sm" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">Industry</Label>
              <Input value={industry} onChange={(e) => setIndustry(e.target.value)} className="h-8 text-sm" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Location</Label>
              <Input value={location} onChange={(e) => setLocation(e.target.value)} className="h-8 text-sm" />
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Client / Project</Label>
            <div className="flex flex-wrap gap-1.5 p-2 border rounded-md min-h-[36px] bg-background focus-within:ring-1 focus-within:ring-ring">
              {clientTags.map((tag) => (
                <Badge key={tag} variant="secondary" className="gap-1 text-xs">
                  {tag}
                  <button onClick={() => removeTag(tag)} className="hover:text-destructive">
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
              <input
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={handleTagKeyDown}
                onBlur={() => { if (tagInput.trim()) addTag(tagInput); }}
                placeholder={clientTags.length === 0 ? "Type and press Enter..." : ""}
                className="flex-1 min-w-[100px] bg-transparent outline-none text-sm"
              />
            </div>
            <p className="text-[10px] text-muted-foreground">Press Enter or comma to add a tag</p>
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={handleSave} disabled={saving || !firstName || !email} className="gap-1">
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            {saving ? "Saving..." : "Save"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
