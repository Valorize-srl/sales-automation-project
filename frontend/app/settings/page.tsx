"use client";

import { Settings as SettingsIcon } from "lucide-react";
import ExchangeRateSettings from "@/components/settings/exchange-rate-settings";

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <SettingsIcon className="h-8 w-8" />
            Settings
          </h1>
          <p className="text-muted-foreground mt-1">
            Manage application settings and preferences
          </p>
        </div>
      </div>

      <div className="grid gap-6">
        <ExchangeRateSettings />
      </div>
    </div>
  );
}
