"use client";

import { useMemo, useState } from "react";
import { Download, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MacroChart } from "./MacroChart";
import { formatMacroPeriod, formatPct } from "@/lib/intelligence/macro-commentary";
import type { MacroSnapshot } from "@/lib/types";

function kpiValue(value: number | null, period: string | null): { value: string; hint: string } {
  if (value == null) return { value: "—", hint: "Not available" };
  return {
    value: formatPct(value),
    hint: period ? formatMacroPeriod(period) : "",
  };
}

export function MacroSheet({ initial }: { initial: MacroSnapshot }) {
  const [snapshot, setSnapshot] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const kpis = useMemo(() => {
    const { latest } = snapshot;
    const inflation = kpiValue(latest.inflation, latest.inflationPeriod);
    const rate = kpiValue(latest.policyRate, latest.policyPeriod);
    const real =
      latest.realRate == null
        ? { value: "—", hint: "Need both series" }
        : {
            value: `${latest.realRate >= 0 ? "+" : ""}${latest.realRate.toFixed(1)} pp`,
            hint: "Policy rate minus CPI",
          };
    const cpiChange =
      latest.inflation == null || latest.inflationYearAgo == null
        ? { value: "—", hint: "12-month change" }
        : {
            value: `${latest.inflation - latest.inflationYearAgo >= 0 ? "+" : ""}${(latest.inflation - latest.inflationYearAgo).toFixed(1)} pp`,
            hint: "CPI vs 12 months earlier",
          };
    return [
      { label: "CPI inflation", ...inflation },
      { label: "SARB policy rate", ...rate },
      { label: "Real policy rate", ...real },
      { label: "CPI vs year ago", ...cpiChange },
    ];
  }, [snapshot]);

  async function refresh() {
    setBusy(true);
    setMessage("");
    try {
      const res = await fetch("/api/macro?refresh=1", { method: "GET", cache: "no-store" });
      if (!res.ok) throw new Error(`Refresh failed (${res.status})`);
      const next = (await res.json()) as MacroSnapshot;
      setSnapshot(next);
      setMessage(
        next.points.length
          ? `Updated ${next.points.length} monthly points from live sources.`
          : "Sources responded but returned no points.",
      );
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Refresh failed");
    } finally {
      setBusy(false);
    }
  }

  function downloadCsv() {
    window.location.href = "/api/macro-csv";
  }

  const empty = snapshot.points.length === 0;

  return (
    <div className="mx-auto max-w-[960px] space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-[32px] font-semibold">Inflation & interest rates</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            Live South African CPI inflation and the SARB policy rate, with a read on
            what the trend can mean for Unilever Home Care shopper behaviour.
          </p>
          {message ? <p className="mt-2 text-sm text-teal">{message}</p> : null}
          {snapshot.errors.length > 0 ? (
            <p className="mt-2 text-sm text-medium">{snapshot.errors.join(" · ")}</p>
          ) : null}
        </div>
        <div className="flex flex-col items-stretch gap-2 sm:items-end">
          <Button variant="secondary" onClick={downloadCsv} disabled={empty}>
            <Download size={14} />
            Download CSV
          </Button>
          <Button variant="primary" onClick={refresh} disabled={busy}>
            <RefreshCw size={14} className={busy ? "animate-spin" : undefined} />
            Refresh series
          </Button>
        </div>
      </div>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {kpis.map((kpi) => (
          <div key={kpi.label} className="border border-rule bg-white px-4 py-3">
            <p className="text-[11px] uppercase tracking-wider text-muted">{kpi.label}</p>
            <p className="mt-1 font-serif text-2xl">{kpi.value}</p>
            <p className="text-xs text-muted">{kpi.hint}</p>
          </div>
        ))}
      </section>

      <section className="border border-rule bg-white p-5">
        <h2 className="font-serif text-xl">Trend</h2>
        <p className="mt-1 text-sm text-muted">
          Monthly CPI year-on-year % and the SARB policy rate. Empty months are
          skipped; lines connect across gaps.
        </p>
        {empty ? (
          <p className="mt-8 text-sm text-muted">
            No series loaded yet. Click Refresh series.
          </p>
        ) : (
          <div className="mt-4">
            <MacroChart points={snapshot.points} />
          </div>
        )}
      </section>

      <section className="border border-rule bg-white p-5">
        <h2 className="font-serif text-xl">What this can mean for Home Care</h2>
        <p className="mt-3 text-sm leading-6">{snapshot.commentary.headline}</p>
        {snapshot.commentary.facts.length > 0 ? (
          <div className="mt-4">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted">
              What the series show
            </h3>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6">
              {snapshot.commentary.facts.map((fact) => (
                <li key={fact}>{fact}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {snapshot.commentary.behaviours.length > 0 ? (
          <div className="mt-5">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted">
              Possible shopper behaviour
            </h3>
            <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-6">
              {snapshot.commentary.behaviours.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>

      <section className="border border-rule bg-white p-5">
        <h2 className="font-serif text-xl">Sources</h2>
        <p className="mt-1 text-sm text-muted">
          Live official series, not scraped news. World Bank annual figures are
          used only if the monthly BIS feed fails.
        </p>
        <ul className="mt-4 divide-y divide-rule">
          {snapshot.sources.map((source) => (
            <li key={source.id} className="flex items-center justify-between py-2 text-sm">
              <span>
                {source.name}
                <span className="ml-2 text-xs text-muted">{source.frequency}</span>
              </span>
              <a className="text-teal hover:underline" href={source.url} target="_blank" rel="noreferrer">
                {source.url.replace("https://", "")}
              </a>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-muted">
          Last fetched {snapshot.fetchedAt ? new Date(snapshot.fetchedAt).toLocaleString("en-ZA") : "—"}.
        </p>
      </section>
    </div>
  );
}
