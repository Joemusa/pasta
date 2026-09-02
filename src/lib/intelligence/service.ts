import type {
  AskResponse,
  IntelligenceOverview,
  IntelligenceSignal,
  InternalQueryResult,
  Opportunity,
  PeriodDays,
  ScanStatus,
  SignalType,
} from "../types";
import { deltaLabel } from "../utils";
import { rankOpportunities } from "../scoring";
import {
  COMPETITORS,
  HEATMAP,
  MACRO_TRIGGERS,
  NEWS_SOURCES,
  OPPORTUNITIES,
  PROVINCES,
  RETAILERS,
  SCAN_NOTIFICATIONS,
  THREATS,
} from "./demo-data";

export interface SignalFilters {
  period: PeriodDays;
  type: SignalType | "all";
  search: string;
  category: string;
  brand: string;
  retailer: string;
  province: string;
}

const REFERENCE_NOW = new Date("2026-09-01T12:00:00+02:00");

function nowForFilter(): Date {
  const actual = new Date();
  return actual > REFERENCE_NOW ? actual : REFERENCE_NOW;
}

type Store = {
  signals: IntelligenceSignal[];
  lastScanAt: string;
  scanStatus: ScanStatus;
  opportunities: typeof OPPORTUNITIES;
  dismissedOpportunityIds: string[];
  briefIds: string[];
};

const store: Store = {
  signals: [],
  lastScanAt: "",
  scanStatus: "online",
  opportunities: OPPORTUNITIES.map((o) => ({ ...o })),
  dismissedOpportunityIds: [],
  briefIds: [],
};

export function ingestLiveSignals(live: IntelligenceSignal[]) {
  const unique = new Map<string, IntelligenceSignal>();
  for (const signal of live) {
    if (signal.demo) continue;
    unique.set(signal.id, signal);
  }
  const liveList = [...unique.values()].sort(
    (a, b) => +new Date(b.publishedAt) - +new Date(a.publishedAt),
  );
  store.signals = liveList;
  store.lastScanAt = new Date().toISOString();
  store.scanStatus = liveList.length > 0 ? "online" : "degraded";
}

export function hydrateLiveSignals(live: IntelligenceSignal[], lastScanAt?: string) {
  if (live.length === 0) return;
  ingestLiveSignals(live);
  if (lastScanAt) store.lastScanAt = lastScanAt;
}

function inPeriod(iso: string, period: PeriodDays, now = nowForFilter()): boolean {
  const start = new Date(now);
  start.setDate(start.getDate() - period);
  return new Date(iso) >= start;
}

function previousWindow(iso: string, period: PeriodDays, now = nowForFilter()): boolean {
  const end = new Date(now);
  end.setDate(end.getDate() - period);
  const start = new Date(end);
  start.setDate(start.getDate() - period);
  const d = new Date(iso);
  return d >= start && d < end;
}

export function getAllSignals(): IntelligenceSignal[] {
  return store.signals;
}

export function getSignals(filters?: Partial<SignalFilters>): IntelligenceSignal[] {
  const period = filters?.period ?? 14;
  const type = filters?.type ?? "all";
  return store.signals
    .filter((s) => inPeriod(s.publishedAt, period))
    .filter((s) => (type === "all" ? true : s.signalType === type))
    .filter((s) => {
      const q = (filters?.search ?? "").trim().toLowerCase();
      if (!q) return true;
      return `${s.title} ${s.summary} ${s.brand ?? ""} ${s.retailer ?? ""} ${s.source}`
        .toLowerCase()
        .includes(q);
    })
    .filter((s) => (filters?.category ? s.category === filters.category : true))
    .filter((s) => (filters?.brand ? s.brand === filters.brand : true))
    .filter((s) => (filters?.retailer ? s.retailer === filters.retailer : true))
    .filter((s) => (filters?.province ? s.province === filters.province : true))
    .sort((a, b) => +new Date(b.publishedAt) - +new Date(a.publishedAt));
}

export function getSignalById(id: string): IntelligenceSignal | undefined {
  return store.signals.find((s) => s.id === id);
}

