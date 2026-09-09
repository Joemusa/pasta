"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/fields";

export type XStatus = {
  enabled: boolean;
  maxPosts: number;
  relevanceThreshold: number;
  lookbackHours: number;
  extraQuery: string;
  tokenConfigured: boolean;
  api: string;
  maxLookbackHours: number;
};

export function XAgentSettings({ initial }: { initial: XStatus }) {
  const [status, setStatus] = useState<XStatus>(initial);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function save(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setMessage(null);
    try {
      const res = await fetch("/api/x-config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled: status.enabled,
          maxPosts: status.maxPosts,
          relevanceThreshold: status.relevanceThreshold,
          lookbackHours: status.lookbackHours,
          extraQuery: status.extraQuery,
        }),
      });
      const json = (await res.json()) as XStatus & { error?: string };
      if (!res.ok) throw new Error(json.error ?? "Save failed");
      setStatus(json);
      setMessage("X agent settings saved. They apply on the next scan.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="space-y-4" onSubmit={save}>
      <p className="text-sm text-muted">
        Collects public Home Care posts through the official X API v2 recent search. The bearer
        token stays on the server as <code className="text-ink-text">X_BEARER_TOKEN</code> — it is
        never shown here. Token {status.tokenConfigured ? "is configured" : "is not configured"}.
      </p>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={status.enabled}
          onChange={(e) => setStatus({ ...status, enabled: e.target.checked })}
        />
        Enable X agent
      </label>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-sm">
          <span className="mb-1 block text-[11px] uppercase tracking-wider text-muted">Max posts</span>
          <Input
            type="number"
            min={1}
            max={40}
            value={status.maxPosts}
            onChange={(e) => setStatus({ ...status, maxPosts: Number(e.target.value) })}
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-[11px] uppercase tracking-wider text-muted">
            Relevance threshold
          </span>
          <Input
            type="number"
            min={0}
            max={90}
            value={status.relevanceThreshold}
            onChange={(e) => setStatus({ ...status, relevanceThreshold: Number(e.target.value) })}
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-[11px] uppercase tracking-wider text-muted">
            Lookback hours (max {status.maxLookbackHours})
          </span>
          <Input
            type="number"
            min={1}
            max={status.maxLookbackHours}
            value={status.lookbackHours}
            onChange={(e) => setStatus({ ...status, lookbackHours: Number(e.target.value) })}
          />
        </label>
      </div>
      <label className="block text-sm">
        <span className="mb-1 block text-[11px] uppercase tracking-wider text-muted">
          Extra search clause (optional)
        </span>
        <Textarea
          rows={2}
          value={status.extraQuery}
          onChange={(e) => setStatus({ ...status, extraQuery: e.target.value })}
          placeholder='e.g. ("handy andy" OR domestos)'
        />
      </label>
      <p className="text-xs text-muted">
        Frequency follows the existing scan scheduler (Run New Scan and the 6-hour cron). Recent
        search only covers the last 7 days. Low-relevance posts below the threshold stay out of the
        feed.
      </p>
      <Button type="submit" variant="secondary" disabled={saving}>
        {saving ? "Saving…" : "Save X settings"}
      </Button>
      {message ? <p className="text-sm text-teal">{message}</p> : null}
    </form>
  );
}
