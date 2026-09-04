import { createHash } from "crypto";
import type { CategoryName, IntelligenceSignal } from "../types";

type ScanFeedError = { feed: string; error: string };

const TAKEALOT_SEARCH =
  "https://api.takealot.com/rest/v-1-11-0/searches/products,filters,facets,sort_options";

const QUERIES = [
  "OMO detergent",
  "Sunlight dishwashing",
  "Sunlight laundry",
  "Domestos",
  "Handy Andy",
  "Comfort fabric softener",
  "Skip detergent",
  "Surf washing powder",
  "MAQ washing powder",
  "Harpic toilet",
  "Sta-soft",
  "Finish dishwasher",
];

const BRANDS: { name: string; re: RegExp; category: CategoryName; competitor?: boolean }[] = [
  { name: "OMO", re: /\bomo\b/i, category: "Laundry Detergent" },
  { name: "Surf", re: /\bsurf\b/i, category: "Laundry Detergent" },
  { name: "Skip", re: /\bskip\b/i, category: "Laundry Detergent" },
  { name: "Sunlight", re: /\bsunlight\b/i, category: "Dishwashing" },
  { name: "Domestos", re: /\bdomestos\b/i, category: "Toilet Cleaners" },
  { name: "Comfort", re: /\bcomfort\b/i, category: "Fabric Conditioners" },
  { name: "Handy Andy", re: /\bhandy andy\b/i, category: "Hard Surface Cleaners" },
  { name: "Jik", re: /\bjik\b/i, category: "Toilet Cleaners" },
  { name: "MAQ", re: /\bmaq\b/i, category: "Laundry Detergent", competitor: true },
  { name: "Ariel", re: /\bariel\b/i, category: "Laundry Detergent", competitor: true },
  { name: "Harpic", re: /\bharpic\b/i, category: "Toilet Cleaners", competitor: true },
  { name: "Sta-soft", re: /\bsta-?soft\b/i, category: "Fabric Conditioners", competitor: true },
  { name: "Britelite", re: /\bbritelite\b/i, category: "Laundry Bars", competitor: true },
  { name: "Finish", re: /\bfinish\b/i, category: "Dishwashing", competitor: true },
];

type PromoHit = {
  title: string;
  brand: string;
  category: CategoryName;
  competitor: boolean;
  price: string;
  saving: string | null;
  deal: string | null;
  url: string;
  slug: string;
};

type TakealotProductView = {
  core?: { id?: number; title?: string; brand?: string | null; slug?: string };
  buybox_summary?: {
    pretty_price?: string;
    listing_price?: number | null;
    prices?: number[];
    saving?: string | null;
  };
  promotions_summary?: { is_displayed?: boolean; label?: string | null };
};

function categoryFor(title: string, fallback: CategoryName): CategoryName {
  if (/\bomo\b|\bsurf\b|\bskip\b|\bmaq\b|\bariel\b/i.test(title) && !/dish/i.test(title)) {
    return "Laundry Detergent";
  }
  if (/dish|dishwasher/i.test(title)) return "Dishwashing";
  if (/laundry bar|\bbar soap\b|laundry bar/i.test(title)) return "Laundry Bars";
  if (/toilet|bleach|domestos|harpic|\bjik\b/i.test(title) && !/dish/i.test(title)) {
    return "Toilet Cleaners";
  }
  if (/conditioner|softener|comfort|sta-?soft/i.test(title)) return "Fabric Conditioners";
  if (/handy andy|surface cleaner/i.test(title)) return "Hard Surface Cleaners";
  if (/detergent|laundry|washing powder/i.test(title)) return "Laundry Detergent";
  return fallback;
}

function matchBrand(title: string, listed: string | null): (typeof BRANDS)[number] | null {
  const blob = `${listed ?? ""} ${title}`;
  return BRANDS.find((b) => b.re.test(blob)) ?? null;
}

function isPromo(view: TakealotProductView): { saving: string | null; deal: string | null } | null {
  const box = view.buybox_summary ?? {};
  const promo = view.promotions_summary ?? {};
  const price = box.prices?.[0];
  const list = box.listing_price;
  const saving = box.saving?.trim() || null;
  const deal =
    promo.is_displayed && promo.label && !/^save with$/i.test(promo.label.trim())
      ? promo.label.trim()
      : null;
  const cutPct =
    typeof list === "number" && typeof price === "number" && list > 0 ? (list - price) / list : 0;
  const cutLabel = cutPct >= 0.08 ? `${Math.round(cutPct * 100)}% off` : null;
  if (!saving && !deal && !cutLabel) return null;
  return { saving: saving ?? cutLabel, deal };
}

