import type { IntelligenceSignal } from "./types";
import { analyseStory } from "./product-impact";

export const NEWS_CSV_HEADERS = [
  "story_id",
  "published_date",
  "source",
  "headline",
  "category",
  "brand",
  "product",
  "retailer",
  "province",
  "what_it_means",
  "pos_check",
  "source_url",
] as const;

function csvCell(value: string): string {
  const text = value.replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
  if (/[",\n]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

function publishedDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(+date)) return "";
  return date.toISOString().slice(0, 10);
}

function posCheck(category: string, brand: string, product: string, retailer: string | null): string {
  const where = retailer
    ? `in ${retailer}`
    : "by retailer (Shoprite, Usave, Boxer, Pick n Pay, SPAR)";
  return `POS check for ${product} (${brand}) in ${category} ${where}: last 12 weeks value share, volume, ASP and % sales on promo versus the prior 12 weeks.`;
}

export function newsSignalsToCsv(signals: IntelligenceSignal[]): string {
  const rows = signals.map((signal) => {
    const analysis = analyseStory(signal);
    return [
      signal.id,
      publishedDate(signal.publishedAt),
      signal.source,
      signal.title,
      analysis.category,
      analysis.brand,
      analysis.product,
      signal.retailer ?? "",
      signal.province ?? "",
      analysis.meaning,
      posCheck(analysis.category, analysis.brand, analysis.product, signal.retailer),
      signal.sourceUrl ?? "",
    ].map((cell) => csvCell(String(cell)));
  });
  return `\uFEFF${[NEWS_CSV_HEADERS.join(","), ...rows.map((row) => row.join(","))].join("\n")}\n`;
}

export function newsCsvFilename(now = new Date()): string {
  return `unilever-sa-homecare-news-${now.toISOString().slice(0, 10)}.csv`;
}
