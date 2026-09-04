import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import path from "path";
import type { IntelligenceSignal } from "../types";

const LIVE_PATH = process.env.VERCEL
  ? path.join("/tmp", "live-signals.json")
  : path.join(process.cwd(), "data", "live-signals.json");

export type LiveCache = {
  lastScanAt: string;
  signals: IntelligenceSignal[];
};

function liveOnly(signals: IntelligenceSignal[]): IntelligenceSignal[] {
  return signals.filter((s) => !s.demo);
}

export function readLiveCache(): LiveCache {
  try {
    if (!existsSync(LIVE_PATH)) return { lastScanAt: "", signals: [] };
    const parsed = JSON.parse(readFileSync(LIVE_PATH, "utf8")) as LiveCache | IntelligenceSignal[];
    if (Array.isArray(parsed)) {
      const signals = liveOnly(parsed);
      return { lastScanAt: signals[0]?.detectedAt ?? "", signals };
    }
    return {
      lastScanAt: parsed.lastScanAt ?? "",
      signals: liveOnly(parsed.signals ?? []),
    };
  } catch {
    return { lastScanAt: "", signals: [] };
  }
}

export function writeLiveCache(cache: LiveCache) {
  mkdirSync(path.dirname(LIVE_PATH), { recursive: true });
  writeFileSync(
    LIVE_PATH,
    JSON.stringify({ lastScanAt: cache.lastScanAt, signals: liveOnly(cache.signals) }, null, 2),
  );
}

export function readLiveSignals(): IntelligenceSignal[] {
  return readLiveCache().signals;
}

export function writeLiveSignals(signals: IntelligenceSignal[]) {
  writeLiveCache({ lastScanAt: new Date().toISOString(), signals });
}
