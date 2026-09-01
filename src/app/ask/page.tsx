"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/fields";
import { askIntelligence } from "@/lib/intelligence/service";
import type { AskResponse } from "@/lib/types";

const PROMPTS = [
  "What are the biggest threats to OMO?",
  "Where is MAQ gaining share?",
  "What changed in Home Care this week?",
  "Which retailer has the biggest opportunity?",
  "Which competitor is becoming more aggressive?",
  "Why is Sunlight Laundry Bar growing?",
  "What external factors could affect Home Care sales?",
];

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState<AskResponse | null>(null);

  function ask(q: string) {
    setQuestion(q);
    setResponse(askIntelligence(q));
  }

  return (
    <div className="mx-auto max-w-[800px] space-y-6">
      <div>
        <h1 className="text-[32px] font-semibold">Ask Home Care Intelligence</h1>
        <p className="text-sm text-muted">
          Ask anything about the South African Home Care market.
        </p>
      </div>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (question.trim()) ask(question.trim());
        }}
      >
        <Input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question..."
        />
        <Button type="submit">Ask</Button>
      </form>
      <div className="flex flex-wrap gap-2">
        {PROMPTS.map((p) => (
          <button
            key={p}
            type="button"
            className="border border-rule bg-white px-3 py-1.5 text-left text-xs text-muted hover:text-ink-text"
            onClick={() => ask(p)}
          >
            {p}
          </button>
        ))}
      </div>
      {response ? (
        <article className="space-y-4 border border-rule bg-white p-5">
          <Section title="Answer" body={response.answer} />
          <div>
            <h2 className="text-[11px] uppercase tracking-wider text-muted">Evidence</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
              {response.evidence.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </div>
          <Section title="Why it matters" body={response.whyItMatters} />
          <Section title="Recommended action" body={response.recommendedAction} />
          <Section title="Internal data query" body={response.internalDataQuery} />
        </article>
      ) : null}
    </div>
  );
}

function Section({ title, body }: { title: string; body: string }) {
  return (
    <div>
      <h2 className="text-[11px] uppercase tracking-wider text-muted">{title}</h2>
      <p className="mt-1 text-sm leading-relaxed">{body}</p>
    </div>
  );
}