export function getOverview(period: PeriodDays): IntelligenceOverview {
  const current = store.signals.filter((s) => inPeriod(s.publishedAt, period));
  const previous = store.signals.filter((s) => previousWindow(s.publishedAt, period));

  const count = (
    list: IntelligenceSignal[],
    pred: (s: IntelligenceSignal) => boolean,
  ) => list.filter(pred).length;

  const kpis = [
    {
      key: "critical",
      label: "Critical Signals",
      value: count(current, (s) => s.severity === "critical" || s.severity === "high"),
      previous: count(previous, (s) => s.severity === "critical" || s.severity === "high"),
      severity: "high" as const,
    },
    {
      key: "competitors",
      label: "Competitor Moves",
      value: count(current, (s) => s.signalType === "competitor" || s.signalType === "promotion"),
      previous: count(previous, (s) => s.signalType === "competitor" || s.signalType === "promotion"),
      severity: "high" as const,
    },
    {
      key: "retailers",
      label: "Retailer Moves",
      value: count(current, (s) => s.signalType === "retailer"),
      previous: count(previous, (s) => s.signalType === "retailer"),
      severity: "medium" as const,
    },
    {
      key: "macro",
      label: "Macro Triggers",
      value: count(current, (s) => s.signalType === "macro" || s.signalType === "consumer"),
      previous: count(previous, (s) => s.signalType === "macro" || s.signalType === "consumer"),
      severity: "medium" as const,
    },
    {
      key: "opportunities",
      label: "Opportunities",
      value: store.opportunities.filter((o) => o.status !== "dismissed").length,
      previous: Math.max(1, store.opportunities.length - 2),
      severity: "low" as const,
    },
    {
      key: "threats",
      label: "Threats",
      value: THREATS.filter((t) => t.level === "high" || t.level === "critical").length,
      previous: 1,
      severity: "high" as const,
    },
  ];

  return {
    period,
    kpis,
    opportunities: rankOpportunities(
      store.opportunities.filter((o) => !store.dismissedOpportunityIds.includes(o.id)),
    ),
    threats: THREATS,
    lastScanAt: store.lastScanAt,
    scanStatus: store.scanStatus,
  };
}

export function getKpiDelta(value: number, previous: number) {
  return deltaLabel(value, previous);
}

export function getCompetitors() {
  return COMPETITORS;
}

export function getRetailers() {
  return RETAILERS;
}

export function getHeatmap() {
  return HEATMAP;
}

export function getMacro() {
  return MACRO_TRIGGERS;
}

export function getProvinces() {
  return PROVINCES;
}

export function getSources() {
  return NEWS_SOURCES;
}

export function getNotifications() {
  return SCAN_NOTIFICATIONS;
}

export function getScanMeta() {
  return { lastScanAt: store.lastScanAt, scanStatus: store.scanStatus };
}

export function setScanStatus(status: ScanStatus, lastScanAt?: string) {
  store.scanStatus = status;
  if (lastScanAt) store.lastScanAt = lastScanAt;
}

const SCAN_SIGNAL: IntelligenceSignal = {
  id: "sig-scan-picknpay-maq",
  title: "Pick n Pay leaflet adds MAQ 2-for price feature",
  source: "Supermarket & Retailer",
  sourceUrl: "https://www.supermarket.co.za",
  publishedAt: "2026-09-01T11:05:00+02:00",
  detectedAt: "2026-09-01T12:10:00+02:00",
  signalType: "promotion",
  category: "Laundry Detergent",
  brand: "MAQ",
  retailer: "Pick n Pay",
  province: "gauteng",
  summary:
    "A new Pick n Pay leaflet feature puts MAQ on a 2-for price mechanic in Gauteng.",
  fact: "Demo scan: Pick n Pay Gauteng leaflet now features MAQ on a 2-for mechanic.",
  interpretation:
    "MAQ is moving from value banners into a mainstream grocery leaflet, widening OMO exposure.",
  recommendation:
    "Check OMO versus MAQ share and promo intensity in Pick n Pay Gauteng for the leaflet week.",
  whyItMatters:
    "Mainstream-banner features make MAQ a broader Unilever problem than a Usave-only story.",
  suggestedInternalQuery:
    "Pick n Pay Gauteng: OMO vs MAQ value share, volume and % sales on promo for the leaflet week versus prior 4 weeks.",
  severity: "high",
  confidence: "medium",
  commercialImpact: "unvalidated",
  demo: true,
};

