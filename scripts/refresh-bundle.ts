import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { runLiveScan } from "../src/lib/intelligence/scanner.ts";

async function main() {
  const out = path.join(process.cwd(), "src", "data", "bundled-signals.json");
  const result = await runLiveScan();
  mkdirSync(path.dirname(out), { recursive: true });
  writeFileSync(
    out,
    `${JSON.stringify(
      {
        lastScanAt: result.fetchedAt,
        signals: result.signals,
        errors: result.errors,
        feedsAttempted: result.feedsAttempted,
      },
      null,
      2,
    )}\n`,
  );

  console.log(
    JSON.stringify(
      {
        wrote: out,
        articles: result.signals.length,
        feedsAttempted: result.feedsAttempted,
        errors: result.errors,
      },
      null,
      2,
    ),
  );

  if (result.signals.length === 0) {
    console.error("Live scan returned no Home Care articles; bundle not useful.");
    process.exit(1);
  }
}

void main();
