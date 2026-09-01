"use client";

import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { SeverityDot } from "@/components/ui/severity";
import { Select } from "@/components/ui/fields";
import { getCompetitors } from "@/lib/intelligence/service";
import type { CategoryName, CompetitorBrand } from "@/lib/types";

const CATEGORIES: CategoryName[] = [
  "Laundry Detergent",
  "Laundry Bars",
  "Dishwashing",
  "Toilet Cleaners",
  "Fabric Conditioners",
  "Hard Surface Cleaners",
];

const PAIRS = [
  { id: "omo-maq", a: "OMO", b: "MAQ", category: "Laundry Detergent" },
  { id: "sunlight-britelite", a: "Sunlight", b: "Britelite", category: "Laundry Bars" },
  { id: "domestos-harpic", a: "Domestos", b: "Harpic", category: "Toilet Cleaners" },
];

const COMPARE: Record<string, { metric: string; a: number; b: number; unit: string }[]> = {
  "omo-maq": [
    { metric: "Price pressure", a: 55, b: 88, unit: "index" },
    { metric: "Promotion", a: 60, b: 90, unit: "index" },
    { metric: "Distribution", a: 85, b: 62, unit: "index" },
    { metric: "Marketing", a: 70, b: 58, unit: "index" },
    { metric: "Consumer sentiment", a: 64, b: 71, unit: "index" },
  ],
  "sunlight-britelite": [
    { metric: "Price pressure", a: 50, b: 86, unit: "index" },
    { metric: "Promotion", a: 48, b: 55, unit: "index" },
    { metric: "Distribution", a: 88, b: 60, unit: "index" },
    { metric: "Marketing", a: 40, b: 22, unit: "index" },
    { metric: "Consumer sentiment", a: 72, b: 50, unit: "index" },
  ],
  "domestos-harpic": [
    { metric: "Price pressure", a: 35, b: 52, unit: "index" },
    { metric: "Promotion", a: 50, b: 78, unit: "index" },
    { metric: "Distribution", a: 80, b: 58, unit: "index" },
    { metric: "Marketing", a: 62, b: 58, unit: "index" },
    { metric: "Consumer sentiment", a: 68, b: 61, unit: "index" },
  ],
};

export default function CompetitorsPage() {
  const brands = getCompetitors();
  const [pair, setPair] = useState(PAIRS[0].id);
  const selected = PAIRS.find((p) => p.id === pair)!;
  const chart = COMPARE[pair].map((row) => ({
    metric: row.metric,
    [selected.a]: row.a,
    [selected.b]: row.b,
  }));

  const grouped = useMemo(() => {
    return CATEGORIES.map((cat) => ({
      cat,
      items: brands.filter((b) => b.category === cat),
    })).filter((g) => g.items.length > 0);
  }, [brands]);

  return (
    <div className="mx-auto max-w-[1200px] space-y-8">
      <div>
        <h1 className="text-[32px] font-semibold">Competitors</h1>
        <p className="text-sm text-muted">
          Brand intelligence across South African Home Care. Share movement is CONNECT DATA until POS is joined.
        </p>
      </div>

      <section className="border border-rule bg-white p-5">
        <h2 className="font-serif text-2xl">Comparison</h2>
        <p className="mt-1 text-sm text-muted">
          Indices are directional from the demo scan — not financial impact.
        </p>
        <div className="mt-4">
          <Select value={pair} onChange={(e) => setPair(e.target.value)}>
            {PAIRS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.a} vs {p.b}
              </option>
            ))}
          </Select>
        </div>
        <div className="mt-4 h-72 w-full overflow-x-auto">
          <ResponsiveContainer width="100%" height="100%" minWidth={480}>
            <BarChart data={chart} barGap={4}>
              <CartesianGrid stroke="#d4cec2" vertical={false} />
              <XAxis dataKey="metric" tick={{ fontSize: 12, fill: "#6d665c" }} />
              <YAxis tick={{ fontSize: 12, fill: "#6d665c" }} />
              <Tooltip />
              <Legend />
              <Bar dataKey={selected.a} fill="#1e4f48" />
              <Bar dataKey={selected.b} fill="#c2410c" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-2 text-xs text-muted">
          Market share and volume/value growth require internal POS — not shown as invented numbers.
        </p>
      </section>

      {grouped.map((g) => (
        <section key={g.cat}>
          <h2 className="mb-3 font-serif text-2xl">{g.cat}</h2>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {g.items.map((brand) => (
              <BrandCard key={brand.id} brand={brand} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function BrandCard({ brand }: { brand: CompetitorBrand }) {
  return (
    <article className="border border-rule bg-white p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-serif text-lg">{brand.name}</h3>
          <p className="text-xs text-muted">{brand.company}</p>
        </div>
        <SeverityDot
          level={brand.threatLevel === "own" ? "own" : brand.threatLevel}
          label={brand.threatLevel === "own" ? "OWN BRAND" : `THREAT ${brand.threatLevel.toUpperCase()}`}
        />
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
        <Row k="Price" v={brand.priceActivity} />
        <Row k="Promotion" v={brand.promotionalActivity} />
        <Row k="Distribution" v={brand.distribution} />
        <Row k="Marketing" v={brand.marketingActivity} />
        <Row k="Social" v={brand.socialActivity} />
        <Row k="Retailer" v={brand.retailerActivity} />
      </dl>
      <p className="mt-3 text-xs">
        <span className="text-muted">Internal share · </span>
        {brand.shareMovement}
      </p>
      <p className="mt-2 text-sm leading-relaxed">{brand.aiInterpretation}</p>
    </article>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between gap-2 border-b border-rule/70 py-1">
      <dt className="text-muted">{k}</dt>
      <dd className="capitalize">{v}</dd>
    </div>
  );
}
