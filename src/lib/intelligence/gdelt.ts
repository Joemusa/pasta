import { isHomeCareRelevant } from "../home-care-relevance";
import { articleToItem, type GdeltArticle } from "./gdelt-map";
import type { RssItem } from "./rss";

type ScanFeedError = { feed: string; error: string };

const QUERIES: { name: string; query: string }[] = [
  {
    name: "GDELT · Unilever Home Care SA",
    query:
      '(Unilever OR OMO OR Sunlight OR Domestos OR "Handy Andy" OR Comfort OR MAQ) sourceloc:southafrica',
  },
  {
    name: "GDELT · SA laundry and cleaning",
    query:
      '("washing powder" OR "dishwashing liquid" OR "fabric softener" OR detergent OR "toilet cleaner") sourceloc:southafrica',
  },
];

const FETCH_MS = 15000;

function gdeltUrl(query: string): string {
  const params = new URLSearchParams({
    query,
    mode: "ArtList",
    maxrecords: "50",
    format: "json",
    sort: "DateDesc",
    timespan: "90d",
  });
  return `https://api.gdeltproject.org/api/v2/doc/doc?${params.toString()}`;
}

async function fetchArticles(query: string): Promise<GdeltArticle[]> {
  const res = await fetch(gdeltUrl(query), {
    headers: {
      "User-Agent": "Mozilla/5.0 (compatible; SAHomeCareIntelligence/1.0)",
      Accept: "application/json, text/plain, */*",
    },
    signal: AbortSignal.timeout(FETCH_MS),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const text = await res.text();
  if (!text.trim() || text.trim().startsWith("<")) return [];
  const json = JSON.parse(text) as { articles?: GdeltArticle[] };
  return json.articles ?? [];
}

export { articleToItem };

export async function runGdeltScan(): Promise<{
  items: RssItem[];
  errors: ScanFeedError[];
  feedsAttempted: number;
}> {
  const errors: ScanFeedError[] = [];
  const items: RssItem[] = [];
  const results = await Promise.allSettled(QUERIES.map((feed) => fetchArticles(feed.query)));
  results.forEach((result, index) => {
    const feed = QUERIES[index]?.name ?? "GDELT";
    if (result.status === "rejected") {
      errors.push({
        feed,
        error: result.reason instanceof Error ? result.reason.message : String(result.reason),
      });
      return;
    }
    for (const article of result.value) {
      const item = articleToItem(article);
      if (!item) continue;
      if (!isHomeCareRelevant(item.title, item.summary, item.source, item.link)) continue;
      items.push(item);
    }
  });
  return { items, errors, feedsAttempted: QUERIES.length };
}
