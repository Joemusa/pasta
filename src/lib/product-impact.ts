import type { IntelligenceSignal } from "./types";

const UNILEVER = [
  { name: "OMO", re: /\bomo\b/i, need: /\b(unilever|detergent|laundry|washing powder|handwash|2-in-1)\b/i },
  { name: "Surf", re: /\bsurf\b/i, need: /\b(unilever|detergent|laundry|washing powder|handwash|2-in-1)\b/i },
  { name: "Skip", re: /\bskip\b/i, need: /\b(unilever|detergent|laundry|washing)\b/i },
  { name: "Sunlight", re: /\bsunlight\b/i, need: /\b(dish|laundry|bar|liquid|soap|unilever|detergent|washing)\b/i },
  { name: "Domestos", re: /\bdomestos\b/i, need: null },
  { name: "Comfort", re: /\bcomfort\b/i, need: /\b(fabric|conditioner|softener|unilever|sta-?soft)\b/i },
  { name: "Handy Andy", re: /\bhandy andy\b/i, need: null },
  { name: "Jik", re: /\bjik\b/i, need: null },
] as const;

const COMPETITORS = [
  { name: "MAQ", re: /\bmaq\b/i, products: ["OMO", "Surf"], category: "Laundry Detergent" as const },
  { name: "Ariel", re: /\bariel\b/i, products: ["OMO", "Surf"], category: "Laundry Detergent" as const },
  { name: "Harpic", re: /\bharpic\b/i, products: ["Domestos"], category: "Toilet Cleaners" as const },
  { name: "Sta-soft", re: /\bsta-?soft\b/i, products: ["Comfort"], category: "Fabric Conditioners" as const },
  { name: "Britelite", re: /\bbritelite\b/i, products: ["Sunlight"], category: "Laundry Bars" as const },
  { name: "Finish", re: /\bfinish\b/i, products: ["Sunlight"], category: "Dishwashing" as const },
] as const;

export type StoryAnalysis = {
  category: string;
  brand: string;
  product: string;
  meaning: string;
};

function blobOf(signal: IntelligenceSignal): string {
  return `${signal.title} ${signal.summary} ${signal.brand ?? ""} ${signal.retailer ?? ""}`;
}

function andList(names: string[]): string {
  const unique = [...new Set(names)];
  if (unique.length === 1) return unique[0];
  if (unique.length === 2) return `${unique[0]} and ${unique[1]}`;
  return `${unique.slice(0, -1).join(", ")} and ${unique[unique.length - 1]}`;
}

function ownBrands(blob: string): string[] {
  return UNILEVER.filter((b) => b.re.test(blob) && (b.need == null || b.need.test(blob))).map(
    (b) => b.name,
  );
}

function inferCategory(blob: string, signal: IntelligenceSignal, brands: string[]): string {
  if (signal.category) return signal.category;
  if (/dish|dishwashing|sunlight liquid|finish/i.test(blob)) return "Dishwashing";
  if (/laundry bar|sunlight bar|britelite/i.test(blob)) return "Laundry Bars";
  if (/toilet|domestos|harpic|jik bleach/i.test(blob)) return "Toilet Cleaners";
  if (/conditioner|comfort|sta-?soft|fabric soft/i.test(blob)) return "Fabric Conditioners";
  if (/handy andy|surface cleaner|hard surface/i.test(blob)) return "Hard Surface Cleaners";
  if (/detergent|laundry|omo|maq|surf|ariel|skip|washing powder/i.test(blob)) {
    return "Laundry Detergent";
  }
  if (/liquid production|home care liquids|home care/i.test(blob)) return "Home Care liquids";
  if (brands.includes("Sunlight")) return "Dishwashing";
  if (brands.includes("OMO") || brands.includes("Surf") || brands.includes("Skip")) {
    return "Laundry Detergent";
  }
  if (brands.includes("Domestos") || brands.includes("Jik")) return "Toilet Cleaners";
  if (brands.includes("Handy Andy")) return "Hard Surface Cleaners";
  if (brands.includes("Comfort")) return "Fabric Conditioners";
  return "Unilever Home Care";
}

