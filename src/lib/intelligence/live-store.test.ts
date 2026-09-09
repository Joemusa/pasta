import assert from "node:assert/strict";
import { test } from "node:test";
import { readBundledCache } from "./live-store.ts";

test("bundled snapshot ships real SA Home Care stories", () => {
  const cache = readBundledCache();
  assert.ok(cache.signals.length >= 10, `expected bundled stories, got ${cache.signals.length}`);
  assert.equal(cache.signals.some((s) => s.demo), false);
  const sources = new Set(cache.signals.map((s) => s.source));
  assert.ok(sources.has("takealot.com"));
  assert.ok(sources.has("hellopeter.com"));
  assert.ok(sources.has("news24.com"));
  assert.ok(
    cache.signals.some((s) => /omo|sunlight|domestos|maq|finish|handy andy/i.test(`${s.title} ${s.brand}`)),
    "bundled feed should name Home Care brands",
  );
});
