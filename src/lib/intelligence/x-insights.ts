import type { IntelligenceSignal, Sentiment } from "../types";

export type XInsightReport = {
  posts: number;
  sentiment: Record<Sentiment, number>;
  consumerVoice: string;
  brandSentiment: string;
  productIssues: string[];
  competitive: string[];
  trends: string[];
  important: string[];
  implication: string;
};

const EMPTY: XInsightReport = {
  posts: 0,
  sentiment: { positive: 0, neutral: 0, negative: 0 },
  consumerVoice: "No X posts in this view yet.",
  brandSentiment: "No X sentiment to summarise.",
  productIssues: [],
  competitive: [],
  trends: [],
  important: [],
  implication:
    "X is social-media discussion, not a verified fact. Compare with News24, Takealot and HelloPeter.",
};

export function isXSignal(signal: IntelligenceSignal): boolean {
  return signal.source === "X" || signal.sourceType === "social_media";
}

function top(values: string[], limit = 3): string[] {
  const counts = new Map<string, number>();
  for (const value of values) {
    const key = value.trim();
    if (!key) continue;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([key, n]) => (n > 1 ? `${key} (${n})` : key));
}

export function xInsights(signals: IntelligenceSignal[]): XInsightReport {
  const posts = signals.filter(isXSignal);
  if (posts.length === 0) return EMPTY;

  const sentiment: Record<Sentiment, number> = { positive: 0, neutral: 0, negative: 0 };
  for (const post of posts) {
    const key = post.sentiment ?? "neutral";
    sentiment[key] += 1;
  }

  const brands = posts.map((p) => p.brand).filter((b): b is string => Boolean(b));
  const issues = posts
    .filter((p) => p.sentiment === "negative" || p.topic === "complaint")
    .map((p) => p.topic || p.title);
  const competitive = posts
    .filter((p) => p.signalType === "competitor" || p.topic === "comparison")
    .map((p) => p.title);
  const trends = posts.filter((p) => p.topic === "trend" || p.topic === "packaging").map((p) => p.title);
  const important = posts
    .filter((p) => p.attention === "high" || (p.relevanceScore ?? 0) >= 70)
    .map((p) => p.title);

  const leadBrand = top(brands, 1)[0] ?? "Unilever Home Care";
  const consumerVoice =
    posts.length === 1
      ? `One consumer conversation on X about ${leadBrand}. Treat as opinion, not a market fact.`
      : `Consumers on X are talking about ${top(brands).join(", ") || "Home Care"}. ${sentiment.negative} negative, ${sentiment.positive} positive, ${sentiment.neutral} neutral.`;

  return {
    posts: posts.length,
    sentiment,
    consumerVoice,
    brandSentiment: `X sentiment mix — negative ${sentiment.negative}, neutral ${sentiment.neutral}, positive ${sentiment.positive}. Individual posts are unverified consumer opinion.`,
    productIssues: top(issues),
    competitive: top(competitive),
    trends: top(trends),
    important: important.slice(0, 3),
    implication:
      "Use X to spot issues and comparisons early, then confirm with HelloPeter complaints, Takealot promotions and News24 before changing price, pack or media.",
  };
}
