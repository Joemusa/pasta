import { ingestLiveSignals, getScanMeta, hydrateLiveSignals } from "./service";
import { readLiveCache, writeLiveCache } from "./live-store";
import { runLiveScan, type LiveScanResult } from "./scanner";
import { mergeSignals } from "./merge";
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
  const previous = readLiveCache();
  const result = await runLiveScan();
  const incoming = result.signals.filter((s) => !s.demo);

  if (incoming.length === 0 && previous.signals.length > 0) {
    hydrateLiveSignals(previous.signals, previous.lastScanAt);
    return {
      lastScanAt: previous.lastScanAt || getScanMeta().lastScanAt,
      added: 0,
      signals: previous.signals,
      source: "cache",
      errors: result.errors,
      feedsAttempted: result.feedsAttempted,
      durationMs: Date.now() - started,
    };
  }

  const merged = mergeSignals(previous.signals, incoming);
  ingestLiveSignals(merged);
  const meta = getScanMeta();
  try {
    writeLiveCache({ lastScanAt: meta.lastScanAt, signals: merged });
  } catch {
    // Persist is best-effort on read-only hosts.
  }
  return {
    lastScanAt: meta.lastScanAt,
    added: incoming.length,
    signals: merged,
    source: incoming.length > 0 ? "live" : "cache",
    errors: result.errors,
    feedsAttempted: result.feedsAttempted,
    durationMs: Date.now() - started,
  };
}