export function runScan(): { lastScanAt: string; added: IntelligenceSignal | null } {
  const lastScanAt = new Date().toISOString();
  store.lastScanAt = lastScanAt;
  store.scanStatus = "online";
  const exists = store.signals.some((s) => s.id === SCAN_SIGNAL.id);
  if (!exists) {
    store.signals = [SCAN_SIGNAL, ...store.signals];
    return { lastScanAt, added: SCAN_SIGNAL };
  }
  return { lastScanAt, added: null };
}

export function dismissOpportunity(id: string) {
  store.dismissedOpportunityIds.push(id);
  store.opportunities = store.opportunities.map((o) =>
    o.id === id ? { ...o, status: "dismissed" } : o,
  );
}

export function addOpportunityToBrief(id: string) {
  if (!store.briefIds.includes(id)) store.briefIds.push(id);
  store.opportunities = store.opportunities.map((o) =>
    o.id === id ? { ...o, status: "on-brief" } : o,
  );
}

export function getBriefOpportunityIds() {
  return store.briefIds;
}

export function getOpportunity(id: string) {
  return store.opportunities.find((o) => o.id === id);
}

export function getOpportunities() {
  return rankOpportunities(
    store.opportunities.filter((o) => !store.dismissedOpportunityIds.includes(o.id)),
  );
}

export function createOpportunityFromSignal(signalId: string): Opportunity | null {
  const signal = getSignalById(signalId);
  if (!signal) return null;
  const id = `opp-from-${signalId}`;
  if (store.opportunities.some((o) => o.id === id)) {
    return store.opportunities.find((o) => o.id === id) ?? null;
  }
  const created: Opportunity = {
    id,
    title: `Investigate: ${signal.title}`,
    description: signal.interpretation,
    category: signal.category ?? "Laundry Detergent",
    brand: signal.brand ?? "Unilever Home Care",
    opportunityScore: 58,
    impact: signal.severity === "low" ? "low" : "medium",
    confidence: signal.confidence,
    evidence: [signal.fact],
    recommendedAction: signal.recommendation,
    status: "open",
    signalIds: [signal.id],
    createdAt: new Date().toISOString(),
    demo: true,
  };
  store.opportunities = [created, ...store.opportunities];
  return created;
}

const AGENT_REPLIES: Record<string, Omit<InternalQueryResult, "id" | "query" | "agent" | "createdAt" | "signalId">> = {
  "shares-growth": {
    status: "ready",
    fact: "Demo internal extract: In the latest 12-week POS window, MAQ value share rose in Usave and Shoprite while OMO value share declined in the same banners. Surf declined faster than OMO in Shoprite Gauteng. National totals are not shown as a single financial impact figure because not every banner-week is complete.",
    interpretation:
      "The external MAQ promotion story is consistent with directional share movement in value banners. This is still a demo join — treat magnitudes as illustrative until the live Price/Shares agent is connected.",
    recommendation:
      "Focus the defence on Usave Limpopo, Shoprite Gauteng and Boxer KZN rather than a national OMO relaunch.",
    demo: true,
  },
  price: {
    status: "ready",
    fact: "Demo internal extract: MAQ average selling price sits below OMO in Usave and Shoprite. Britelite bar ASP moved down in Usave Eastern Cape. Comfort ASP in SPAR Gauteng is above Sta-soft during the multi-buy.",
    interpretation:
      "Price gaps, not only feature slots, are doing the work in value laundry and in SPAR conditioner.",
    recommendation:
      "Run price-pack architecture on OMO Auto/handwash and Sunlight bar before adding more promo spend.",
    demo: true,
  },
  distribution: {
    status: "ready",
    fact: "Demo internal extract: Sunlight bar numeric distribution in new Boxer KZN stores is below the Boxer chain average. MAQ distribution in Usave Limpopo is complete for core SKUs.",
    interpretation:
      "Listing gaps in growth banners will read as share loss even if brand equity is intact.",
    recommendation:
      "Close Sunlight bar listings in new Boxer stores this cycle.",
    demo: true,
  },
  promotion: {
    status: "ready",
    fact: "Demo internal extract: MAQ % sales on promo is elevated in Usave and Shoprite. Comfort % sales on promo in SPAR is below Sta-soft for the same weeks.",
    interpretation:
      "Unilever is being out-featured in the weeks that matter (grant week, SPAR leaflet).",
    recommendation:
      "Reallocate promo slots toward SASSA week in value banners and SPAR conditioner features.",
    demo: true,
  },
  category: {
    status: "ready",
    fact: "Demo internal extract: Laundry detergent remains the largest Home Care value pool. Laundry bars still over-index in Boxer and Usave. Toilet care over-indexes in Clicks.",
    interpretation:
      "The live fights sit in the largest pools (laundry liquids) and in the specialist channel (Clicks toilet care).",
    recommendation:
      "Keep category resource on laundry value defence first, Clicks toilet care second.",
    demo: true,
  },
  opportunity: {
    status: "ready",
    fact: "Demo internal extract: Ranked commercial actions from the existing Commercial Brain remain directional. No rand incremental sales figure is attached because addressable opportunity is not guaranteed.",
    interpretation:
      "External signals and internal ranking agree that OMO/MAQ is the lead action; Sunlight bar is second.",
    recommendation:
      "Promote 'Defend OMO against MAQ' onto the weekly brief and attach the Usave Limpopo query.",
    demo: true,
  },
};

