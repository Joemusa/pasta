import assert from "node:assert/strict";
import { test } from "node:test";
import { runXScan } from "./x-twitter.ts";

test("runXScan without a bearer token does not throw and leaves other agents free", async () => {
  delete process.env.X_BEARER_TOKEN;
  delete process.env.TWITTER_BEARER_TOKEN;
  process.env.X_AGENT_ENABLED = "true";
  const result = await runXScan("2026-09-09T09:00:00.000Z");
  assert.equal(result.signals.length, 0);
  assert.ok(result.errors.some((row) => /X_BEARER_TOKEN/.test(row.error)));
});

test("disabled X agent returns empty without errors", async () => {
  process.env.X_AGENT_ENABLED = "false";
  const result = await runXScan("2026-09-09T09:00:00.000Z");
  assert.deepEqual(result.errors, []);
  assert.equal(result.signals.length, 0);
  delete process.env.X_AGENT_ENABLED;
});
