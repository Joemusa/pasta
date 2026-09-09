import assert from "node:assert/strict";
import { test } from "node:test";
import type { IntelligenceSignal } from "../types.ts";
import type { LiveCache } from "./live-store.ts";
import {
  clearMemoryFeed,
  persistLocalFeed,
  readMemoryFeed,
  rememberFeed,
  resolveFeed,
  resolveLiveFeed,
} from "./feed-store.ts";

function signal(id: string, title: string, extra: Partial<IntelligenceSignal> = {}): IntelligenceSignal {
  return {
    id,
    title,
    source: "News24",
    sourceUrl: "https://www.news24.com/x",
    publishedAt: "2026-09-09T08:00:00.000Z",
    detectedAt: "2026-09-09T08:00:00.000Z",
    signalType: "consumer",
    category: "Laundry Detergent",
    brand: "OMO",
    retailer: null,
    province: null,
    summary: "South Africa OMO laundry note",
    fact: "fact",
    interpretation: "",
    recommendation: "",
    whyItMatters: "",
    suggestedInternalQuery: "",
    severity: "low",
    confidence: "medium",
    commercialImpact: "unvalidated",
    demo: false,
    ...extra,
  };
}

const bundled: LiveCache = {
  lastScanAt: "2026-09-01T00:00:00.000Z",
  signals: [signal("bundle", "Bundled Sunlight dishwashing South Africa")],
};

test("resolveFeed prefers in-memory scan results over durable storage", async () => {
  clearMemoryFeed();
  rememberFeed({ lastScanAt: "2026-09-09T10:00:00.000Z", signals: [signal("mem", "Memory OMO")] });
  const durable: LiveCache = {
    lastScanAt: "2026-09-09T09:00:00.000Z",
    signals: [signal("dur", "Durable Sunlight")],
  };
  const resolved = await resolveFeed({
    readDurable: async () => durable,
    readBundled: () => bundled,
  });
  assert.equal(resolved.signals[0]?.id, "mem");
  assert.equal(resolved.origin, "memory");
  clearMemoryFeed();
});

test("resolveFeed uses durable snapshot when this instance has no memory", async () => {
  clearMemoryFeed();
  const durable: LiveCache = {
    lastScanAt: "2026-09-09T09:00:00.000Z",
    signals: [signal("dur", "Durable Sunlight dishwashing South Africa")],
  };
  const resolved = await resolveFeed({
    readDurable: async () => durable,
    readRuntime: () => ({ lastScanAt: "", signals: [] }),
    readBundled: () => bundled,
  });
  assert.equal(resolved.origin, "durable");
  assert.equal(resolved.signals[0]?.id, "dur");
  assert.equal(readMemoryFeed()?.signals[0]?.id, "dur");
  clearMemoryFeed();
});

test("resolveFeed falls back to bundled snapshot when durable and runtime are empty", async () => {
  clearMemoryFeed();
  const resolved = await resolveFeed({
    readDurable: async () => null,
    readRuntime: () => ({ lastScanAt: "", signals: [] }),
    readBundled: () => bundled,
  });
  assert.equal(resolved.origin, "bundled");
  assert.equal(resolved.signals[0]?.id, "bundle");
  assert.equal(readMemoryFeed(), null);
  clearMemoryFeed();
});

test("resolveLiveFeed never returns the bundled snapshot", async () => {
  clearMemoryFeed();
  const live = await resolveLiveFeed({
    readDurable: async () => null,
    readRuntime: () => ({ lastScanAt: "", signals: [] }),
    readBundled: () => bundled,
  });
  assert.equal(live, null);
  clearMemoryFeed();
});

test("persistLocalFeed remembers the scan, writes durable storage, and drops demo rows", async () => {
  clearMemoryFeed();
  let written: LiveCache | null = null;
  let runtime: LiveCache | null = null;
  const stored = await persistLocalFeed(
    {
      lastScanAt: "2026-09-09T11:00:00.000Z",
      signals: [
        signal("p", "Takealot: OMO 10% off"),
        signal("demo", "Demo headline", { demo: true }),
      ],
    },
    {
      writeRuntime: (cache) => {
        runtime = cache;
      },
      writeDurable: async (cache) => {
        written = cache;
      },
    },
  );
  assert.equal(stored.signals.length, 1);
  assert.equal(written?.signals[0]?.id, "p");
  assert.equal(runtime?.signals.length, 1);
  assert.equal(readMemoryFeed()?.lastScanAt, "2026-09-09T11:00:00.000Z");

  clearMemoryFeed();
  const fromDurable = await resolveFeed({
    readDurable: async () => written,
    readBundled: () => bundled,
  });
  assert.equal(fromDurable.origin, "durable");
  assert.equal(fromDurable.signals[0]?.id, "p");
  clearMemoryFeed();
});

test("persistLocalFeed still remembers the scan if durable write fails", async () => {
  clearMemoryFeed();
  await persistLocalFeed(
    { lastScanAt: "2026-09-09T12:00:00.000Z", signals: [signal("ok", "News24 OMO SA")] },
    {
      writeRuntime: () => undefined,
      writeDurable: async () => {
        throw new Error("supabase down");
      },
    },
  );
  assert.equal(readMemoryFeed()?.signals[0]?.id, "ok");
  clearMemoryFeed();
});
