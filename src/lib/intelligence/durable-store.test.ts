import assert from "node:assert/strict";
import { test } from "node:test";
import { snapshotFromRow } from "./durable-store.ts";
import type { IntelligenceSignal } from "../types.ts";

function signal(id: string): IntelligenceSignal {
  return {
    id,
    title: "Sunlight dishwashing South Africa",
    source: "News24",
    sourceUrl: "https://www.news24.com/x",
    publishedAt: "2026-09-09T08:00:00.000Z",
    detectedAt: "2026-09-09T08:00:00.000Z",
    signalType: "consumer",
    category: "Dishwashing",
    brand: "Sunlight",
    retailer: null,
    province: null,
    summary: "SA Home Care",
    fact: "fact",
    interpretation: "",
    recommendation: "",
    whyItMatters: "",
    suggestedInternalQuery: "",
    severity: "low",
    confidence: "medium",
    commercialImpact: "unvalidated",
    demo: false,
  };
}

test("snapshotFromRow hydrates a JSONB feed row and drops demo stories", () => {
  const row = {
    last_scan_at: "2026-09-09T11:00:00.000Z",
    signals: [signal("live"), { ...signal("demo"), demo: true }],
  };
  const cache = snapshotFromRow(row);
  assert.equal(cache?.lastScanAt, "2026-09-09T11:00:00.000Z");
  assert.equal(cache?.signals.length, 1);
  assert.equal(cache?.signals[0]?.id, "live");
});

test("snapshotFromRow parses a JSON string payload", () => {
  const cache = snapshotFromRow({
    last_scan_at: "2026-09-09T11:00:00.000Z",
    signals: JSON.stringify([signal("json")]),
  });
  assert.equal(cache?.signals[0]?.id, "json");
});

test("snapshotFromRow returns null for an empty snapshot", () => {
  assert.equal(snapshotFromRow({ last_scan_at: "", signals: [] }), null);
  assert.equal(snapshotFromRow(null), null);
});
