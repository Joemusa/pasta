"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { SeverityDot } from "@/components/ui/severity";
import {
  addOpportunityToBrief,
  dismissOpportunity,
  getOpportunities,
} from "@/lib/intelligence/service";
import { commercialImpactLabel } from "@/lib/scoring";
import type { Opportunity } from "@/lib/types";
import { cn } from "@/lib/utils";

function RadarInner() {
  const params = useSearchParams();
  const [tick, setTick] = useState(0);
  void tick;
  const opportunities = getOpportunities();
  const focus = params.get("id") ?? opportunities[0]?.id;
  const current = opportunities.find((o) => o.id === focus) ?? opportunities[0];

  if (!current) {
    return (
      <EmptyState
        title="No opportunities ranked yet."
        body="Run a scan so overlapping signals can generate an opportunity."
      />
    );
  }

  return (
    <div className="mx-auto max-w-[1100px] space-y-6">
      <div>
        <h1 className="text-[32px] font-semibold">Opportunity Radar</h1>
        <p className="text-sm text-muted">
          Ranked by relevance, magnitude, confidence, urgency, Unilever exposure and competitive intensity.
        </p>
      </div>
      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <ol className="space-y-2">
          {opportunities.map((o, i) => (
            <li key={o.id}>
              <Link
                href={`/opportunities?id=${o.id}`}
                className={cn(
                  "block border px-3 py-3",
                  current.id === o.id ? "border-ink bg-white" : "border-rule bg-white/60",
                )}
              >
                <p className="text-[11px] uppercase tracking-wider text-muted">
                  Opportunity #{i + 1}
                </p>
                <p className="font-medium">{o.title}</p>
                <p className="mt-1 text-sm text-teal">{o.opportunityScore} / 100</p>
              </Link>
            </li>
          ))}
        </ol>
        <OpportunityDetail
          opp={current}
          onDismiss={() => {
            dismissOpportunity(current.id);
            setTick((t) => t + 1);
          }}
          onBrief={() => {
            addOpportunityToBrief(current.id);
            setTick((t) => t + 1);
          }}
        />
      </div>
    </div>
  );
}

function OpportunityDetail({
  opp,
  onDismiss,
  onBrief,
}: {
  opp: Opportunity;
  onDismiss: () => void;
  onBrief: () => void;
}) {
  return (
    <article className="border border-rule bg-white p-6">
      <p className="text-[11px] uppercase tracking-wider text-muted">Opportunity</p>
      <h2 className="font-serif text-3xl">{opp.title}</h2>
      <div className="mt-4 flex flex-wrap gap-6 text-sm">
        <div>
          <p className="text-muted">Opportunity score</p>
          <p className="font-serif text-3xl">{opp.opportunityScore} / 100</p>
        </div>
        <div>
          <p className="text-muted">Potential impact</p>
          <SeverityDot
            level={opp.impact === "high" ? "high" : "medium"}
            label={commercialImpactLabel(opp.impact)}
          />
          <p className="mt-1 text-xs text-muted">{commercialImpactLabel("unvalidated")}</p>
        </div>
        <div>
          <p className="text-muted">Confidence</p>
          <p className="capitalize">{opp.confidence}</p>
        </div>
      </div>
      <p className="mt-5 text-sm leading-relaxed">{opp.description}</p>
      <h3 className="mt-6 text-[11px] uppercase tracking-wider text-muted">Evidence</h3>
      <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">
        {opp.evidence.map((e) => (
          <li key={e}>{e}</li>
        ))}
      </ol>
      <h3 className="mt-6 text-[11px] uppercase tracking-wider text-muted">Recommended action</h3>
      <p className="mt-2 text-sm">{opp.recommendedAction}</p>
      <div className="mt-6 flex flex-wrap gap-2">
        <Link href={`/internal?opportunity=${opp.id}`}>
          <Button>Analyse Internally</Button>
        </Link>
        <Button variant="secondary" onClick={onBrief}>
          Add to Weekly Brief
        </Button>
        <Button variant="danger" onClick={onDismiss}>
          Dismiss
        </Button>
      </div>
    </article>
  );
}

export default function OpportunitiesPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted">Loading radar…</p>}>
      <RadarInner />
    </Suspense>
  );
}
