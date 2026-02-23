"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DollarSign, Save, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

export default function ExchangeRateSettings() {
  const [rate, setRate] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    loadRate();
  }, []);

  const loadRate = async () => {
    setLoading(true);
    try {
      const setting = await api.getSetting("usd_eur_exchange_rate");
      setRate(setting.value);
    } catch (error) {
      console.error("Failed to load exchange rate:", error);
      setMessage({ type: "error", text: "Failed to load exchange rate" });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    const rateNum = parseFloat(rate);
    if (isNaN(rateNum) || rateNum < 0.01 || rateNum > 2.0) {
      setMessage({ type: "error", text: "Please enter a valid rate between 0.01 and 2.00" });
      return;
    }

    setSaving(true);
    setMessage(null);
    try {
      await api.updateSetting("usd_eur_exchange_rate", rate);
      setMessage({ type: "success", text: "Exchange rate updated successfully" });
    } catch (error) {
      console.error("Failed to save exchange rate:", error);
      setMessage({ type: "error", text: "Failed to save exchange rate" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <DollarSign className="h-5 w-5" />
          USD/EUR Exchange Rate
        </CardTitle>
        <CardDescription>
          Manually set the exchange rate for display purposes. All costs are calculated in USD.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading...
          </div>
        ) : (
          <>
            <div className="space-y-2">
              <Label htmlFor="exchange-rate">Exchange Rate</Label>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">1 USD =</span>
                <Input
                  id="exchange-rate"
                  type="number"
                  min="0.01"
                  max="2.00"
                  step="0.01"
                  value={rate}
                  onChange={(e) => setRate(e.target.value)}
                  className="w-32"
                  placeholder="0.92"
                />
                <span className="text-sm text-muted-foreground">EUR</span>
              </div>
              <p className="text-xs text-muted-foreground">
                Valid range: 0.01 to 2.00
              </p>
            </div>

            <Button onClick={handleSave} disabled={saving} className="gap-2">
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4" />
                  Save Exchange Rate
                </>
              )}
            </Button>

            {message && (
              <div
                className={`text-sm p-2 rounded ${
                  message.type === "success"
                    ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                    : "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                }`}
              >
                {message.text}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
