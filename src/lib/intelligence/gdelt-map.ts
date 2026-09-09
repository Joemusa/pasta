import type { RssItem } from "./rss";

export type GdeltArticle = {
  url?: string;
  title?: string;
  seendate?: string;
  domain?: string;
  sourcecountry?: string;
};

export function gdeltSeenToIso(seendate: string): string {
  const match = seendate.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/);
  if (!match) {
    const fallback = new Date(seendate);
    return Number.isNaN(+fallback) ? new Date().toISOString() : fallback.toISOString();
  }
  const [, y, mo, d, h, mi, s] = match;
  return `${y}-${mo}-${d}T${h}:${mi}:${s}.000Z`;
}

export function articleToItem(article: GdeltArticle): RssItem | null {
  const title = (article.title ?? "").trim();
  const link = (article.url ?? "").trim();
  if (!title || !link) return null;
  const domain = (article.domain ?? "").replace(/^www\./, "");
  const country = article.sourcecountry ?? "";
  const saHint = /south africa/i.test(country) ? "South Africa. " : "";
  return {
    title,
    link,
    pubDate: article.seendate ? gdeltSeenToIso(article.seendate) : new Date().toISOString(),
    source: domain || "GDELT",
    summary: `${saHint}Live GDELT article from ${domain || "a South African source"}.`,
  };
}
