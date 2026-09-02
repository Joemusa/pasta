"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input, Select } from "@/components/ui/fields";
import { SeverityDot } from "@/components/ui/severity";
import { useAppState } from "@/components/providers";
import {
  createOpportunityFromSignal,
  getSignals,
} from "@/lib/intelligence/service";
import { commercialImpactLabel } from "@/lib/scoring";
import type { IntelligenceSignal, SignalType } from "@/lib/types";
import { cn, formatDate } from "@/lib/utils";

const TYPES: { id: SignalType | "all"; label: string }[] = [
  { id: "all", label: "All" },
  { id: "competitor", label: "Competitors" },
  { id: "retailer", label: "Retailers" },
  { id: "promotion", label: "Promotions" },
  { id: "macro", label: "Macro" },
  { id: "consumer", label: "Consumer" },
  { id: "opportunity", label: "Opportunities" },
  { id: "threat", label: "Threats" },
];

export default function IntelligencePage() {
  const { period, lastScanAt, signals: scanned, liveCount, scanMessage } = useAppState();
  const [type, setType] = useState<SignalType | "all">("all");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [brand, setBrand] = useState("");
  const [retailer, setRetailer] = useState("");
  const [province, setProvince] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  void lastScanAt;

  const pool = scanned.length > 0 ? scanned : getSignals({ period: 30, type: "all" });
  const start = new Date();
  start.setDate(start.getDate() - period);
  const signals = pool
    .filter((s) => new Date(s.publishedAt) >= start)
    .filter((s) => (type === "all" ? true : s.signalType === type))
    .filter((s) => {
      const q = search.trim().toLowerCase();
      if (!q) return true;
      return `${s.title} ${s.summary} ${s.brand ?? ""} ${s.retailer ?? ""} ${s.source}`
        .toLowerCase()
        .includes(q);
    })
    .filter((s) => (category ? s.category === category : true))
    .filter((s) => (brand ? s.brand === brand : true))
    .filter((s) => (retailer ? s.retailer === retailer : true))
    .filter((s) => (province ? s.province === province : true));

  const brands = Array.from(new Set(pool.map((s) => s.brand).filter(Boolean))) as string[];
  const retailers = Array.from(new Set(pool.map((s) => s.retailer).filter(Boolean))) as string[];
  const categories = Array.from(new Set(pool.map((s) => s.category).filter(Boolean))) as string[];

  return (
    <div className="mx-auto max-w-[1100px] space-y-6">
      <div>
        <h1 className="text-[32px] font-semibold">Intelligence Feed</h1>
        <p className="text-sm text-muted">
          {liveCount > 0
            ? `${liveCount} live articles from the last scan, plus demo records where still useful.`
            : "Demo records until you click Run New Scan — that pulls live South African news feeds."}
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

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
        <Input placeholder="Search" value={search} onChange={(e) => setSearch(e.target.value)} />
        <Select value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </Select>
        <Select value={brand} onChange={(e) => setBrand(e.target.value)}>
          <option value="">All brands</option>
          {brands.map((b) => (
            <option key={b}>{b}</option>
          ))}
        </Select>
        <Select value={retailer} onChange={(e) => setRetailer(e.target.value)}>
          <option value="">All retailers</option>
          {retailers.map((r) => (
            <option key={r}>{r}</option>
          ))}
        </Select>
        <Select value={province} onChange={(e) => setProvince(e.target.value)}>
          <option value="">All provinces</option>
          <option value="gauteng">Gauteng</option>
          <option value="kwazulu-natal">KwaZulu-Natal</option>
          <option value="western-cape">Western Cape</option>
          <option value="eastern-cape">Eastern Cape</option>
          <option value="limpopo">Limpopo</option>
        </Select>
      </div>

      {toast ? <p className="text-sm text-teal">{toast}</p> : null}

      {signals.length === 0 ? (
        <EmptyState
          title="No competitor signals detected in the selected period."
          body="Adjust filters or run a scan to populate the intelligence feed."
        />
      ) : (
        <div className="space-y-4">
          {signals.map((s) => (
            <SignalCard
              key={s.id}
              signal={s}
              onCreate={() => {
                const created = createOpportunityFromSignal(s.id);
                setToast(
                  created
                    ? `Opportunity created: ${created.title}`
                    : "Could not create opportunity from this signal.",
                );
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function SignalCard({
  signal,
  onCreate,
}: {
  signal: IntelligenceSignal;
  onCreate: () => void;
}) {
  return (
    <article className="border border-rule bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <SeverityDot level={signal.severity} />
          <h2 className="mt-2 font-serif text-xl">{signal.title}</h2>
        </div>
        <p className="text-xs text-muted">{formatDate(signal.publishedAt)}</p>
      </div>
      <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="text-[11px] uppercase tracking-wider text-muted">Type</dt>
          <dd className="capitalize">{signal.signalType}</dd>
        </div>
        {signal.brand ? (
          <div>
            <dt className="text-[11px] uppercase tracking-wider text-muted">Brand</dt>
            <dd>{signal.brand}</dd>
          </div>
        ) : null}
        {signal.category ? (
          <div>
            <dt className="text-[11px] uppercase tracking-wider text-muted">Category</dt>
            <dd>{signal.category}</dd>
          </div>
        ) : null}
        {signal.retailer ? (
          <div>
            <dt className="text-[11px] uppercase tracking-wider text-muted">Retailer</dt>
            <dd>{signal.retailer}</dd>
          </div>
        ) : null}
      </dl>
      <p className="mt-4 text-sm leading-relaxed">{signal.summary}</p>
      <div className="mt-5 grid gap-4 border-t border-rule pt-4 md:grid-cols-3">
        <FactBlock kicker="Fact" body={signal.fact} />
        <FactBlock kicker="Why it matters to Unilever" body={signal.whyItMatters} />
        <FactBlock kicker="Suggested internal data query" body={signal.suggestedInternalQuery} />
      </div>
      <p className="mt-3 text-xs text-muted">
        Source: {signal.source} · Published: {formatDate(signal.publishedAt)} ·{" "}
        {signal.demo ? "Demo record" : "Live source"}
        {signal.commercialImpact === "unvalidated"
          ? ` · ${commercialImpactLabel("unvalidated")}`
          : null}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Link href={`/internal?signal=${signal.id}`}>
          <Button size="sm">Analyse</Button>
        </Link>
        {signal.sourceUrl ? (
          <a href={signal.sourceUrl} target="_blank" rel="noreferrer">
            <Button size="sm" variant="secondary">
              View Source
            </Button>
          </a>
        ) : (
          <Button size="sm" variant="secondary" disabled>
            View Source
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={onCreate}>
          Create Opportunity
        </Button>
      </div>
    </article>
  );
}

function FactBlock({ kicker, body }: { kicker: string; body: string }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-muted">{kicker}</p>
      <p className="mt-1 text-sm leading-relaxed">{body}</p>
    </div>
  );
}
