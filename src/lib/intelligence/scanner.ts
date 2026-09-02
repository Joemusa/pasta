import { createHash } from "crypto";
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

const FEEDS: { name: string; url: string; requireKeywords: boolean }[] = [
  {
    name: "Google News · Home Care & grocery",
    url: "https://news.google.com/rss/search?q=Unilever%20OR%20OMO%20OR%20MAQ%20OR%20Surf%20OR%20Domestos%20OR%20detergent%20OR%20%22home%20care%22%20South%20Africa%20when%3A30d&hl=en-ZA&gl=ZA&ceid=ZA:en",
    requireKeywords: true,
  },
  {
    name: "Google News · Retailers",
    url: "https://news.google.com/rss/search?q=Shoprite%20OR%20Checkers%20OR%20Boxer%20OR%20%22Pick%20n%20Pay%22%20OR%20SPAR%20OR%20Usave%20South%20Africa%20when%3A30d&hl=en-ZA&gl=ZA&ceid=ZA:en",
    requireKeywords: true,
  },
  {
    name: "Google News · Macro",
    url: "https://news.google.com/rss/search?q=SASSA%20OR%20%22fuel%20price%22%20OR%20inflation%20OR%20%22load%20shedding%22%20OR%20%22water%20supply%22%20South%20Africa%20when%3A30d&hl=en-ZA&gl=ZA&ceid=ZA:en",
    requireKeywords: true,
  },
  { name: "Moneyweb", url: "https://www.moneyweb.co.za/feed/", requireKeywords: true },
  { name: "The Citizen", url: "https://www.citizen.co.za/feed/", requireKeywords: true },
  { name: "IOL", url: "https://www.iol.co.za/rss", requireKeywords: true },
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

const RELEVANCE =
  /\b(unilever|omo|surf|maq|skip|ariel|sunlight|domestos|harpic|comfort|handy andy|sta-soft|britelite|shoprite|checkers|usave|pick n pay|boxer|spar|clicks|dis-chem|detergent|laundry|homecare|home care|fmcg|inflation|fuel price|petrol|diesel|sassa|social grant|load-?shedding|water (interruption|outage|shortage|crisis)|food price|cpi)\b/i;

const DENY =
  /\b(gepf|pension fund|sardines?|vida e caff|coffee shop|rugby|cricket|soccer|murder|homicide|celebrity)\b/i;

function decode(text: string): string {
  return text
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
    .replace(/<[^>]+>/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
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
      const source =
        tag(block, "source") ||
        (title.includes(" - ") ? title.split(" - ").slice(-1)[0] : feedName);
      return {
        title: title.replace(/\s+-\s+[^-]+$/, "").trim() || title,
        link,
        pubDate: tag(block, "pubDate") || tag(block, "published"),
        source,
        summary: tag(block, "description") || title,
      };
    })
    .filter((item) => item.title && item.link);
}

async function fetchFeed(url: string): Promise<string> {
  const res = await fetch(url, {
    headers: {
      "User-Agent": "Mozilla/5.0 (compatible; SAHomeCareIntelligence/1.0; +https://cursor.com)",
      Accept: "application/rss+xml, application/xml, text/xml, */*",
    },
    signal: AbortSignal.timeout(12000),
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
  if (brand && !/unilever|omo|surf|skip|sunlight|domestos|comfort|handy andy/i.test(brand)) {
    return "competitor";
  }
  if (retailer) return "retailer";
  if (brand) return "competitor";
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
  const interpretation = brand
    ? `This may be relevant to Unilever Home Care if it changes competitive pressure, distribution or demand around ${brand}. This is an interpretation, not a source claim.`
    : retailer
      ? `This may affect Home Care ranging, price architecture or trip mix in ${retailer}. This is an interpretation, not a source claim.`
      : `This is an external South African consumer/macro signal that can move Home Care pack size, banner or brand choice. This is an interpretation, not a source claim.`;
  const recommendation =
    "Confirm with internal POS whether Unilever Home Care volume or share moved in the named banners and provinces. Do not treat this headline as a financial impact figure.";

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
    summary: item.summary.slice(0, 400),
    fact,
    interpretation,
    recommendation,
    whyItMatters: interpretation,
    suggestedInternalQuery:
      "Latest 12-week Unilever Home Care scorecard by retailer and province, overlaying the date of this article.",
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
      const items = parseRss(xml, feed.name).filter((item) => {
        const blob = `${item.title} ${item.summary}`;
        if (DENY.test(blob)) return false;
        return feed.requireKeywords ? RELEVANCE.test(blob) : true;
      });
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
    if (DENY.test(`${item.title} ${item.summary}`)) continue;
    if (!RELEVANCE.test(`${item.title} ${item.summary}`)) continue;
    signals.push(toSignal(item));
  }

  signals.sort((a, b) => {
    const score = (s: IntelligenceSignal) =>
      (s.brand ? 3 : 0) + (s.retailer ? 2 : 0) + (s.signalType === "macro" ? 2 : 0);
    const byScore = score(b) - score(a);
    if (byScore !== 0) return byScore;
    return +new Date(b.publishedAt) - +new Date(a.publishedAt);
  });
  return {
    signals: signals.slice(0, 40),
    errors,
    fetchedAt,
    feedsAttempted: FEEDS.length,
  };
}
