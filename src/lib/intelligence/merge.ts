import type { IntelligenceSignal } from "../types";

export const SIGNAL_CAP = 75;
const MAX_AGE_MS = 90 * 24 * 60 * 60 * 1000;

/** Keep prior live items when a later scan misses a source (Vercel timeouts). */
export function mergeSignals(
  existing: IntelligenceSignal[],
  incoming: IntelligenceSignal[],
  now = Date.now(),
): IntelligenceSignal[] {
  const cutoff = now - MAX_AGE_MS;
  const unique = new Map<string, IntelligenceSignal>();
  for (const signal of existing) {
    if (signal.demo) continue;
    if (+new Date(signal.publishedAt) < cutoff) continue;
    unique.set(signal.id, signal);
  }
  for (const signal of incoming) {
    if (signal.demo) continue;
    unique.set(signal.id, signal);
  }
  return [...unique.values()]
    .sort((a, b) => +new Date(b.publishedAt) - +new Date(a.publishedAt))
    .slice(0, SIGNAL_CAP);
}
