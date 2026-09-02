"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { SeverityDot } from "@/components/ui/severity";
import { useAppState } from "@/components/providers";
import {
  dismissOpportunity,
  getKpiDelta,
  getOverview,
  getProvinces,
  getSignals,
} from "@/lib/intelligence/service";
import { commercialImpactLabel } from "@/lib/scoring";
import type { Opportunity, PeriodDays, Threat } from "@/lib/types";
import { cn } from "@/lib/utils";
import { SouthAfricaMap } from "@/components/map/SouthAfricaMap";
import { NewsList } from "@/components/news/NewsList";

const PERIODS: { id: PeriodDays; label: string }[] = [
  { id: 7, label: "Last 7 days" },
  { id: 14, label: "Last 14 days" },
  { id: 30, label: "Last 30 days" },
];

export default function HomePage() {
  const { period, setPeriod, lastScanAt, liveCount, scanMessage, signals: scanned } = useAppState();
  const [dismissed, setDismissed] = useState<string[]>([]);
  const overview = getOverview(period);
  void lastScanAt;
  void dismissed;
  const [activeOpp, setActiveOpp] = useState<Opportunity | null>(
    overview.opportunities[0] ?? null,
  );
  const liveStories = scanned.filter((s) => !s.demo);
  const latestNews = (liveStories.length > 0 ? liveStories : getSignals({ period, type: "all" }))
    .slice()
    .sort((a, b) => +new Date(b.publishedAt) - +new Date(a.publishedAt))
    .slice(0, 6);

  return (
    <div className="mx-auto max-w-[1280px] space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-[32px] font-semibold leading-tight text-ink-text">
            Home Care Intelligence
          </h1>
          <p className="mt-1 max-w-xl text-sm text-muted">
            What changed in the market and where can Unilever move the needle?
          </p>
          {scanMessage ? <p className="mt-2 text-sm text-teal">{scanMessage}</p> : null}
          {liveCount > 0 ? (
            <p className="mt-1 text-xs text-muted">
              {liveCount} live stories with source links. Open the Intelligence Feed for the full list.
            </p>
          ) : (
            <p className="mt-1 text-xs text-muted">
              Click Run New Scan to pull live South African news with publisher links.
            </p>
          )}
        </div>
        <div className="flex border border-rule bg-white" role="tablist" aria-label="Date range">
          {PERIODS.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setPeriod(p.id)}
              className={cn(
                "px-3 py-2 text-xs tracking-wide",
                period === p.id
                  ? "bg-ink text-white"
                  : "text-muted hover:text-ink-text",
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <section aria-label="Executive KPIs" className="grid grid-cols-2 gap-px border border-rule bg-rule md:grid-cols-3 xl:grid-cols-6">
        {overview.kpis.map((kpi) => {
          const delta = getKpiDelta(kpi.value, kpi.previous);
          return (
            <article key={kpi.key} className="bg-paper px-4 py-4">
              <p className="text-[11px] uppercase tracking-[0.12em] text-muted">
                {kpi.label}
              </p>
              <p className="mt-2 font-serif text-3xl text-ink-text">{kpi.value}</p>
              <p
                className={cn(
                  "mt-2 text-xs",
                  delta.direction === "up"
                    ? "text-high"
                    : delta.direction === "down"
                      ? "text-low"
                      : "text-muted",
                )}
              >
                {delta.text}
              </p>
              <div className="mt-2">
                <SeverityDot level={kpi.severity} />
              </div>
            </article>
          );
        })}
      </section>

      <section>
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl text-ink-text">Latest news</h2>
            <p className="text-sm text-muted">Headlines with the publisher that ran them</p>
          </div>
          <Link href="/intelligence" className="text-sm text-teal hover:underline">
            Full feed
          </Link>
        </div>
        <NewsList items={latestNews} />
      </section>

      <section>
        <div className="mb-4">
          <h2 className="text-2xl text-ink-text">Top 3 Opportunities</h2>
          <p className="text-sm text-muted">Where Unilever could move the needle</p>
        </div>
        {overview.opportunities.length === 0 ? (
          <EmptyState title="No opportunities in this period." body="Run a scan to populate the intelligence feed." />
        ) : (
          <div className="grid gap-4 lg:grid-cols-3">
            {overview.opportunities.slice(0, 3).map((opp, index) => (
              <OpportunityCard
                key={opp.id}
                opp={opp}
                index={index}
                selected={activeOpp?.id === opp.id}
                onSelect={() => setActiveOpp(opp)}
                onDismiss={() => {
                  dismissOpportunity(opp.id);
                  setDismissed((ids) => [...ids, opp.id]);
                  setActiveOpp(null);
                }}
              />
            ))}
          </div>
        )}
      </section>

      {activeOpp ? <OpportunityEvidence opp={activeOpp} /> : null}

      <section>
        <h2 className="mb-4 text-2xl text-ink-text">Top Competitive Threats</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {overview.threats.map((threat) => (
            <ThreatCard key={threat.id} threat={threat} />
          ))}
        </div>
      </section>

      <section>
        <div className="mb-4 flex items-end justify-between">
          <div>
            <h2 className="text-2xl text-ink-text">Signals by province</h2>
            <p className="text-sm text-muted">Click a province for the local picture</p>
          </div>
          <Link href="/macro" className="text-sm text-teal hover:underline">
            Macro triggers
          </Link>
        </div>
        <SouthAfricaMap provinces={getProvinces()} />
      </section>
    </div>
  );
}

function OpportunityCard({
  opp,
  index,
  selected,
  onSelect,
  onDismiss,
}: {
  opp: Opportunity;
  index: number;
  selected: boolean;
  onSelect: () => void;
  onDismiss: () => void;
}) {
  return (
    <article
      className={cn(
        "flex h-full flex-col border bg-white p-5",
        selected ? "border-ink" : "border-rule",
      )}
    >
      <button type="button" onClick={onSelect} className="text-left">
        <p className="text-[11px] uppercase tracking-[0.16em] text-muted">
          {String(index + 1).padStart(2, "0")}
        </p>
        <h3 className="mt-2 font-serif text-xl text-ink-text">{opp.title}</h3>
      </button>
      <dl className="mt-4 space-y-2 text-sm">
        <div className="flex justify-between gap-4">
          <dt className="text-muted">Potential impact</dt>
          <dd>
            <SeverityDot
              level={opp.impact === "high" ? "high" : opp.impact === "medium" ? "medium" : "low"}
              label={commercialImpactLabel(opp.impact)}
            />
          </dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-muted">Category</dt>
          <dd>{opp.category}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-muted">Score</dt>
          <dd className="font-medium">{opp.opportunityScore} / 100</dd>
        </div>
      </dl>
      <p className="mt-4 flex-1 text-sm leading-relaxed text-muted">
        {opp.description}
      </p>
      <div className="mt-5 flex flex-wrap gap-2">
        <Link href={`/internal?opportunity=${opp.id}`}>
          <Button size="sm">Analyse Internally</Button>
        </Link>
        <Button size="sm" variant="secondary" onClick={onSelect}>
          View Evidence
        </Button>
        <Button size="sm" variant="ghost" onClick={onDismiss}>
          Dismiss
        </Button>
      </div>
    </article>
  );
}

function OpportunityEvidence({ opp }: { opp: Opportunity }) {
  return (
    <section className="border border-rule bg-white p-5">
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted">Evidence</p>
      <h3 className="mt-1 font-serif text-xl">{opp.title}</h3>
      <div className="mt-4 grid gap-6 md:grid-cols-3">
        <div>
          <p className="text-[11px] uppercase tracking-wider text-muted">Signal</p>
          <ul className="mt-2 space-y-1 text-sm">
            {opp.evidence.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wider text-muted">Why this matters</p>
          <p className="mt-2 text-sm leading-relaxed">{opp.description}</p>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wider text-muted">Recommended action</p>
          <p className="mt-2 text-sm leading-relaxed">{opp.recommendedAction}</p>
          <p className="mt-3 text-xs text-muted">
            {commercialImpactLabel("unvalidated")} until POS is joined.
          </p>
        </div>
      </div>
    </section>
  );
}

function ThreatCard({ threat }: { threat: Threat }) {
  return (
    <article className="border border-rule bg-white p-5">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-serif text-lg">{threat.title}</h3>
        <SeverityDot level={threat.level} />
      </div>
      <p className="mt-3 text-xs uppercase tracking-wider text-muted">{threat.category}</p>
      <ul className="mt-3 space-y-1 text-sm text-ink-text">
        {threat.signals.map((s) => (
          <li key={s} className="flex gap-2">
            <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-ink-text" />
            {s}
          </li>
        ))}
      </ul>
      <p className="mt-4 text-sm">
        <span className="text-muted">Recommended response · </span>
        {threat.recommendedResponse}
      </p>
    </article>
  );
}
