"use client";

import { SouthAfricaMap } from "@/components/map/SouthAfricaMap";
import { SeverityDot } from "@/components/ui/severity";
import { getMacro, getProvinces } from "@/lib/intelligence/service";
import { formatDate } from "@/lib/utils";

const TYPES = {
  "consumer-economy": "Consumer economy",
  "cash-flow": "Government / cash flow",
  infrastructure: "Infrastructure",
  weather: "Weather",
} as const;

export default function MacroPage() {
  const triggers = getMacro();
  return (
    <div className="mx-auto max-w-[1100px] space-y-8">
      <div>
        <h1 className="text-[32px] font-semibold">Macro Triggers</h1>
        <p className="text-sm text-muted">
          Economic, infrastructure and environmental events that can move Home Care demand.
        </p>
      </div>

      <SouthAfricaMap provinces={getProvinces()} />

      <div className="space-y-4">
        {triggers.map((t) => (
          <article key={t.id} className="border border-rule bg-white p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-wider text-muted">{TYPES[t.type]}</p>
                <h2 className="font-serif text-xl">{t.title}</h2>
              </div>
              <SeverityDot level={t.severity} />
            </div>
            <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <dt className="text-muted">Location</dt>
                <dd>{t.location}</dd>
              </div>
              <div>
                <dt className="text-muted">Date</dt>
                <dd>
                  {formatDate(t.startDate)}
                  {t.endDate ? ` – ${formatDate(t.endDate)}` : " · ongoing"}
                </dd>
              </div>
              <div>
                <dt className="text-muted">Affected consumers</dt>
                <dd>{t.affectedConsumers}</dd>
              </div>
              <div>
                <dt className="text-muted">Potential Home Care impact</dt>
                <dd>{t.potentialHomecareImpact}</dd>
              </div>
            </dl>
            <p className="mt-3 text-sm">{t.description}</p>
            <p className="mt-3 text-sm">
              <span className="text-muted">Recommended internal query · </span>
              {t.recommendedInternalQuery}
            </p>
          </article>
        ))}
      </div>
    </div>
  );
}