export function runInternalQuery(input: {
  agent: string;
  query: string;
  signalId?: string | null;
}): InternalQueryResult {
  const template = AGENT_REPLIES[input.agent] ?? {
    status: "unavailable" as const,
    fact: "No internal agent is connected for this workspace yet.",
    interpretation:
      "The query is stored so it can be sent to the Price, Promotion, Distribution or Shares agents on the pasta commercial stack.",
    recommendation: "Connect the internal POS agents, then re-run this query.",
    demo: true as const,
  };
  return {
    id: `q-${Date.now()}`,
    signalId: input.signalId ?? null,
    query: input.query,
    agent: input.agent,
    createdAt: new Date().toISOString(),
    ...template,
  };
}

export function askIntelligence(question: string): AskResponse {
  const q = question.toLowerCase();
  const overview = getOverview(14);
  const top = overview.opportunities[0];

  if (q.includes("threat") && q.includes("omo")) {
    return {
      question,
      answer:
        "The biggest threat to OMO in this scan window is MAQ’s value positioning, amplified by affordability pressure and a Usave grant-week end-cap.",
      evidence: [
        "FACT: MAQ remains on aggressive promotional pricing across major banners (BusinessTech, demo scan).",
        "FACT: Usave Limpopo featured MAQ on an end-cap during SASSA week (Supermarket & Retailer, demo scan).",
        "FACT: Food inflation and a fuel increase are tightening household cash (Fin24, demo scan).",
      ],
      whyItMatters:
        "OMO is Unilever’s core laundry franchise. Value-banner share lost in grant week is hard to retake in the same month.",
      recommendedAction:
        "Analyse internally: OMO vs MAQ share, ASP and promo intensity in Usave, Shoprite and Boxer over 12 weeks.",
      internalDataQuery:
        "Compare OMO, Surf and MAQ value share, volume share, ASP, distribution and promotional intensity over the last 12 weeks. Identify retailers and provinces where MAQ gained while OMO declined.",
    };
  }
  if (q.includes("maq") && (q.includes("share") || q.includes("gaining"))) {
    return {
      question,
      answer:
        "External signals show MAQ gaining competitive momentum in value banners. Internal share confirmation is still CONNECT DATA — do not treat a rand impact as known.",
      evidence: [
        "FACT: MAQ promotions and a Usave Limpopo end-cap were detected this period.",
        "FACT: Shoprite private-label detergent ranging is also expanding, so MAQ is not the only value pressure.",
      ],
      whyItMatters:
        "If internal POS confirms MAQ gains where OMO declines, this is a defence brief, not a brand campaign brief.",
      recommendedAction: "Run the Shares & Growth Expert on Usave, Shoprite and Boxer.",
      internalDataQuery:
        "MAQ versus OMO and Surf: 12-week value and volume share by retailer and province.",
    };
  }
  if (q.includes("this week") || q.includes("changed")) {
    return {
      question,
      answer: `In the last 14 days the system logged ${overview.kpis[0].value} high-impact signals, with MAQ, Shoprite private label, Gauteng water interruptions and a Britelite bar price cut as the lead stories.`,
      evidence: overview.opportunities.slice(0, 3).map((o) => `Opportunity: ${o.title} (${o.opportunityScore}/100)`),
      whyItMatters:
        "These are the moves that can change Unilever Home Care share this month, not general news.",
      recommendedAction: `Start with ${top?.title ?? "the top-ranked opportunity"} and attach internal POS.`,
      internalDataQuery:
        "Latest 12-week Home Care scorecard: Unilever versus named competitors by retailer.",
    };
  }
  if (q.includes("retailer") && q.includes("opportunit")) {
    return {
      question,
      answer:
        "Usave currently shows the highest competitive intensity, followed by Shoprite and Boxer. That is where Unilever can still move the needle this month — by defending listings and grant-week features, not by a national brand burst.",
      evidence: [
        "FACT: Usave intensity score is 91/100 in the demo heatmap (MAQ end-cap + Britelite price cut).",
        "FACT: Boxer is adding KZN stores (Moneyweb, demo scan).",
      ],
      whyItMatters: "Growth and value banners set the price and listing waterline for Home Care.",
      recommendedAction: "Build a Usave + Boxer defence pack for laundry liquids and bars.",
      internalDataQuery:
        "Usave and Boxer: Unilever Home Care distribution, share and promo intensity versus MAQ and Britelite.",
    };
  }
  if (q.includes("aggressive") || q.includes("competitor is")) {
    return {
      question,
      answer: "MAQ is the most aggressive competitor this period, with Harpic second in Clicks and Britelite third on laundry bars.",
      evidence: [
        "MAQ: high price, high promo, high retailer activity.",
        "Harpic: high promo in Clicks Western Cape.",
        "Britelite: high price activity in Usave Eastern Cape.",
      ],
      whyItMatters: "Aggression is concentrated, which makes response cheaper than a category-wide war.",
      recommendedAction: "Three focused responses, not one generic competitor programme.",
      internalDataQuery: "Rank competitor promo intensity and ASP gaps versus Unilever equivalents, 12 weeks.",
    };
  }
  if (q.includes("sunlight") && q.includes("bar")) {
    return {
      question,
      answer:
        "Sunlight laundry bar is exposed by a Britelite price cut in Usave Eastern Cape and by Boxer expansion in KZN, where bars over-index.",
      evidence: [
        "FACT: Britelite reduced bar price in Usave Eastern Cape (Retail Brief Africa, demo scan).",
        "FACT: Boxer is opening stores in KwaZulu-Natal (Moneyweb, demo scan).",
      ],
      whyItMatters:
        "Bars are a high-penetration Unilever franchise among lower-income households. A price or listing gap becomes a share gap quickly.",
      recommendedAction: "Day-one Boxer listings and a Usave price-gap close.",
      internalDataQuery:
        "Sunlight bar vs Britelite vs Rave: ASP, volume share and numeric distribution in Usave and Boxer.",
    };
  }
  if (q.includes("external") || q.includes("macro") || q.includes("affect")) {
    return {
      question,
      answer:
        "Fuel, food inflation, SASSA payment timing, Gauteng water interruptions and Stage 2 load-shedding are the external factors most likely to move Home Care sales this month.",
      evidence: MACRO_TRIGGERS.slice(0, 5).map((m) => `${m.title} — ${m.potentialHomecareImpact}`),
      whyItMatters:
        "These triggers change pack size, banner and brand choice; they are not background colour.",
      recommendedAction: "Overlay grant week and water-outage weeks on the POS calendar before reading share moves.",
      internalDataQuery:
        "Weekly Home Care volume versus fuel-change, SASSA and Gauteng outage weeks.",
    };
  }

  const hits = getSignals({ period: 14, search: question, type: "all" }).slice(0, 3);
  return {
    question,
    answer:
      hits.length > 0
        ? `The closest matching intelligence is: ${hits.map((h) => h.title).join("; ")}.`
        : "No single signal matches that question closely. The lead commercial question remains OMO defence versus MAQ in value banners.",
    evidence:
      hits.length > 0
        ? hits.map((h) => `FACT: ${h.fact}`)
        : ["No additional matching facts in the demo set."],
    whyItMatters:
      hits[0]?.whyItMatters ??
      "Unilever Home Care decisions should stay tied to detected signals, not general category commentary.",
    recommendedAction: hits[0]?.recommendation ?? top?.recommendedAction ?? "Open the Opportunity Radar.",
    internalDataQuery:
      hits[0]?.suggestedInternalQuery ??
      "Run a 12-week Unilever Home Care scorecard by retailer and brand.",
  };
}

export { REFERENCE_NOW };
