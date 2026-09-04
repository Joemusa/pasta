import { createHash } from "crypto";
import { isHomeCareRelevant } from "../home-care-relevance";
import { runPromoScan } from "./promotions";
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

type RssItem = {
  title: string;
  link: string;
  pubDate: string;
  source: string;
  summary: string;
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

function decode(text: string): string {
  const withTags = text
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&");
  return withTags.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

function tag(block: string, name: string): string {
  const cdata = block.match(new RegExp(`<${name}[^>]*>\\s*<!\\[CDATA\\[([\\s\\S]*?)\\]\\]>`, "i"));
  if (cdata) return decode(cdata[1]);
  const plain = block.match(new RegExp(`<${name}[^>]*>([\\s\\S]*?)</${name}>`, "i"));
  return plain ? decode(plain[1]) : "";
}

function parseRss(xml: string, feedName: string): RssItem[] {
  const chunks = xml.split(/<item[\s>]/i).slice(1);
  return chunks
    .map((chunk) => {
      const block = chunk.split(/<\/item>/i)[0] ?? "";
      const title = tag(block, "title");
      const link = tag(block, "link") || tag(block, "guid");
      const publisher =
        tag(block, "source") ||
        (title.includes(" - ") ? title.split(" - ").slice(-1)[0] : "");
      const headline = title.replace(/\s+-\s+[^-]+$/, "").trim() || title;
      return {
        title: headline,
        link,
        pubDate: tag(block, "pubDate") || tag(block, "published"),
        source: prettySource(publisher, feedName),
        summary: cleanExcerpt(tag(block, "description"), headline),
      };
    })
    .filter((item) => item.title && item.link);
}

const FEED_TIMEOUT_MS = 6000;

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
    !!brand &&
    /^(omo|surf|skip|sunlight|domestos|comfort|handy andy|jik)$/i.test(brand);
  if (brand && !own) return "competitor";
  if (retailer) return "retailer";
  return "consumer";
}

function severityFor(type: SignalType, text: string): Severity {
  if (/unilever|omo|maq|shoprite|usave|boxer/i.test(text) && type !== "consumer") return "high";
  if (type === "macro" || type === "retailer") return "medium";
  return "low";
}

function prettySource(publisher: string, feedName: string): string {
  const name = publisher.trim();
  if (name && !/^google news/i.test(name)) return name;
  if (feedName.startsWith("Google News")) return "Google News";
  return feedName;
}

function cleanExcerpt(raw: string, title: string): string {
  let text = decode(raw).replace(/View Full Coverage on Google News/gi, "").trim();
  if (title && text.toLowerCase().startsWith(title.toLowerCase())) {
    text = text.slice(title.length).replace(/^[\s:—–-]+/, "");
  }
  if (text.includes("<") || text.length < 48) return "";
  if (text.length > 400) return `${text.slice(0, 397).replace(/\s+\S*$/, "")}…`;
  return text;
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

export async function runLiveScan(): Promise<LiveScanResult> {
  const fetchedAt = new Date().toISOString();
  const errors: ScanFeedError[] = [];
  const collected: RssItem[] = [];

  const results = await Promise.allSettled(
    FEEDS.map(async (feed) => {
      const xml = await fetchFeed(feed.url);
      const items = parseRss(xml, feed.name).filter((item) =>
        isHomeCareRelevant(item.title, item.summary, item.source, item.link),
      );
      return { feed: feed.name, items };
    }),
  );

  results.forEach((result, index) => {
    if (result.status === "fulfilled") {
      collected.push(...result.value.items);
    } else {
      errors.push({
        feed: FEEDS[index]?.name ?? "unknown",
        error: result.reason instanceof Error ? result.reason.message : String(result.reason),
      });
    }
  });

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

  const promo = await runPromoScan(fetchedAt);
  errors.push(...promo.errors);
  for (const signal of promo.signals) {
    if (signals.some((existing) => existing.id === signal.id)) continue;
    signals.push(signal);
  }

  signals.sort((a, b) => +new Date(b.publishedAt) - +new Date(a.publishedAt));
  return {
    signals: signals.slice(0, 40),
    errors,
    fetchedAt,
    feedsAttempted: FEEDS.length + promo.feedsAttempted,
  };
}
