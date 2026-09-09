import {
  CONSUMER_VOICE_TERMS,
  HOME_CARE_TOPIC_TERMS,
  SA_MARKET_TERMS,
  TREND_TERMS,
  matchCatalogBrands,
  type HomeCareBrand,
} from "../home-care-catalog";
import type { Severity } from "../types";

export type XPost = {
  id: string;
  text: string;
  createdAt: string;
  url: string;
  author?: string;
  authorHandle?: string;
  location?: string;
  likes: number;
  replies: number;
  reposts: number;
  hashtags: string[];
  mediaType?: string;
  query: string;
};

export type XRelevance = {
  score: number;
  band: "high" | "medium" | "low" | "drop";
  severity: Severity;
  brands: HomeCareBrand[];
  reasons: string[];
};

const UNILEVER_NOT_HOME_CARE =
  /\b(dove\b|tresemme|trésemmé|knorr|lipton|magnum|hellmann|rexona|vaseline|lifebuoy|aromat)\b/i;

const SPAM =
  /\b(giveaway|follow me|crypto|nft|forex|click here|dm me for)\b/i;

function hasAny(text: string, terms: string[]): boolean {
  const blob = text.toLowerCase();
  return terms.some((term) => blob.includes(term.toLowerCase()));
}

export function scoreXPost(post: XPost): XRelevance {
  const location = post.location ?? "";
  const blob = `${post.text} ${location} ${post.hashtags.join(" ")}`;
  const brands = matchCatalogBrands(blob);
  const own = brands.filter((b) => b.ownership === "unilever");
  const rivals = brands.filter((b) => b.ownership === "competitor");
  const reasons: string[] = [];
  let score = 0;

  if (UNILEVER_NOT_HOME_CARE.test(blob) && own.length === 0 && rivals.length === 0) {
    return { score: 0, band: "drop", severity: "low", brands, reasons: ["Unrelated Unilever division"] };
  }
  if (SPAM.test(blob)) {
    return { score: 0, band: "drop", severity: "low", brands, reasons: ["Spam or promotional noise"] };
  }

  const sa =
    hasAny(blob, SA_MARKET_TERMS) ||
    /south africa|gauteng|cape town|durban|joburg|johannesburg|western cape/i.test(location);
  const distinctive = own.some((b) => !["Comfort", "Surf"].includes(b.name)) || rivals.length > 0;
  if (!sa && !distinctive && own.length === 0) {
    return { score: 0, band: "drop", severity: "low", brands, reasons: ["No South African Home Care link"] };
  }
  if (!sa && own.some((b) => ["Comfort", "Surf"].includes(b.name)) && !hasAny(blob, HOME_CARE_TOPIC_TERMS)) {
    return { score: 0, band: "drop", severity: "low", brands, reasons: ["Ambiguous brand without Home Care or SA context"] };
  }

  if (own.length > 0) {
    score += 35;
    reasons.push(`Unilever brand: ${own.map((b) => b.name).join(", ")}`);
  }
  if (rivals.length > 0) {
    score += 20;
    reasons.push(`Competitor: ${rivals.map((b) => b.name).join(", ")}`);
  }
  if (hasAny(blob, HOME_CARE_TOPIC_TERMS)) {
    score += 15;
    reasons.push("Home Care category language");
  }
  if (hasAny(blob, CONSUMER_VOICE_TERMS)) {
    score += 15;
    reasons.push("Consumer experience language");
  }
  if (hasAny(blob, TREND_TERMS)) {
    score += 10;
    reasons.push("Trend or formulation language");
  }
  if (/\b(vs|versus|better than|switch(?:ed|ing)? to)\b/i.test(blob)) {
    score += 10;
    reasons.push("Product comparison");
  }
  if (hasAny(blob, SA_MARKET_TERMS) || /south africa/i.test(location)) {
    score += 10;
    reasons.push("South African market");
  }

  const engagement = post.likes + post.replies + post.reposts;
  if (engagement >= 200) {
    score += 15;
    reasons.push("High engagement conversation");
  } else if (engagement >= 50) {
    score += 10;
    reasons.push("Elevated engagement");
  }

  score = Math.max(0, Math.min(100, score));

  if (own.length === 0 && rivals.length === 0 && !hasAny(blob, HOME_CARE_TOPIC_TERMS)) {
    return { score, band: "drop", severity: "low", brands, reasons: ["Generic mention"] };
  }

  if (score >= 70) return { score, band: "high", severity: "high", brands, reasons };
  if (score >= 45) return { score, band: "medium", severity: "medium", brands, reasons };
  if (score >= 25) return { score, band: "low", severity: "low", brands, reasons };
  return { score, band: "drop", severity: "low", brands, reasons: ["Below relevance floor"] };
}

export function passesRelevanceThreshold(relevance: XRelevance, threshold: number): boolean {
  if (relevance.band === "drop") return false;
  if (relevance.band === "low" && threshold >= 45) return false;
  return relevance.score >= threshold;
}
