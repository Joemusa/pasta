"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Textarea, Select } from "@/components/ui/fields";
import { INTERNAL_AGENTS } from "@/lib/internal-agents";
import {
  getOpportunity,
  getSignalById,
  runInternalQuery,
} from "@/lib/intelligence/service";
import type { InternalQueryResult } from "@/lib/types";

function InternalInner() {
  const params = useSearchParams();
  const signalId = params.get("signal");
  const opportunityId = params.get("opportunity");
  const signal = signalId ? getSignalById(signalId) : undefined;
  const opportunity = opportunityId ? getOpportunity(opportunityId) : undefined;

  const defaultQuery = useMemo(() => {
    if (signal) return signal.suggestedInternalQuery;
    if (opportunity) {
      return `Compare ${opportunity.brand} against named competitors on value share, volume share, average selling price, distribution and promotional intensity over the last 12 weeks. Identify regions and retailers where the competitor gained while ${opportunity.brand} declined.`;
    }
    return "Compare MAQ and OMO value share, volume share, average selling price, distribution and promotional intensity over the last 12 weeks. Identify regions and retailers where MAQ gained share while OMO declined.";
  }, [signal, opportunity]);

  const [agent, setAgent] = useState(INTERNAL_AGENTS[0].id);
  const [query, setQuery] = useState(defaultQuery);
  const [result, setResult] = useState<InternalQueryResult | null>(null);

  return (
    <div className="mx-auto max-w-[900px] space-y-6">
      <div>
        <h1 className="text-[32px] font-semibold">Internal Analysis</h1>
        <p className="text-sm text-muted">
          Connect external intelligence with Unilever POS agents. Demo replies until the commercial stack is wired.
        </p>
      </div>

      {signal ? (
        <p className="border border-rule bg-white px-4 py-3 text-sm">
          Linked signal · {signal.title}
        </p>
      ) : null}
      {opportunity ? (
        <p className="border border-rule bg-white px-4 py-3 text-sm">
          Linked opportunity · {opportunity.title}
        </p>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2">
        {INTERNAL_AGENTS.map((a) => (
          <button
            key={a.id}
            type="button"
            onClick={() => setAgent(a.id)}
            className={`border p-4 text-left ${agent === a.id ? "border-ink bg-white" : "border-rule bg-white/70"}`}
          >
            <p className="font-medium">{a.name}</p>
            <p className="mt-1 text-xs text-muted">{a.expertise}</p>
          </button>
        ))}
      </div>

      <div className="border border-rule bg-white p-4">
        <label className="text-[11px] uppercase tracking-wider text-muted">
          Query sent to Internal Intelligence
        </label>
        <Textarea className="mt-2" rows={5} value={query} onChange={(e) => setQuery(e.target.value)} />
        <div className="mt-3 flex items-center gap-2">
          <Select value={agent} onChange={(e) => setAgent(e.target.value)}>
            {INTERNAL_AGENTS.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </Select>
          <Button
            onClick={() =>
              setResult(
                runInternalQuery({
                  agent,
                  query,
                  signalId: signal?.id ?? null,
                }),
              )
            }
          >
            Run query
          </Button>
        </div>
      </div>

      {!result ? (
        <EmptyState title="No internal data connection yet." body="Select an agent and run the query to see a structured demo response." />
      ) : (
        <article className="border border-rule bg-white p-5 space-y-4">
          <p className="text-xs uppercase tracking-wider text-muted">
            {result.status === "ready" ? "Demo result" : "Unavailable"} · {INTERNAL_AGENTS.find((a) => a.id === result.agent)?.name}
          </p>
          <Block title="Fact" body={result.fact} />
          <Block title="Interpretation" body={result.interpretation} />
          <Block title="Recommendation" body={result.recommendation} />
        </article>
      )}
    </div>
  );
}

function Block({ title, body }: { title: string; body: string }) {
  return (
    <div>
      <h2 className="text-[11px] uppercase tracking-wider text-muted">{title}</h2>
      <p className="mt-1 text-sm leading-relaxed">{body}</p>
    </div>
  );
}

export default function InternalPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted">Loading internal analysis…</p>}>
      <InternalInner />
    </Suspense>
  );
}
