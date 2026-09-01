"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { getMacro, getOpportunities, getOverview, getSignals } from "@/lib/intelligence/service";

export default function BriefPage() {
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const overview = getOverview(14);
  const signals = getSignals({ period: 14, type: "all" });
  const opportunities = getOpportunities().slice(0, 3);
  const threats = overview.threats.slice(0, 3);
  const macro = getMacro().slice(0, 4);
  const competitorMoves = signals.filter((s) => s.signalType === "competitor" || s.signalType === "promotion");
  const retailerMoves = signals.filter((s) => s.signalType === "retailer");

  const summary = useMemo(
    () =>
      `Home Care is being reshaped by value competition (MAQ, private label, Britelite) against a tight household-cash backdrop (fuel, food inflation, SASSA timing). The lead Unilever question is OMO and Surf defence in Usave, Shoprite and Boxer — not a generic brand campaign.`,
    [],
  );

  return (
    <div className="mx-auto max-w-[800px] space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3 no-print">
        <div>
          <h1 className="text-[32px] font-semibold">Weekly Home Care Intelligence Brief</h1>
          <p className="text-sm text-muted">
            {generatedAt ? `Generated ${new Date(generatedAt).toLocaleString("en-ZA")}` : "Draft from the current demo scan"}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setGeneratedAt(new Date().toISOString())}>
            Generate Brief
          </Button>
          <Button onClick={() => window.print()}>Download PDF</Button>
        </div>
      </div>

      <article className="space-y-8 border border-rule bg-white p-6">
        <section>
          <h2 className="font-serif text-2xl">Executive summary</h2>
          <p className="mt-2 text-sm leading-relaxed">{summary}</p>
        </section>
        <section>
          <h2 className="font-serif text-2xl">3 things management needs to know</h2>
          <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm">
            <li>MAQ is the primary competitive threat, now showing up beyond hard-discount into leaflet features.</li>
            <li>Gauteng water interruptions and grant-week timing will distort weekly volume — read POS with that calendar.</li>
            <li>Sunlight bar is exposed on price (Usave EC) and listings (new Boxer KZN stores).</li>
          </ol>
        </section>
        <section>
          <h2 className="font-serif text-2xl">Competitor moves</h2>
          <ul className="mt-2 space-y-1 text-sm">
            {competitorMoves.slice(0, 5).map((s) => (
              <li key={s.id}>{s.title}</li>
            ))}
          </ul>
        </section>
        <section>
          <h2 className="font-serif text-2xl">Retailer moves</h2>
          <ul className="mt-2 space-y-1 text-sm">
            {retailerMoves.map((s) => (
              <li key={s.id}>{s.title}</li>
            ))}
          </ul>
        </section>
        <section>
          <h2 className="font-serif text-2xl">Macro triggers</h2>
          <ul className="mt-2 space-y-1 text-sm">
            {macro.map((m) => (
              <li key={m.id}>
                {m.title} — {m.potentialHomecareImpact}
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h2 className="font-serif text-2xl">Top 3 threats</h2>
          <ul className="mt-2 space-y-1 text-sm">
            {threats.map((t) => (
              <li key={t.id}>
                {t.title} ({t.level}) — {t.recommendedResponse}
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h2 className="font-serif text-2xl">Top 3 opportunities</h2>
          <ul className="mt-2 space-y-2 text-sm">
            {opportunities.map((o) => (
              <li key={o.id}>
                <strong>{o.title}</strong> · {o.opportunityScore}/100 · {o.recommendedAction}
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h2 className="font-serif text-2xl">Recommended actions</h2>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">
            {opportunities.map((o) => (
              <li key={o.id}>{o.recommendedAction}</li>
            ))}
          </ol>
        </section>
        <section>
          <h2 className="font-serif text-2xl">Internal data queries</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            <li>OMO vs MAQ vs Surf, 12 weeks, by retailer and province.</li>
            <li>Sunlight bar vs Britelite vs Rave in Usave and Boxer.</li>
            <li>Domestos vs Harpic in Clicks and Dis-Chem around the aisle reset.</li>
          </ul>
        </section>
      </article>
    </div>
  );
}
