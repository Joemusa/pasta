import type { IntelligenceSignal } from "./types";

const UNILEVER = [
  { name: "OMO", re: /\bomo\b/i },
  { name: "Surf", re: /\bsurf\b/i },
  { name: "Skip", re: /\bskip\b/i },
  { name: "Sunlight", re: /\bsunlight\b/i },
  { name: "Domestos", re: /\bdomestos\b/i },
  { name: "Comfort", re: /\bcomfort\b/i },
  { name: "Handy Andy", re: /\bhandy andy\b/i },
  { name: "Jik", re: /\bjik\b/i },
] as const;

const COMPETITORS = [
  { name: "MAQ", re: /\bmaq\b/i, products: ["OMO", "Surf"], why: "MAQ is competing in laundry detergent value." },
  { name: "Ariel", re: /\bariel\b/i, products: ["OMO", "Surf"], why: "Ariel is competing in laundry detergent." },
  { name: "Harpic", re: /\bharpic\b/i, products: ["Domestos"], why: "Harpic is competing in toilet care." },
  { name: "Sta-soft", re: /\bsta-?soft\b/i, products: ["Comfort"], why: "Sta-soft is competing in fabric conditioner." },
  { name: "Britelite", re: /\bbritelite\b/i, products: ["Sunlight"], why: "Britelite is competing in laundry bars." },
  { name: "Finish", re: /\bfinish\b/i, products: ["Sunlight"], why: "Finish is competing in dishwashing." },
] as const;

function andList(names: string[]): string {
  const unique = [...new Set(names)];
  if (unique.length === 1) return unique[0];
  if (unique.length === 2) return `${unique[0]} and ${unique[1]}`;
  return `${unique.slice(0, -1).join(", ")} and ${unique[unique.length - 1]}`;
}

function blobOf(signal: IntelligenceSignal): string {
  return `${signal.title} ${signal.summary} ${signal.brand ?? ""} ${signal.retailer ?? ""}`;
}

/**
 * One line only when a story names a Unilever Home Care brand or a mapped competitor.
 * No generic market commentary.
 */
export function productImpact(signal: IntelligenceSignal): string | null {
  const blob = blobOf(signal);
  const own = UNILEVER.filter((b) => b.re.test(blob)).map((b) => b.name);
  const rivals = COMPETITORS.filter((c) => c.re.test(blob));
  const products = [...own, ...rivals.flatMap((r) => r.products)];
  if (products.length === 0) return null;

  if (rivals.length > 0) {
    return `Possible impact on ${andList(products)}: ${rivals[0].why}`;
  }
  return `Possible impact on ${andList(own)}: this story names the Unilever brand.`;
}
