import { createHash } from "crypto";
import { isHomeCareRelevant } from "../home-care-relevance";
import type { IntelligenceSignal } from "../types";

type ScanFeedError = { feed: string; error: string };

const BUSINESSES = [
  { slug: "unilever", name: "Unilever SA" },
  { slug: "maq", name: "MAQ" },
];

const MAX_PAGES = 4;
const MAX_AGE_DAYS = 90;
const MAX_COMPLAINTS = 12;

type HelloPeterReview = {
  id: number;
  created_at: string;
  review_title: string;
  review_rating: number;
  review_content: string;
  business_name: string;
  business_slug: string;
  permalink: string;
  author?: string;
  authorDisplayName?: string;
};

const NOT_HOME_CARE =
  /\b(tresemme|trésemmé|dove\b|keratin|hair loss|aromat|knorr|lipton|hellmann|magnum|ice cream|lifebuoy|lux soap|rexona|vaseline|bath soap|personal care|for the skin)\b/i;

function stripHtml(value: string): string {
  return value
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();
}

function publishedAt(raw: string): Date {
  const withZone = raw.includes("T") ? raw : raw.replace(" ", "T") + "+02:00";
  const date = new Date(withZone);
  return Number.isNaN(+date) ? new Date() : date;
}

function isFresh(date: Date, now: Date): boolean {
  return now.getTime() - date.getTime() <= MAX_AGE_DAYS * 24 * 60 * 60 * 1000;
}

function isComplaint(review: HelloPeterReview): boolean {
  return Number(review.review_rating) <= 3;
}

function isRelevant(review: HelloPeterReview): boolean {
  const title = review.review_title ?? "";
  const body = stripHtml(review.review_content ?? "");
  const blob = `${title} ${body}`;
  if (NOT_HOME_CARE.test(blob)) return false;
  const url = `https://www.hellopeter.com/${review.business_slug}/${review.permalink}`;
  if (isHomeCareRelevant(title, `${body} Unilever South Africa`, "HelloPeter", url)) return true;
  // Unilever SA complaints often name Comfort / OMO without extra category words.
  return (
    review.business_slug === "unilever" &&
    /\b(comfort|omo|surf|skip|sunlight|domestos|handy andy|jik)\b/i.test(blob)
  );
}

async function fetchPage(slug: string, page: number): Promise<HelloPeterReview[]> {
  const url = `https://api.hellopeter.com/consumer/business/${slug}/reviews?page=${page}`;
  const res = await fetch(url, {
    headers: {
      "User-Agent": "Mozilla/5.0 (compatible; SAHomeCareIntelligence/1.0)",
      Accept: "application/json",
    },
    signal: AbortSignal.timeout(8000),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const json = (await res.json()) as { data?: HelloPeterReview[] };
  return json.data ?? [];
}

function toSignal(review: HelloPeterReview): IntelligenceSignal {
  const when = publishedAt(review.created_at).toISOString();
  const title = review.review_title.trim() || "HelloPeter Home Care complaint";
  const body = stripHtml(review.review_content ?? "");
  const excerpt = body.length > 280 ? `${body.slice(0, 277).replace(/\s+\S*$/, "")}…` : body;
  const url = `https://www.hellopeter.com/${review.business_slug}/${review.permalink}`;
  const rating = Number(review.review_rating) || 1;
  return {
    id: `live-hp-${createHash("sha1").update(String(review.id)).digest("hex").slice(0, 16)}`,
    title: `HelloPeter: ${title}`,
    source: "hellopeter.com",
    sourceUrl: url,
    publishedAt: when,
    detectedAt: when,
    signalType: "consumer",
    category: null,
    brand: null,
    retailer: null,
    province: null,
    summary: excerpt,
    fact: `${review.authorDisplayName || review.author || "A shopper"} rated this ${rating}/5 on HelloPeter: "${title}".`,
    interpretation: "",
    recommendation: "",
    whyItMatters: "",
    suggestedInternalQuery: "",
    severity: rating <= 1 ? "high" : "medium",
    confidence: "high",
    commercialImpact: "unvalidated",
    demo: false,
  };
}

export async function runHelloPeterScan(fetchedAt: string): Promise<{
  signals: IntelligenceSignal[];
  errors: ScanFeedError[];
  feedsAttempted: number;
}> {
  const errors: ScanFeedError[] = [];
  const collected: HelloPeterReview[] = [];
  const now = new Date(fetchedAt);

  for (const company of BUSINESSES) {
    for (let page = 1; page <= MAX_PAGES; page += 1) {
      try {
        const rows = await fetchPage(company.slug, page);
        if (rows.length === 0) break;
        let reachedOld = false;
        for (const row of rows) {
          const when = publishedAt(row.created_at);
          if (!isFresh(when, now)) {
            reachedOld = true;
            continue;
          }
          collected.push(row);
        }
        if (reachedOld) break;
      } catch (error) {
        errors.push({
          feed: `HelloPeter · ${company.name}`,
          error: error instanceof Error ? error.message : String(error),
        });
        break;
      }
    }
  }

  const seen = new Set<number>();
  const signals = collected
    .filter((review) => {
      if (seen.has(review.id)) return false;
      seen.add(review.id);
      return isComplaint(review) && isRelevant(review);
    })
    .sort((a, b) => +publishedAt(b.created_at) - +publishedAt(a.created_at))
    .slice(0, MAX_COMPLAINTS)
    .map(toSignal);

  return { signals, errors, feedsAttempted: BUSINESSES.length };
}
