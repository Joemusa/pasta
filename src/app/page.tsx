"use client";

import { useMemo, useState } from "react";
import { Input, Select } from "@/components/ui/fields";
import { NewsList } from "@/components/news/NewsList";
import { useAppState } from "@/components/providers";
import type { IntelligenceSignal, PeriodDays, SignalType } from "@/lib/types";
import { cn } from "@/lib/utils";

const TYPES: { id: SignalType | "all"; label: string }[] = [
  { id: "all", label: "All" },
  { id: "competitor", label: "Competitors" },
  { id: "retailer", label: "Retailers" },
  { id: "promotion", label: "Promotions" },
  { id: "macro", label: "Macro" },
];

const PERIODS: { id: PeriodDays; label: string }[] = [
  { id: 14, label: "Last 14 days" },
  { id: 30, label: "Last 30 days" },
  { id: 90, label: "Last 90 days" },
];

export default function IntelligenceFeedPage() {
  const { period, setPeriod, signals, liveCount, scanMessage, bootDone } = useAppState();
  const [type, setType] = useState<SignalType | "all">("all");
  const [search, setSearch] = useState("");
  const [source, setSource] = useState("");

  const pool = useMemo(() => signals.filter((s) => !s.demo), [signals]);

  const sources = useMemo(
    () => Array.from(new Set(pool.map((s) => s.source))).sort((a, b) => a.localeCompare(b)),
    [pool],
  );

  const start = new Date();
  start.setDate(start.getDate() - period);

  const stories = pool
    .filter((s) => new Date(s.publishedAt) >= start)
    .filter((s) => (type === "all" ? true : s.signalType === type))
    .filter((s) => (source ? s.source === source : true))
    .filter((s) => matchesSearch(s, search))
    .sort((a, b) => +new Date(b.publishedAt) - +new Date(a.publishedAt));

  const loading = !bootDone && pool.length === 0;

  return (
    <div className="mx-auto max-w-[820px] space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-[32px] font-semibold">Intelligence Feed</h1>
          <p className="mt-1 max-w-xl text-sm text-muted">
            South African Home Care news, with what it means for the Unilever
            category, brand and product.
          </p>
          <p className="mt-2 text-sm text-muted">
            {loading
              ? "Loading live South African news…"
              : liveCount === 0
                ? "No Home Care stories yet. Click Run New Scan."
                : `${stories.length} shown · ${liveCount} live South African stories.`}
          </p>
          {scanMessage ? <p className="mt-1 text-sm text-teal">{scanMessage}</p> : null}
        </div>
        <div className="flex border border-rule bg-white" role="tablist" aria-label="Date range">
          {PERIODS.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setPeriod(p.id)}
              className={cn(
                "px-3 py-2 text-xs tracking-wide",
                period === p.id ? "bg-ink text-white" : "text-muted hover:text-ink-text",
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap gap-1">
        {TYPES.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setType(t.id)}
            className={cn(
              "border px-3 py-1.5 text-xs",
              type === t.id ? "border-ink bg-ink text-white" : "border-rule bg-white text-muted",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <Input placeholder="Search headlines" value={search} onChange={(e) => setSearch(e.target.value)} />
        <Select className="w-full" value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">All sources</option>
          {sources.map((name) => (
            <option key={name}>{name}</option>
          ))}
        </Select>
      </div>

      <NewsList
        items={stories}
        emptyTitle={loading ? "Loading live news…" : "No Home Care stories in this view."}
        emptyBody={
          loading
            ? "Fetching South African RSS feeds."
            : "Try All, a wider date range, or Run New Scan."
        }
      />
    </div>
  );
}

function matchesSearch(signal: IntelligenceSignal, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return `${signal.title} ${signal.source} ${signal.brand ?? ""} ${signal.retailer ?? ""}`
    .toLowerCase()
    .includes(q);
}
