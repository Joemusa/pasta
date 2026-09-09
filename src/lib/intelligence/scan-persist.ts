import { ingestLiveSignals, getScanMeta, hydrateLiveSignals } from "./service";
import { runLiveScan, type LiveScanResult } from "./scanner";
import { mergeSignals } from "./merge";
import { loadSharedFeed, persistSharedFeed } from "./shared-feed";
import type { IntelligenceSignal } from "../types";

export type PersistedScan = {
  lastScanAt: string;
  added: number;
  signals: IntelligenceSignal[];
  source: "live" | "cache";
  errors: LiveScanResult["errors"];
  feedsAttempted: number;
  durationMs: number;
};

export async function runAndPersistScan(): Promise<PersistedScan> {
  const started = Date.now();
  const previous = await loadSharedFeed();
  const result = await runLiveScan();
  const incoming = result.signals.filter((s) => !s.demo);

  if (incoming.length === 0 && previous.signals.length > 0) {
    hydrateLiveSignals(previous.signals, previous.lastScanAt);
    const stored = await persistSharedFeed({
      lastScanAt: previous.lastScanAt || getScanMeta().lastScanAt,
      signals: previous.signals,
    });
    return {
      lastScanAt: stored.lastScanAt || getScanMeta().lastScanAt,
      added: 0,
      signals: stored.signals,
      source: "cache",
      errors: result.errors,
      feedsAttempted: result.feedsAttempted,
      durationMs: Date.now() - started,
    };
  }

  const merged = mergeSignals(previous.signals, incoming);
  ingestLiveSignals(merged);
  const meta = getScanMeta();
  const stored = await persistSharedFeed({ lastScanAt: meta.lastScanAt, signals: merged });
  return {
    lastScanAt: stored.lastScanAt || meta.lastScanAt,
    added: incoming.length,
    signals: stored.signals,
    source: incoming.length > 0 ? "live" : "cache",
    errors: result.errors,
    feedsAttempted: result.feedsAttempted,
    durationMs: Date.now() - started,
  };
}
