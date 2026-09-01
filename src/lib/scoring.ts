import type { Confidence, Impact, IntelligenceSignal, Opportunity, Severity } from "./types";

const SEVERITY_WEIGHT: Record<Severity, number> = {
  low: 0.25,
  medium: 0.5,
  high: 0.8,
  critical: 1,
};

const CONFIDENCE_WEIGHT: Record<Confidence, number> = {
  low: 0.4,
  medium: 0.7,
  high: 1,
};

const UNILEVER_BRANDS = new Set([
  "OMO",
  "Surf",
  "Skip",
  "Sunlight",
  "Domestos",
  "Comfort",
  "Handy Andy",
  "Sta-soft",
]);

export function unileverExposure(signal: IntelligenceSignal): number {
  if (signal.brand && UNILEVER_BRANDS.has(signal.brand)) return 1;
  const text = `${signal.title} ${signal.whyItMatters} ${signal.interpretation}`.toLowerCase();
  if (/(omo|surf|skip|sunlight|domestos|comfort|handy andy|sta-soft|unilever)/i.test(text)) {
    return 0.85;
  }
  return 0.45;
}

export function commercialImpactLabel(
  impact: Impact | "unvalidated",
): string {
  if (impact === "unvalidated") return "Potential Impact: Requires Internal Validation";
  return impact.toUpperCase();
}

/**
 * Opportunity score /100 from overlapping evidence.
 * Weights: relevance, magnitude, confidence, urgency, Unilever exposure, competitive intensity.
 */
export function scoreOpportunity(input: {
  signals: IntelligenceSignal[];
  relevance: number;
  urgency: number;
  competitiveIntensity: number;
  confidence: Confidence;
}): number {
  if (input.signals.length === 0) return 0;
  const magnitude =
    input.signals.reduce((sum, s) => sum + SEVERITY_WEIGHT[s.severity], 0) /
    input.signals.length;
  const exposure =
    input.signals.reduce((sum, s) => sum + unileverExposure(s), 0) /
    input.signals.length;
  const raw =
    input.relevance * 20 +
    magnitude * 20 +
    CONFIDENCE_WEIGHT[input.confidence] * 15 +
    input.urgency * 15 +
    exposure * 15 +
    input.competitiveIntensity * 15;
  return Math.max(0, Math.min(100, Math.round(raw)));
}

export function shouldCreateOpportunity(signals: IntelligenceSignal[]): boolean {
  if (signals.length >= 2) return true;
  const [only] = signals;
  return Boolean(only && only.confidence === "high" && only.severity !== "low");
}

export function rankOpportunities(opportunities: Opportunity[]): Opportunity[] {
  return [...opportunities].sort((a, b) => b.opportunityScore - a.opportunityScore);
}
