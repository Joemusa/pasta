"use client";

import { useMemo, useState } from "react";
import { Download } from "lucide-react";
import { Input, Select } from "@/components/ui/fields";
import { Button } from "@/components/ui/button";
import { NewsList } from "@/components/news/NewsList";
import { useAppState } from "@/components/providers";
import { newsCsvFilename, newsSignalsToCsv } from "@/lib/news-csv";
import type { IntelligenceSignal, PeriodDays } from "@/lib/types";
import { cn } from "@/lib/utils";

const PERIODS: { id: PeriodDays; label: string }[] = [
  { id: 14, label: "Last 14 days" },
  { id: 30, label: "Last 30 days" },
  { id: 90, label: "Last 90 days" },
];

export default function IntelligenceFeedPage() {
  const { period, setPeriod, signals, liveCount, scanMessage, bootDone } = useAppState();
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
    .filter((s) => (source ? s.source === source : true))
    .filter((s) => matchesSearch(s, search))
    .sort((a, b) => +new Date(b.publishedAt) - +new Date(a.publishedAt));

  const loading = !bootDone && pool.length === 0;

  function downloadCsv() {
    const csv = newsSignalsToCsv(stories);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = newsCsvFilename();
    link.click();
    URL.revokeObjectURL(url);
  }

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
        <div className="flex flex-col items-stretch gap-2 sm:items-end">
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
          <Button
            type="button"
            variant="secondary"
            onClick={downloadCsv}
            disabled={stories.length === 0}
          >
            <Download size={14} />
            Download CSV
          </Button>
        </div>
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
            : "Try a wider date range, or Run New Scan."
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
