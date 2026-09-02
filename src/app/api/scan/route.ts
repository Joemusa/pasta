import { NextResponse } from "next/server";
import { ingestLiveSignals, getAllSignals, getScanMeta } from "@/lib/intelligence/service";
import { runLiveScan } from "@/lib/intelligence/scanner";
import { writeLiveSignals } from "@/lib/intelligence/live-store";

export async function POST() {
  try {
    const result = await runLiveScan();
    ingestLiveSignals(result.signals);
    try {
      writeLiveSignals(result.signals);
    } catch {
      // Persist is best-effort.
    }
    const meta = getScanMeta();
    return NextResponse.json({
      lastScanAt: meta.lastScanAt,
      added: result.signals.length,
      signals: getAllSignals(),
      source: result.signals.length > 0 ? "live" : "demo",
      errors: result.errors,
      feedsAttempted: result.feedsAttempted,
    });
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Scan failed",
        source: "demo",
      },
      { status: 500 },
    );
  }
}
