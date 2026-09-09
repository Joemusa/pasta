import assert from "node:assert/strict";
import { test } from "node:test";
import { mergeSignals } from "./merge.ts";
import type { IntelligenceSignal } from "../types.ts";

function signal(partial: Partial<IntelligenceSignal> & Pick<IntelligenceSignal, "id" | "title">): IntelligenceSignal {
  return {
    source: "News24",
    sourceUrl: "https://www.news24.com/x",
    publishedAt: "2026-09-08T10:00:00.000Z",
    detectedAt: "2026-09-08T10:00:00.000Z",
    signalType: "consumer",
    category: "Laundry Detergent",
    brand: "OMO",
    retailer: null,
    province: null,
    summary: "South Africa laundry note",
    fact: "fact",
    interpretation: "",
    recommendation: "",
    whyItMatters: "",
    suggestedInternalQuery: "",
    severity: "low",
    confidence: "medium",
    commercialImpact: "unvalidated",
    demo: false,
    ...partial,
  };
}

test("mergeSignals keeps prior items when a later scan misses them", () => {
  const existing = [signal({ id: "a", title: "OMO promo" })];
  const incoming = [signal({ id: "b", title: "Sunlight dish" })];
  const merged = mergeSignals(existing, incoming, Date.parse("2026-09-09T00:00:00.000Z"));
  assert.equal(merged.length, 2);
  assert.deepEqual(merged.map((s) => s.id).sort(), ["a", "b"]);
});

test("mergeSignals lets incoming replace the same id", () => {
  const existing = [signal({ id: "a", title: "old", summary: "old" })];
  const incoming = [signal({ id: "a", title: "new", summary: "new" })];
  const merged = mergeSignals(existing, incoming);
  assert.equal(merged.length, 1);
  assert.equal(merged[0].title, "new");
});

test("mergeSignals drops demo rows and items older than 90 days", () => {
  const existing = [
    signal({ id: "demo", title: "demo", demo: true }),
    signal({
      id: "old",
      title: "old",
      publishedAt: "2025-01-01T00:00:00.000Z",
    }),
  ];
  const merged = mergeSignals(existing, [], Date.parse("2026-09-09T00:00:00.000Z"));
  assert.equal(merged.length, 0);
});
