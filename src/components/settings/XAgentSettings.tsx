"use client";

import { useActionState } from "react";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/fields";
import { saveXSettingsAction, type XSaveState } from "@/app/settings/x-actions";

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
  const [state, action, pending] = useActionState<XSaveState, FormData>(
    saveXSettingsAction,
    null,
  );

  return (
    <form action={action} className="space-y-4">
      <p className="text-sm text-muted">
        Collects public Home Care posts through the official X API v2 recent search. The bearer
        token stays on the server as <code className="text-ink-text">X_BEARER_TOKEN</code> — it is
        never shown here. Token {initial.tokenConfigured ? "is configured" : "is not configured"}.
      </p>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" name="enabled" defaultChecked={initial.enabled} />
        Enable X agent
      </label>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-sm">
          <span className="mb-1 block text-[11px] uppercase tracking-wider text-muted">Max posts</span>
          <Input
            type="number"
            name="maxPosts"
            min={1}
            max={40}
            defaultValue={initial.maxPosts}
            key={`max-${initial.maxPosts}`}
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-[11px] uppercase tracking-wider text-muted">
            Relevance threshold
          </span>
          <Input
            type="number"
            name="relevanceThreshold"
            min={0}
            max={90}
            defaultValue={initial.relevanceThreshold}
            key={`thr-${initial.relevanceThreshold}`}
          />
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-[11px] uppercase tracking-wider text-muted">
            Lookback hours (max {initial.maxLookbackHours})
          </span>
          <Input
            type="number"
            name="lookbackHours"
            min={1}
            max={initial.maxLookbackHours}
            defaultValue={initial.lookbackHours}
            key={`hrs-${initial.lookbackHours}`}
          />
        </label>
      </div>
      <label className="block text-sm">
        <span className="mb-1 block text-[11px] uppercase tracking-wider text-muted">
          Extra search clause (optional)
        </span>
        <Textarea
          rows={2}
          name="extraQuery"
          defaultValue={initial.extraQuery}
          placeholder='e.g. ("handy andy" OR domestos)'
          key={`q-${initial.extraQuery}`}
        />
      </label>
      <p className="text-xs text-muted">
        Frequency follows the existing scan scheduler (Run New Scan and the 6-hour cron). Recent
        search only covers the last 7 days. Low-relevance posts below the threshold stay out of the
        feed.
      </p>
      <Button type="submit" variant="secondary" disabled={pending}>
        {pending ? "Saving…" : "Save X settings"}
      </Button>
      {state?.message ? (
        <p className={`text-sm ${state.ok ? "text-teal" : "text-critical"}`}>{state.message}</p>
      ) : null}
    </form>
  );
}
