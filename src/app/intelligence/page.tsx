"use client";

import { useMemo, useState } from "react";
import { Input, Select } from "@/components/ui/fields";
import { NewsList } from "@/components/news/NewsList";
import { useAppState } from "@/components/providers";
import { getSignals } from "@/lib/intelligence/service";
import type { IntelligenceSignal, SignalType } from "@/lib/types";
import { cn } from "@/lib/utils";

const TYPES: { id: SignalType | "all"; label: string }[] = [
  { id: "all", label: "All" },
  { id: "competitor", label: "Competitors" },
  { id: "retailer", label: "Retailers" },
  { id: "promotion", label: "Promotions" },
  { id: "macro", label: "Macro" },
];

export default function IntelligencePage() {
  const { period, signals: scanned, liveCount, scanMessage } = useAppState();
  const [type, setType] = useState<SignalType | "all">("all");
  const [search, setSearch] = useState("");
  const [source, setSource] = useState("");

  const pool = useMemo(() => {
    const fallback = getSignals({ period: 30, type: "all" });
    const base = scanned.length > 0 ? scanned : fallback;
    const live = base.filter((s) => !s.demo);
    return liveCount > 0 || live.length > 0 ? live : base;
  }, [scanned, liveCount]);

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

  return (
    <div className="mx-auto max-w-[820px] space-y-6">
      <div>
        <h1 className="text-[32px] font-semibold">Intelligence Feed</h1>
        <p className="text-sm text-muted">
          {liveCount > 0
            ? `${stories.length} stories from South African sources.`
            : "Demo headlines until you click Run New Scan. Product notes appear only when a Unilever brand or a direct competitor is named."}
        </p>
        {scanMessage ? <p className="mt-1 text-sm text-teal">{scanMessage}</p> : null}
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

      <NewsList items={stories} />
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
