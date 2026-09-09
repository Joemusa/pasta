import { createHash } from "crypto";
import { isHomeCareRelevant } from "../home-care-relevance";
import { runGdeltScan } from "./gdelt";
import { runHelloPeterScan } from "./hellopeter";
import { SIGNAL_CAP } from "./merge";
import { runPromoScan } from "./promotions";
import { parseRss, type RssItem } from "./rss";
import { runXScan } from "./x-twitter";
import type {
  CategoryName,
  IntelligenceSignal,
  ProvinceId,
  Severity,
  SignalType,
} from "../types";

export type ScanFeedError = { feed: string; error: string };

export type LiveScanResult = {
  signals: IntelligenceSignal[];
  errors: ScanFeedError[];
  fetchedAt: string;
  feedsAttempted: number;
};

const FEEDS: { name: string; url: string }[] = [
  {
    name: "Google News · Unilever Home Care SA",
    url: "https://news.google.com/rss/search?q=Unilever+%22South+Africa%22+(OMO+OR+Sunlight+OR+Domestos+OR+detergent+OR+laundry+OR+%22home+care%22)+when:90d&hl=en-ZA&gl=ZA&ceid=ZA:en",
  },
  {
    name: "Google News · SA Home Care products",
    url: "https://news.google.com/rss/search?q=%22dishwashing+liquid%22+OR+%22washing+powder%22+OR+%22laundry+detergent%22+OR+Domestos+OR+%22Handy+Andy%22+South+Africa+when:90d&hl=en-ZA&gl=ZA&ceid=ZA:en",
  },
  {
    name: "Google News · News24 Home Care",
    url: "https://news.google.com/rss/search?q=site:news24.com+(Sunlight+OR+OMO+OR+Domestos+OR+%22Handy+Andy%22+OR+dishwashing+OR+detergent)+when:90d&hl=en-ZA&gl=ZA&ceid=ZA:en",
  },
  {
    name: "Google News · SA Home Care promotions",
    url: "https://news.google.com/rss/search?q=(OMO+OR+Sunlight+OR+Domestos+OR+MAQ+OR+Comfort)+(specials+OR+catalogue+OR+leaflet+OR+%22on+promotion%22)+(Shoprite+OR+Checkers+OR+SPAR+OR+%22Pick+n+Pay%22+OR+Takealot)+when:90d&hl=en-ZA&gl=ZA&ceid=ZA:en",
  },
  {
    name: "Google News · Bizcommunity",
    url: "https://news.google.com/rss/search?q=site:bizcommunity.com+(Unilever+OR+OMO+OR+Sunlight+OR+Domestos+OR+detergent)+when:90d&hl=en-ZA&gl=ZA&ceid=ZA:en",
  },
  {
    name: "Google News · Fin24 Unilever",
    url: "https://news.google.com/rss/search?q=site:news24.com/fin24+(Unilever+OR+OMO+OR+Sunlight+OR+Domestos)+when:90d&hl=en-ZA&gl=ZA&ceid=ZA:en",
  },
  { name: "Moneyweb", url: "https://www.moneyweb.co.za/feed/" },
  { name: "The Citizen", url: "https://www.citizen.co.za/feed/" },
  { name: "IOL", url: "https://www.iol.co.za/rss" },
];

const BRANDS = [
  "OMO",
  "Surf",
  "Skip",
  "MAQ",
  "Ariel",
  "Sunlight",
  "Domestos",
  "Harpic",
  "Comfort",
  "Sta-soft",
  "Handy Andy",
  "Britelite",
  "Finish",
  "Jik",
];

const RETAILERS = [
  "Shoprite",
  "Checkers",
  "Usave",
  "Pick n Pay",
  "Boxer",
  "SPAR",
  "Game",
  "Clicks",
  "Dis-Chem",
];

const FEED_TIMEOUT_MS = 8000;

