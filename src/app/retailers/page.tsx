"use client";

import { getHeatmap, getRetailers } from "@/lib/intelligence/service";
import { cn } from "@/lib/utils";

function cellColor(score: number) {
  if (score >= 80) return "bg-[#f4d7d4] text-critical";
  if (score >= 60) return "bg-[#f6ddd0] text-high";
  if (score >= 40) return "bg-[#f3e6c8] text-medium";
  return "bg-[#dde8df] text-low";
}

export default function RetailersPage() {
  const retailers = getRetailers();
  const heat = getHeatmap();
  const brands = Array.from(new Set(heat.map((h) => h.brand)));
  const cols = Array.from(new Set(heat.map((h) => h.retailer)));

  return (
    <div className="mx-auto max-w-[1280px] space-y-8">
      <div>
        <h1 className="text-[32px] font-semibold">Retailers</h1>
        <p className="text-sm text-muted">
          Retailer intelligence and brand × banner competitive intensity.
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {retailers.map((r) => (
          <article key={r.id} className="border border-rule bg-white p-4">
            <div className="flex items-baseline justify-between">
              <h2 className="font-serif text-xl">{r.name}</h2>
              <span className="text-xs text-muted">{r.type}</span>
            </div>
            <dl className="mt-3 space-y-2 text-sm">
              <Item k="Promotions" v={r.currentPromotions} />
              <Item k="Private label" v={r.privateLabel} />
              <Item k="Price" v={r.priceChanges} />
              <Item k="Competitor activity" v={r.competitorActivity} />
              <Item k="Network" v={r.storeNetwork} />
              <Item k="Distribution" v={r.distributionChanges} />
              <Item k="Home Care" v={r.homeCareActivity} />
            </dl>
          </article>
        ))}
      </div>

      <section>
        <h2 className="font-serif text-2xl">Retailer × brand intensity</h2>
        <p className="mb-3 text-sm text-muted">
          Cell = competitive intensity score from the demo scan, not a financial forecast.
        </p>
        <div className="overflow-x-auto border border-rule bg-white">
          <table className="min-w-[720px] w-full text-left text-xs">
            <thead>
              <tr className="border-b border-rule">
                <th className="px-3 py-2 font-medium">Brand</th>
                {cols.map((c) => (
                  <th key={c} className="px-2 py-2 font-medium">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {brands.map((brand) => (
                <tr key={brand} className="border-b border-rule/80">
                  <th className="whitespace-nowrap px-3 py-2 text-left font-medium">{brand}</th>
                  {cols.map((retailer) => {
                    const cell = heat.find((h) => h.brand === brand && h.retailer === retailer);
                    const score = cell?.score ?? 0;
                    return (
                      <td key={retailer} className={cn("px-2 py-2 text-center", cellColor(score))}>
                        {score}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Item({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wider text-muted">{k}</dt>
      <dd className="mt-0.5 leading-relaxed">{v}</dd>
    </div>
  );
}
