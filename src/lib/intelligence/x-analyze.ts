import { analyseStory } from "../product-impact";
import type { CategoryName, IntelligenceSignal, Sentiment } from "../types";
import type { XPost, XRelevance } from "./x-relevance";

const NEGATIVE =
  /\b(hate|terrible|awful|worst|scam|fake|watered down|doesn't work|doesnt work|disappointed|complaint|smells? (bad|off|cheap)|never again|waste|useless|broke out)\b/i;
const POSITIVE =
  /\b(love|great|best|works|recommend|favourite|favorite|amazing|smells? (good|nice|amazing)|must buy)\b/i;

export function inferSentiment(text: string): Sentiment {
  const neg = NEGATIVE.test(text);
  const pos = POSITIVE.test(text);
  if (neg && !pos) return "negative";
  if (pos && !neg) return "positive";
  return "neutral";
}

export function inferTopic(text: string): string {
  if (/\b(promo|promotion|special|discount|% off|on special)\b/i.test(text)) return "promotion";
  if (/\b(out of stock|empty shelf|can't find|cannot find|unavailable)\b/i.test(text)) return "availability";
  if (/\b(price|expensive|cheap|cost)\b/i.test(text)) return "pricing";
  if (/\b(pack|packaging|bottle|pouch|refill)\b/i.test(text)) return "packaging";
  if (/\b(smell|scent|fragrance|perfume)\b/i.test(text)) return "fragrance";
  if (/\b(vs|versus|better than|switch)\b/i.test(text)) return "comparison";
  if (/\b(launch|new|campaign|advert|ad)\b/i.test(text)) return "campaign";
  if (/\b(sustainable|plastic|concentrate|formula)\b/i.test(text)) return "trend";
  if (/\b(complaint|disappointed|hate|doesn't work|doesnt work)\b/i.test(text)) return "complaint";
  if (/\b(love|recommend|best)\b/i.test(text)) return "praise";
  return "product discussion";
}

function attentionFor(relevance: XRelevance, engagement: number, sentiment: Sentiment): "low" | "medium" | "high" {
  if (relevance.band === "high" || engagement >= 200 || (sentiment === "negative" && relevance.brands.some((b) => b.ownership === "unilever"))) {
    return "high";
  }
  if (relevance.band === "medium" || engagement >= 50) return "medium";
  return "low";
}

export function xPostToSignal(
  post: XPost,
  relevance: XRelevance,
  fetchedAt: string,
): IntelligenceSignal {
  const handle = post.authorHandle ? `@${post.authorHandle.replace(/^@/, "")}` : "an X account";
  const quoted = post.text.replace(/\s+/g, " ").trim();
  const brand = relevance.brands.find((b) => b.ownership === "unilever") ?? relevance.brands[0];
  const category = (brand?.category ?? null) as CategoryName | null;
  const sentiment = inferSentiment(post.text);
  const topic = inferTopic(post.text);
  const engagement = post.likes + post.replies + post.reposts;
  const fact = `On X, ${handle} posted: "${quoted}".`;
  const draft: IntelligenceSignal = {
    id: `live-x-${post.id}`,
    title: quoted.length > 110 ? `${quoted.slice(0, 107).replace(/\s+\S*$/, "")}…` : quoted,
    source: "X",
    sourceUrl: post.url,
    publishedAt: post.createdAt,
    detectedAt: fetchedAt,
    signalType:
      relevance.brands.some((b) => b.ownership === "competitor") &&
      !relevance.brands.some((b) => b.ownership === "unilever")
        ? "competitor"
        : topic === "promotion"
          ? "promotion"
          : "consumer",
    category,
    brand: brand?.name ?? null,
    retailer: null,
    province: null,
    summary: `${quoted}${post.location ? ` Location mentioned: ${post.location}.` : ""} South African Home Care conversation on X (consumer opinion, not a verified fact).`,
    fact,
    interpretation: "",
    recommendation: "",
    whyItMatters: "",
    suggestedInternalQuery: "",
    severity: relevance.severity,
    confidence: engagement >= 50 ? "medium" : "low",
    commercialImpact: "unvalidated",
    demo: false,
    sourceType: "social_media",
    sentiment,
    relevanceScore: relevance.score,
    importanceScore: Math.min(100, relevance.score + Math.min(20, Math.floor(engagement / 20))),
    attention: attentionFor(relevance, engagement, sentiment),
    author: post.author,
    authorHandle: post.authorHandle,
    engagement: { likes: post.likes, replies: post.replies, reposts: post.reposts },
    hashtags: post.hashtags,
    searchQuery: post.query,
    topic,
    mediaType: post.mediaType,
  };

  const analysis = analyseStory(draft);
  const interpretation = `Interpretation, not a verified fact: ${analysis.meaning}`;
  const recommendation =
    sentiment === "negative" && brand?.ownership === "unilever"
      ? `Check whether this ${analysis.product} issue is showing up in HelloPeter, ratings or repeat purchase before treating a single X post as a market fact.`
      : `Compare this X conversation with News24, Takealot and HelloPeter before acting.`;

  return {
    ...draft,
    interpretation,
    recommendation,
    whyItMatters: interpretation,
    category: (draft.category ?? analysis.category) as CategoryName | null,
    brand: draft.brand ?? analysis.brand,
  };
}