async function searchTakealot(query: string): Promise<TakealotProductView[]> {
  const url = `${TAKEALOT_SEARCH}?qsearch=${encodeURIComponent(query)}`;
  const res = await fetch(url, {
    headers: {
      "User-Agent": "Mozilla/5.0 (compatible; SAHomeCareIntelligence/1.0)",
      Accept: "application/json",
    },
    signal: AbortSignal.timeout(8000),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const json = (await res.json()) as {
    sections?: { products?: { results?: { product_views?: TakealotProductView }[] } };
  };
  return (json.sections?.products?.results ?? [])
    .map((row) => row.product_views)
    .filter((view): view is TakealotProductView => Boolean(view));
}

function toHit(view: TakealotProductView): PromoHit | null {
  const title = view.core?.title?.trim();
  const slug = view.core?.slug?.trim();
  const id = view.core?.id;
  if (!title || !slug || !id) return null;
  const brand = matchBrand(title, view.core?.brand ?? null);
  if (!brand) return null;
  const promo = isPromo(view);
  if (!promo) return null;
  const price = view.buybox_summary?.pretty_price?.trim() || "";
  return {
    title,
    brand: brand.name,
    category: categoryFor(title, brand.category),
    competitor: Boolean(brand.competitor),
    price,
    saving: promo.saving,
    deal: promo.deal,
    url: `https://www.takealot.com/${slug}/PLID${id}`,
    slug,
  };
}

function scoreGroup(group: PromoHit[]): number {
  const first = group[0];
  const pct = Number.parseInt(first.saving ?? "0", 10) || 0;
  return (first.deal ? 80 : 0) + (first.competitor ? 40 : 0) + pct + group.length;
}

function groupHits(hits: PromoHit[]): PromoHit[][] {
  const groups = new Map<string, PromoHit[]>();
  for (const hit of hits) {
    const key = hit.deal
      ? `deal:${hit.brand}:${hit.deal.toLowerCase()}`
      : `cut:${hit.brand}:${(hit.saving ?? "").toLowerCase()}:${hit.price}`;
    const list = groups.get(key) ?? [];
    list.push(hit);
    groups.set(key, list);
  }
  return [...groups.values()];
}

function toSignal(group: PromoHit[], fetchedAt: string): IntelligenceSignal {
  const first = group[0];
  const mechanic = first.deal
    ? first.deal
    : first.saving
      ? `${first.saving} at ${first.price}`
      : `promoted at ${first.price}`;
  const names = [...new Set(group.map((h) => h.title))].slice(0, 3);
  const extra = group.length > names.length ? ` and ${group.length - names.length} more packs` : "";
  const headline = `Takealot: ${first.brand} ${mechanic}`;
  const summary = `${names.join("; ")}${extra}. Live Takealot promotion for South African shoppers.`;
  const id = `live-promo-${createHash("sha1").update(`${first.brand}|${mechanic}`).digest("hex").slice(0, 16)}`;
  return {
    id,
    title: headline,
    source: "takealot.com",
    sourceUrl: first.url,
    publishedAt: fetchedAt,
    detectedAt: fetchedAt,
    signalType: "promotion",
    category: first.category,
    brand: first.brand,
    retailer: "Takealot",
    province: null,
    summary,
    fact: `Takealot is promoting ${first.brand}: ${mechanic}.`,
    interpretation: "",
    recommendation: "",
    whyItMatters: "",
    suggestedInternalQuery: "",
    severity: first.competitor ? "high" : "medium",
    confidence: "high",
    commercialImpact: "unvalidated",
    demo: false,
  };
}

export async function runPromoScan(fetchedAt: string): Promise<{
  signals: IntelligenceSignal[];
  errors: ScanFeedError[];
  feedsAttempted: number;
}> {
  const errors: ScanFeedError[] = [];
  const hits: PromoHit[] = [];
  const results = await Promise.allSettled(QUERIES.map((query) => searchTakealot(query)));
  results.forEach((result, index) => {
    const feed = `Takealot · ${QUERIES[index]}`;
    if (result.status === "rejected") {
      errors.push({
        feed,
        error: result.reason instanceof Error ? result.reason.message : String(result.reason),
      });
      return;
    }
    for (const view of result.value) {
      const hit = toHit(view);
      if (hit) hits.push(hit);
    }
  });

  const seen = new Set<string>();
  const unique = hits.filter((hit) => {
    const key = hit.slug;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  const ranked = groupHits(unique).sort((a, b) => scoreGroup(b) - scoreGroup(a));
  const usedBrand = new Map<string, number>();
  const signals: IntelligenceSignal[] = [];
  for (const group of ranked) {
    const brand = group[0].brand;
    const used = usedBrand.get(brand) ?? 0;
    if (used >= 3) continue;
    usedBrand.set(brand, used + 1);
    signals.push(toSignal(group, fetchedAt));
    if (signals.length >= 12) break;
  }

  return { signals, errors, feedsAttempted: QUERIES.length };
}
