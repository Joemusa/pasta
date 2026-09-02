export type Severity = "low" | "medium" | "high" | "critical";
export type Confidence = "low" | "medium" | "high";
export type Impact = "low" | "medium" | "high";
export type PeriodDays = 7 | 14 | 30;
export type ScanStatus = "online" | "scanning" | "degraded";

export type SignalType =
  | "competitor"
  | "retailer"
  | "promotion"
  | "macro"
  | "consumer"
  | "opportunity"
  | "threat";

export type CategoryName =
  | "Laundry Detergent"
  | "Laundry Bars"
  | "Dishwashing"
  | "Toilet Cleaners"
  | "Fabric Conditioners"
  | "Hard Surface Cleaners";

export type ProvinceId =
  | "gauteng"
  | "kwazulu-natal"
  | "western-cape"
  | "eastern-cape"
  | "free-state"
  | "limpopo"
  | "mpumalanga"
  | "north-west"
  | "northern-cape";

export type Ownership = "unilever" | "competitor";

export interface IntelligenceSignal {
  id: string;
  title: string;
  source: string;
  sourceUrl: string | null;
  publishedAt: string;
  detectedAt: string;
  signalType: SignalType;
  category: CategoryName | null;
  brand: string | null;
  retailer: string | null;
  province: ProvinceId | null;
  summary: string;
  fact: string;
  interpretation: string;
  recommendation: string;
  whyItMatters: string;
  suggestedInternalQuery: string;
  severity: Severity;
  confidence: Confidence;
  commercialImpact: Impact | "unvalidated";
  demo: boolean;
}

export interface CompetitorBrand {
  id: string;
  name: string;
  company: string;
  category: CategoryName;
  ownership: Ownership;
  active: boolean;
  threatLevel: Severity | "own";
  priceActivity: Severity;
  promotionalActivity: Severity;
  newLaunches: Severity | "none";
  distribution: Severity;
  marketingActivity: Severity;
  socialActivity: Severity;
  retailerActivity: Severity;
  shareMovement: string;
  aiInterpretation: string;
}

export interface RetailerRecord {
  id: string;
  name: string;
  type: string;
  active: boolean;
  currentPromotions: string;
  privateLabel: string;
  priceChanges: string;
  competitorActivity: string;
  storeNetwork: string;
  distributionChanges: string;
  homeCareActivity: string;
  intensity: number;
}

export interface Opportunity {
  id: string;
  title: string;
  description: string;
  category: CategoryName;
  brand: string;
  opportunityScore: number;
  impact: Impact;
  confidence: Confidence;
  evidence: string[];
  recommendedAction: string;
  status: "open" | "in-review" | "on-brief" | "dismissed";
  signalIds: string[];
  createdAt: string;
  demo: true;
}

export interface Threat {
  id: string;
  title: string;
  level: Severity;
  signals: string[];
  recommendedResponse: string;
  category: CategoryName;
  brand: string;
}

export interface MacroTrigger {
  id: string;
  title: string;
  type: "consumer-economy" | "cash-flow" | "infrastructure" | "weather";
  location: string;
  severity: Severity;
  startDate: string;
  endDate: string | null;
  description: string;
  affectedConsumers: string;
  potentialHomecareImpact: string;
  recommendedInternalQuery: string;
}

export interface InternalAgent {
  id: string;
  name: string;
  expertise: string;
}

export interface InternalQueryResult {
  id: string;
  signalId: string | null;
  query: string;
  agent: string;
  status: "ready" | "pending" | "unavailable";
  fact: string;
  interpretation: string;
  recommendation: string;
  createdAt: string;
  demo: true;
}

export interface AskResponse {
  question: string;
  answer: string;
  evidence: string[];
  whyItMatters: string;
  recommendedAction: string;
  internalDataQuery: string;
}

export interface NewsSource {
  id: string;
  name: string;
  url: string;
  region: string;
  active: boolean;
}

export interface HeatCell {
  brand: string;
  retailer: string;
  score: number;
}

export interface ProvinceIntel {
  id: ProvinceId;
  name: string;
  signals: { label: string; severity: Severity }[];
  summary: string;
}

export interface OverviewKpi {
  key: string;
  label: string;
  value: number;
  previous: number;
  severity: Severity;
}

export interface IntelligenceOverview {
  period: PeriodDays;
  kpis: OverviewKpi[];
  opportunities: Opportunity[];
  threats: Threat[];
  lastScanAt: string;
  scanStatus: ScanStatus;
}
