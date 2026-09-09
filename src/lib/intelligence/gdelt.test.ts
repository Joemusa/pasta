import assert from "node:assert/strict";
import { test } from "node:test";
import { articleToItem } from "./gdelt-map.ts";

test("articleToItem maps GDELT ArtList rows and marks South Africa", () => {
  const item = articleToItem({
    url: "https://www.news24.com/fin24/omo-price",
    title: "OMO washing powder price watch",
    seendate: "20260908T101500Z",
    domain: "news24.com",
    sourcecountry: "South Africa",
  });
  assert.ok(item);
  assert.equal(item.source, "news24.com");
  assert.equal(item.pubDate, "2026-09-08T10:15:00.000Z");
  assert.match(item.summary, /South Africa/);
});

test("articleToItem skips empty GDELT rows", () => {
  assert.equal(articleToItem({ title: "", url: "https://example.com" }), null);
});
