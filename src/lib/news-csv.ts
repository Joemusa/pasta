import type { IntelligenceSignal } from "./types";
import { analyseStory } from "./product-impact";

export const NEWS_CSV_HEADERS = ["what_it_means"] as const;

function csvCell(value: string): string {
  const text = value.replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
  if (/[",\n]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

export function newsSignalsToCsv(signals: IntelligenceSignal[]): string {
  const rows = signals.map((signal) => csvCell(analyseStory(signal).meaning));
  return `\uFEFF${[NEWS_CSV_HEADERS.join(","), ...rows].join("\n")}\n`;
}

export function newsCsvFilename(now = new Date()): string {
  return `unilever-sa-homecare-news-${now.toISOString().slice(0, 10)}.csv`;
}
