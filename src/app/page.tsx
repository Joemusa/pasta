"use client";

import Link from "next/link";
import { useAppState } from "@/components/providers";
import { NewsList } from "@/components/news/NewsList";
import type { PeriodDays } from "@/lib/types";
import { cn } from "@/lib/utils";

const PERIODS: { id: PeriodDays; label: string }[] = [
  { id: 14, label: "Last 14 days" },
  { id: 30, label: "Last 30 days" },
  { id: 90, label: "Last 90 days" },
];

export default function HomePage() {
  const { period, setPeriod, liveCount, scanMessage, signals, bootDone } = useAppState();
  const start = new Date();
  start.setDate(start.getDate() - period);
  const latestNews = signals
    .filter((s) => !s.demo && new Date(s.publishedAt) >= start)
    .slice()
    .sort((a, b) => +new Date(b.publishedAt) - +new Date(a.publishedAt))
    .slice(0, 10);
  const waiting = !bootDone && signals.length === 0;

  return (
    <div className="mx-auto max-w-[820px] space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-[32px] font-semibold leading-tight text-ink-text">
            Home Care news
          </h1>
          <p className="mt-1 max-w-xl text-sm text-muted">
            Only South African Home Care news. Each story includes what it means
            for the Unilever category, brand and product.
          </p>
          {scanMessage ? <p className="mt-2 text-sm text-teal">{scanMessage}</p> : null}
          {liveCount > 0 ? (
            <p className="mt-1 text-xs text-muted">
              {liveCount} live stories. Open the Intelligence Feed for the full list.
            </p>
          ) : null}
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

      <section>
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl text-ink-text">Latest news</h2>
            <p className="text-sm text-muted">Headlines plus Unilever category, brand and product impact</p>
          </div>
          <Link href="/intelligence" className="text-sm text-teal hover:underline">
            Full feed
          </Link>
        </div>
        <NewsList
          items={latestNews}
          emptyTitle={waiting ? "Loading live news…" : "No Home Care stories yet."}
          emptyBody={
            waiting
              ? "Fetching South African RSS feeds."
              : "Click Run New Scan to pull headlines that name Unilever Home Care brands or categories."
          }
        />
      </section>
    </div>
  );
}
