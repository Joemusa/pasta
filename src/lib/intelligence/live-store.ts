import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import path from "path";
import type { IntelligenceSignal } from "../types";

const LIVE_PATH = path.join(process.cwd(), "data", "live-signals.json");

export function readLiveSignals(): IntelligenceSignal[] {
  try {
    if (!existsSync(LIVE_PATH)) return [];
    const parsed = JSON.parse(readFileSync(LIVE_PATH, "utf8")) as IntelligenceSignal[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function writeLiveSignals(signals: IntelligenceSignal[]) {
  mkdirSync(path.dirname(LIVE_PATH), { recursive: true });
  writeFileSync(LIVE_PATH, JSON.stringify(signals, null, 2));
}