async function fetchFeed(url: string): Promise<string> {
  const res = await fetch(url, {
    headers: {
      "User-Agent": "Mozilla/5.0 (compatible; SAHomeCareIntelligence/1.0; +https://cursor.com)",
      Accept: "application/rss+xml, application/xml, text/xml, */*",
    },
    signal: AbortSignal.timeout(FEED_TIMEOUT_MS),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.text();
}

function findBrand(text: string): string | null {
  return BRANDS.find((b) => new RegExp(`\\b${b}\\b`, "i").test(text)) ?? null;
}

function findRetailer(text: string): string | null {
  return RETAILERS.find((r) => new RegExp(`\\b${r}\\b`, "i").test(text)) ?? null;
}

function findProvince(text: string): ProvinceId | null {
  const map: [RegExp, ProvinceId][] = [
    [/\bgauteng\b|\bjohannesburg\b|\bpretoria\b/i, "gauteng"],
    [/\bkwa[- ]?zulu[- ]?natal\b|\bdurban\b|\bkzn\b/i, "kwazulu-natal"],
    [/\bwestern cape\b|\bcape town\b/i, "western-cape"],
    [/\beastern cape\b/i, "eastern-cape"],
    [/\bfree state\b/i, "free-state"],
    [/\blimpopo\b/i, "limpopo"],
    [/\bmpumalanga\b/i, "mpumalanga"],
    [/\bnorth[- ]west\b/i, "north-west"],
    [/\bnorthern cape\b/i, "northern-cape"],
  ];
  for (const [re, id] of map) if (re.test(text)) return id;
  return null;
}

function findCategory(text: string): CategoryName | null {
  if (/detergent|laundry liquid|omo|maq|surf|ariel|skip/i.test(text)) return "Laundry Detergent";
  if (/laundry bar|sunlight bar|britelite/i.test(text)) return "Laundry Bars";
  if (/dish|sunlight liquid|finish/i.test(text)) return "Dishwashing";
  if (/toilet|domestos|harpic|jik/i.test(text)) return "Toilet Cleaners";
  if (/conditioner|comfort|sta-soft/i.test(text)) return "Fabric Conditioners";
  if (/handy andy|surface cleaner|bleach/i.test(text)) return "Hard Surface Cleaners";
  return null;
}

function classifyType(text: string, brand: string | null, retailer: string | null): SignalType {
  if (/promo|promotion|discount|special|leaflet|price cut/i.test(text)) return "promotion";
  if (/fuel|inflation|sassa|load-?shedding|water|interest rate|cpi|electricity/i.test(text)) {
    return "macro";
  }
  const own =
    !!brand && /^(omo|surf|skip|sunlight|domestos|comfort|handy andy|jik)$/i.test(brand);
  if (brand && !own) return "competitor";
  if (retailer) return "retailer";
  return "consumer";
}

function severityFor(type: SignalType, text: string): Severity {
  if (/unilever|omo|maq|shoprite|usave|boxer/i.test(text) && type !== "consumer") return "high";
  if (type === "macro" || type === "retailer") return "medium";
  return "low";
}

function toSignal(item: RssItem): IntelligenceSignal {
  const blob = `${item.title} ${item.summary}`;
  const brand = findBrand(blob);
  const retailer = findRetailer(blob);
  const category = findCategory(blob);
  const province = findProvince(blob);
  const signalType = classifyType(blob, brand, retailer);
  const published = item.pubDate ? new Date(item.pubDate) : new Date();
  const publishedAt = Number.isNaN(+published) ? new Date().toISOString() : published.toISOString();
  const id = `live-${createHash("sha1").update(item.link || item.title).digest("hex").slice(0, 16)}`;

  const fact = `${item.source} reported: "${item.title}".`;

  return {
    id,
    title: item.title,
    source: item.source,
    sourceUrl: item.link,
    publishedAt,
    detectedAt: new Date().toISOString(),
    signalType,
    category,
    brand,
    retailer,
    province,
    summary: item.summary,
    fact,
    interpretation: "",
    recommendation: "",
    whyItMatters: "",
    suggestedInternalQuery: "",
    severity: severityFor(signalType, blob),
    confidence: item.link.startsWith("http") ? "medium" : "low",
    commercialImpact: "unvalidated",
    demo: false,
  };
}

async function collectRssItems(): Promise<{ items: RssItem[]; errors: ScanFeedError[] }> {
  const errors: ScanFeedError[] = [];
  const items: RssItem[] = [];
  const results = await Promise.allSettled(
    FEEDS.map(async (feed) => {
      const xml = await fetchFeed(feed.url);
      const parsed = parseRss(xml, feed.name).filter((item) =>
        isHomeCareRelevant(item.title, item.summary, item.source, item.link),
      );
      return { feed: feed.name, items: parsed };
    }),
  );

  results.forEach((result, index) => {
    if (result.status === "fulfilled") {
      items.push(...result.value.items);
    } else {
      errors.push({
        feed: FEEDS[index]?.name ?? "unknown",
        error: result.reason instanceof Error ? result.reason.message : String(result.reason),
      });
    }
  });
  return { items, errors };
}

function dedupeItems(collected: RssItem[]): IntelligenceSignal[] {
  const seen = new Set<string>();
  const signals: IntelligenceSignal[] = [];
  for (const item of collected) {
    const key = item.link || item.title.toLowerCase().replace(/\s+/g, " ");
    const titleKey = item.title.toLowerCase().replace(/\s+/g, " ").slice(0, 80);
    if (seen.has(key) || seen.has(titleKey)) continue;
    seen.add(key);
    seen.add(titleKey);
    if (!isHomeCareRelevant(item.title, item.summary, item.source, item.link)) continue;
    signals.push(toSignal(item));
  }
  return signals;
}

function isolateAgent(
  promise: Promise<{ signals: IntelligenceSignal[]; errors: ScanFeedError[]; feedsAttempted: number }>,
  feed: string,
): Promise<{ signals: IntelligenceSignal[]; errors: ScanFeedError[]; feedsAttempted: number }> {
  return promise.catch((error) => ({
    signals: [],
    errors: [
      {
        feed,
        error: error instanceof Error ? error.message : String(error),
      },
    ],
    feedsAttempted: 0,
  }));
}

export async function runLiveScan(): Promise<LiveScanResult> {
  const fetchedAt = new Date().toISOString();
  const errors: ScanFeedError[] = [];

  const [rss, gdelt] = await Promise.all([collectRssItems(), runGdeltScan()]);
  errors.push(...rss.errors, ...gdelt.errors);
  const signals = dedupeItems([...rss.items, ...gdelt.items]);

  const [promo, complaints, twitter] = await Promise.all([
    isolateAgent(runPromoScan(fetchedAt), "Takealot"),
    isolateAgent(runHelloPeterScan(fetchedAt), "HelloPeter"),
    isolateAgent(runXScan(fetchedAt), "X"),
  ]);
  errors.push(...promo.errors, ...complaints.errors, ...twitter.errors);
  for (const signal of [...promo.signals, ...complaints.signals, ...twitter.signals]) {
    if (signals.some((existing) => existing.id === signal.id)) continue;
    signals.push(signal);
  }

  signals.sort((a, b) => +new Date(b.publishedAt) - +new Date(a.publishedAt));
  return {
    signals: signals.slice(0, SIGNAL_CAP),
    errors,
    fetchedAt,
    feedsAttempted:
      FEEDS.length +
      gdelt.feedsAttempted +
      promo.feedsAttempted +
      complaints.feedsAttempted +
      twitter.feedsAttempted,
  };
}
