import { NextResponse } from "next/server";
import { ingestLiveSignals, getScanMeta } from "@/lib/intelligence/service";
import { runLiveScan } from "@/lib/intelligence/scanner";
import { writeLiveCache } from "@/lib/intelligence/live-store";

export const maxDuration = 60;

export async function POST() {
  const started = Date.now();
  try {
    const result = await runLiveScan();
    ingestLiveSignals(result.signals);
    const meta = getScanMeta();
    try {
      writeLiveCache({ lastScanAt: meta.lastScanAt, signals: result.signals });
    } catch {
      // Persist is best-effort.
    }
    return NextResponse.json({
      lastScanAt: meta.lastScanAt,
      added: result.signals.length,
      signals: result.signals,
      source: result.signals.length > 0 ? "live" : "empty",
      errors: result.errors,
      feedsAttempted: result.feedsAttempted,
      durationMs: Date.now() - started,
    });
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Scan failed",
        source: "empty",
      },
      { status: 500 },
    );
  }
}
