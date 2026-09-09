import type { CategoryName } from "./types";

export type BrandOwnership = "unilever" | "competitor";

export type HomeCareBrand = {
  name: string;
  ownership: BrandOwnership;
  category: CategoryName;
  aliases: string[];
  misspellings: string[];
  hashtags: string[];
  terms: string[];
};

/**
 * Canonical Unilever SA Home Care + competitor brands.
 * Social agents must reuse this list instead of inventing a parallel catalog.
 */
export const HOME_CARE_BRANDS: HomeCareBrand[] = [
  {
    name: "OMO",
    ownership: "unilever",
    category: "Laundry Detergent",
    aliases: ["OMO Auto", "OMO Auto Liquid"],
    misspellings: ["omo auto"],
    hashtags: ["#OMO", "#OMOLaundry"],
    terms: ["washing powder", "laundry liquid", "handwash"],
  },
  {
    name: "Surf",
    ownership: "unilever",
    category: "Laundry Detergent",
    aliases: ["Surf washing powder"],
    misspellings: [],
    hashtags: ["#SurfLaundry"],
    terms: ["washing powder", "laundry"],
  },
  {
    name: "Skip",
    ownership: "unilever",
    category: "Laundry Detergent",
    aliases: ["Skip detergent"],
    misspellings: [],
    hashtags: ["#SkipLaundry"],
    terms: ["detergent", "laundry"],
  },
  {
    name: "Sunlight",
    ownership: "unilever",
    category: "Dishwashing",
    aliases: ["Sunlight Liquid", "Sunlight bar", "Sunlight dishwashing"],
    misspellings: ["sunlite"],
    hashtags: ["#Sunlight", "#SunlightLiquid"],
    terms: ["dishwashing liquid", "laundry bar", "dish"],
  },
  {
    name: "Domestos",
    ownership: "unilever",
    category: "Toilet Cleaners",
    aliases: ["Domestos toilet"],
    misspellings: ["domestus"],
    hashtags: ["#Domestos"],
    terms: ["toilet cleaner", "bleach"],
  },
  {
    name: "Comfort",
    ownership: "unilever",
    category: "Fabric Conditioners",
    aliases: ["Comfort fabric conditioner", "Comfort softener"],
    misspellings: [],
    hashtags: ["#ComfortSoftener"],
    terms: ["fabric conditioner", "fabric softener"],
  },
  {
    name: "Handy Andy",
    ownership: "unilever",
    category: "Hard Surface Cleaners",
    aliases: ["HandyAndy"],
    misspellings: ["handyandy", "handy-andy"],
    hashtags: ["#HandyAndy"],
    terms: ["surface cleaner", "multipurpose cleaner"],
  },
  {
    name: "Jik",
    ownership: "unilever",
    category: "Toilet Cleaners",
    aliases: ["Jik bleach"],
    misspellings: [],
    hashtags: ["#Jik"],
    terms: ["bleach", "toilet"],
  },
  {
    name: "MAQ",
    ownership: "competitor",
    category: "Laundry Detergent",
    aliases: ["MAQ washing powder"],
    misspellings: [],
    hashtags: ["#MAQ"],
    terms: ["washing powder", "laundry"],
  },
  {
    name: "Ariel",
    ownership: "competitor",
    category: "Laundry Detergent",
    aliases: ["Ariel detergent"],
    misspellings: [],
    hashtags: ["#Ariel"],
    terms: ["detergent", "laundry"],
  },
  {
    name: "Harpic",
    ownership: "competitor",
    category: "Toilet Cleaners",
    aliases: ["Harpic toilet"],
    misspellings: [],
    hashtags: ["#Harpic"],
    terms: ["toilet cleaner"],
  },
  {
    name: "Sta-soft",
    ownership: "competitor",
    category: "Fabric Conditioners",
    aliases: ["Stasoft", "Sta soft"],
    misspellings: ["sta soft"],
    hashtags: ["#Stasoft"],
    terms: ["fabric softener"],
  },
  {
    name: "Britelite",
    ownership: "competitor",
    category: "Laundry Bars",
    aliases: ["Brite lite"],
    misspellings: ["brightlite"],
    hashtags: ["#Britelite"],
    terms: ["laundry bar"],
  },
  {
    name: "Finish",
    ownership: "competitor",
    category: "Dishwashing",
    aliases: ["Finish dishwasher"],
    misspellings: [],
    hashtags: ["#FinishDishwasher"],
    terms: ["dishwasher", "dishwashing"],
  },
];

export const UNILEVER_HOME_CARE = HOME_CARE_BRANDS.filter((b) => b.ownership === "unilever");
export const COMPETITOR_HOME_CARE = HOME_CARE_BRANDS.filter((b) => b.ownership === "competitor");

export const HOME_CARE_TOPIC_TERMS = [
  "home care",
  "washing powder",
  "laundry liquid",
  "laundry detergent",
  "laundry bar",
  "dishwashing liquid",
  "fabric conditioner",
  "fabric softener",
  "toilet cleaner",
  "surface cleaner",
  "bleach",
  "refill",
  "fragrance",
  "scent",
];

export const CONSUMER_VOICE_TERMS = [
  "complaint",
  "complain",
  "review",
  "recommend",
  "switch",
  "switched",
  "prefer",
  "preference",
  "doesn't work",
  "doesnt work",
  "not working",
  "watered down",
  "cheap scent",
  "packaging",
  "price",
  "expensive",
  "promotion",
  "specials",
  "out of stock",
  "empty shelf",
  "fragrance",
  "smell",
  "scent",
];

export const TREND_TERMS = [
  "refill",
  "concentrate",
  "concentrated",
  "sustainable",
  "plastic",
  "ingredient",
  "formulation",
  "formula changed",
  "new launch",
  "campaign",
];

export const SA_MARKET_TERMS = [
  "South Africa",
  "South African",
  "UnileverSA",
  "Johannesburg",
  "Joburg",
  "Cape Town",
  "Durban",
  "Shoprite",
  "Checkers",
  "Takealot",
  "Pick n Pay",
  "Boxer",
  "Usave",
];

function quote(term: string): string {
  return /\s/.test(term) || term.startsWith("#") ? `"${term.replaceAll('"', "")}"` : term;
}

export function brandSearchTerms(brand: HomeCareBrand): string[] {
  return [brand.name, ...brand.aliases, ...brand.misspellings, ...brand.hashtags]
    .map((t) => t.trim())
    .filter(Boolean);
}

export function matchCatalogBrands(text: string): HomeCareBrand[] {
  return HOME_CARE_BRANDS.filter((brand) => {
    const names = brandSearchTerms(brand);
    return names.some((name) => {
      const escaped = name.replace(/^#/, "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const flexible = escaped.replace(/ /g, "[- ]");
      return new RegExp(`\\b${flexible}\\b`, "i").test(text);
    });
  });
}

export function orClause(terms: string[]): string {
  const unique = [...new Set(terms.map((t) => t.trim()).filter(Boolean))];
  return `(${unique.map(quote).join(" OR ")})`;
}
