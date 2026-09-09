import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import path from "path";
import { mergeSignals } from "./merge";
import type { IntelligenceSignal } from "../types";
import bundledSnapshot from "../../data/bundled-signals.json";

const RUNTIME_PATH = process.env.VERCEL
  ? path.join("/tmp", "live-signals.json")
  : path.join(process.cwd(), "data", "live-signals.json");

export type LiveCache = {
  lastScanAt: string;
  signals: IntelligenceSignal[];
};

function liveOnly(signals: IntelligenceSignal[]): IntelligenceSignal[] {
  return signals.filter((s) => s && !s.demo);
}

function asCache(parsed: LiveCache | IntelligenceSignal[] | null | undefined): LiveCache {
  if (!parsed) return { lastScanAt: "", signals: [] };
  if (Array.isArray(parsed)) {
    const signals = liveOnly(parsed);
    return { lastScanAt: signals[0]?.detectedAt ?? "", signals };
  }
  return {
    lastScanAt: parsed.lastScanAt ?? "",
    signals: liveOnly(parsed.signals ?? []),
  };
}

function readPath(filePath: string): LiveCache {
  try {
    if (!existsSync(filePath)) return { lastScanAt: "", signals: [] };
    return asCache(JSON.parse(readFileSync(filePath, "utf8")) as LiveCache | IntelligenceSignal[]);
  } catch {
    return { lastScanAt: "", signals: [] };
  }
}

/** Last-good SA Home Care snapshot compiled into the serverless bundle. */
export function readBundledCache(): LiveCache {
  return asCache(bundledSnapshot as LiveCache);
}

export function readRuntimeCache(): LiveCache {
  return readPath(RUNTIME_PATH);
}

/** Runtime cache on top of the snapshot shipped with the deploy. */
export function readLiveCache(): LiveCache {
  const bundled = readBundledCache();
  const runtime = readRuntimeCache();
  if (runtime.signals.length === 0) return bundled;
  if (bundled.signals.length === 0) return runtime;
  const newer =
    runtime.lastScanAt && bundled.lastScanAt && runtime.lastScanAt >= bundled.lastScanAt
      ? runtime.lastScanAt
      : runtime.lastScanAt || bundled.lastScanAt;
  return {
    lastScanAt: newer,
    signals: mergeSignals(bundled.signals, runtime.signals),
  };
}

export function writeLiveCache(cache: LiveCache) {
  mkdirSync(path.dirname(RUNTIME_PATH), { recursive: true });
  writeFileSync(
    RUNTIME_PATH,
    JSON.stringify({ lastScanAt: cache.lastScanAt, signals: liveOnly(cache.signals) }, null, 2),
  );
}

export function readLiveSignals(): IntelligenceSignal[] {
  return readLiveCache().signals;
}

export function writeLiveSignals(signals: IntelligenceSignal[]) {
  writeLiveCache({ lastScanAt: new Date().toISOString(), signals });
}
