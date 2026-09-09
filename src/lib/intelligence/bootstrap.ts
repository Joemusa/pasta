import { getScanMeta, hydrateLiveSignals, ingestLiveSignals } from "./service";
import { runLiveScan } from "./scanner";
import { loadSharedFeed, persistSharedFeed } from "./shared-feed";
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
  const cache = await loadSharedFeed();
  const cached = keepHomeCare(cache.signals);
  if (cached.length > 0) {
    hydrateLiveSignals(cached, cache.lastScanAt);
    return {
      signals: cached,
      lastScanAt: cache.lastScanAt || getScanMeta().lastScanAt,
    };
  }

  // Vercel page budget is too short for a full scan; keep the request fast
  // and let cron / Run New Scan fill the shared store.
  if (process.env.VERCEL) {
    return { signals: [], lastScanAt: "" };
  }

  try {
    const result = await runLiveScan();
    const incoming = result.signals.filter((s) => !s.demo);
    if (incoming.length === 0) return { signals: [], lastScanAt: "" };
    ingestLiveSignals(incoming);
    const meta = getScanMeta();
    const stored = await persistSharedFeed({ lastScanAt: meta.lastScanAt, signals: incoming });
    return { signals: stored.signals, lastScanAt: stored.lastScanAt || meta.lastScanAt };
  } catch {
    return { signals: [], lastScanAt: "" };
  }
}
