import { getScanMeta, hydrateLiveSignals, ingestLiveSignals } from "./service";
import { readLiveCache, writeLiveCache } from "./live-store";
import { runLiveScan } from "./scanner";
import type { IntelligenceSignal } from "../types";

export type InitialNews = {
  signals: IntelligenceSignal[];
  lastScanAt: string;
};

export async function loadInitialNews(): Promise<InitialNews> {
  const cache = readLiveCache();
  if (cache.signals.length > 0) {
    hydrateLiveSignals(cache.signals, cache.lastScanAt);
    return {
      signals: cache.signals,
      lastScanAt: cache.lastScanAt || getScanMeta().lastScanAt,
    };
  }

  try {
    const result = await runLiveScan();
    ingestLiveSignals(result.signals);
    const meta = getScanMeta();
    try {
      writeLiveCache({ lastScanAt: meta.lastScanAt, signals: result.signals });
    } catch {
      // Persist is best-effort.
    }
    return { signals: result.signals, lastScanAt: meta.lastScanAt };
  } catch {
    return { signals: [], lastScanAt: "" };
  }
}
