import { getScanMeta, hydrateLiveSignals, ingestLiveSignals } from "./service";
import { readLiveCache, writeLiveCache } from "./live-store";
import { runLiveScan } from "./scanner";
import { signalIsHomeCareRelevant } from "../home-care-relevance";
import type { IntelligenceSignal } from "../types";

export type InitialNews = {
  signals: IntelligenceSignal[];
  lastScanAt: string;
};

function keepHomeCare(signals: IntelligenceSignal[]): IntelligenceSignal[] {
  return signals.filter((s) => !s.demo && signalIsHomeCareRelevant(s));
}

export async function loadInitialNews(): Promise<InitialNews> {
  const cache = readLiveCache();
  const cached = keepHomeCare(cache.signals);
  if (cached.length > 0) {
    hydrateLiveSignals(cached, cache.lastScanAt);
    return {
      signals: cached,
      lastScanAt: cache.lastScanAt || getScanMeta().lastScanAt,
    };
  }

  // Vercel serverless instances have no durable disk. Scanning during SSR
  // would also exceed the page-function budget; the client boots a scan.
  if (process.env.VERCEL) {
    return { signals: [], lastScanAt: "" };
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