function inferProduct(blob: string, brands: string[], category: string, rivals: string[]): string {
  if (/\bsunlight\b/i.test(blob) && /dish|liquid|label|claim/i.test(blob)) {
    return "Sunlight dishwashing liquid";
  }
  if (/\bsunlight\b/i.test(blob) && /bar/i.test(blob)) return "Sunlight laundry bar";
  if (/\bomo\b/i.test(blob) && /auto|liquid/i.test(blob)) return "OMO Auto / liquid detergent";
  if (/\bomo\b/i.test(blob)) return "OMO laundry detergent";
  if (/\bsurf\b/i.test(blob)) return "Surf laundry detergent";
  if (/\bhandy andy\b/i.test(blob)) return "Handy Andy hard-surface cleaner";
  if (/\bdomestos\b/i.test(blob)) return "Domestos toilet care";
  if (/\bcomfort\b/i.test(blob)) return "Comfort fabric conditioner";
  if (/liquid production|african demand/i.test(blob)) {
    return "Home Care liquids (OMO, Sunlight and other Unilever liquids)";
  }
  if (brands.length > 0) return `${andList(brands)} in ${category}`;
  if (rivals.length > 0) return `${category} brands pressed by ${andList(rivals)}`;
  return `${category} products`;
}

function inferMeaning(
  blob: string,
  category: string,
  brand: string,
  product: string,
  rivals: string[],
): string {
  if (/misleading|label|claim|advertising standard|\basa\b|packaging copy|plant-based/i.test(blob)) {
    return `${product} faces a claims or pack-copy issue in ${category}. If the wording on pack, ads or leaflets has to change, Unilever loses a selling line that Finish, retailer own-label and value dishwashing can attack. Check SA artwork, website claims and current Shoprite / Pick n Pay features for ${brand} until the label is clean.`;
  }
  if (/liquid production|capacity|manufactur|plant|african demand|expands liquid/i.test(blob)) {
    return `This is a supply and mix signal for Unilever Home Care in Africa, including South Africa. More liquid capacity supports ${product} and a shift away from powders and laundry bars. Watch fill rates, listings and share for OMO Auto/liquids and Sunlight liquid versus powder, bar and competitor value brands.`;
  }
  if (/recall|contamination|quality issue|withdrawal/i.test(blob)) {
    return `This is a quality or availability risk on ${product}. Gaps on shelf in ${category} usually move volume to the next brand in the fixture within the same shopping trip.`;
  }
  if (/promo|promotion|special|leaflet|discount|price cut|feature/i.test(blob)) {
    return `This is a promotional event on ${product}. In South African grocery, a value-banner feature can decide the month’s share for ${brand}. Compare facings and price against the nearest competitor in Shoprite, Usave, Boxer and Pick n Pay.`;
  }
  if (rivals.length > 0) {
    return `${andList(rivals)} is competing in ${category} against Unilever’s ${brand}. That typically shows up as price, promo or listing pressure on ${product} in Shoprite, Usave and Boxer. Check the gap versus ${andList(rivals)} this week, not only the brand campaign.`;
  }
  if (/price|asp|cost|raw material/i.test(blob)) {
    return `This is a cost or price story for ${product} in ${category}. Home Care shoppers in South Africa trade down quickly; if ${brand} moves up, MAQ, Britelite, Finish or private label usually take the volume.`;
  }
  return `This sits in ${category} and can move shopper choice or retailer ranging on ${product}. For Unilever SA the question is whether ${brand} gains or loses listings, claims, price position or share off the back of it.`;
}

/**
 * Category, brand and product read for Unilever SA Home Care.
 */
export function analyseStory(signal: IntelligenceSignal): StoryAnalysis {
  const blob = blobOf(signal);
  const own = ownBrands(blob);
  const rivals = COMPETITORS.filter((c) => c.re.test(blob));
  const rivalNames = rivals.map((r) => r.name);
  const brandNames = own.length > 0 ? own : rivals.flatMap((r) => r.products);
  const category =
    rivals[0]?.category ??
    inferCategory(blob, signal, brandNames);
  const brand =
    own.length > 0 ? andList(own) : brandNames.length > 0 ? andList(brandNames) : "Unilever Home Care";
  const product = inferProduct(blob, own.length > 0 ? own : brandNames, category, rivalNames);
  return {
    category,
    brand,
    product,
    meaning: inferMeaning(blob, category, brand, product, rivalNames),
  };
}

/** @deprecated use analyseStory */
export function productImpact(signal: IntelligenceSignal): string | null {
  const analysis = analyseStory(signal);
  return `Possible impact on ${analysis.brand}: ${analysis.meaning}`;
}
