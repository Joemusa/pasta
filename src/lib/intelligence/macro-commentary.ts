import type { MacroCommentary, MacroLatest, MacroPoint } from "../types";

const CPI_TARGET_LOW = 3;
const CPI_TARGET_HIGH = 6;

export function lastDefined(
  points: MacroPoint[],
  key: "inflation" | "policyRate",
): { period: string; value: number } | null {
  for (let i = points.length - 1; i >= 0; i--) {
    const value = points[i][key];
    if (typeof value === "number") return { period: points[i].period, value };
  }
  return null;
}

export function valueAt(points: MacroPoint[], period: string, key: "inflation" | "policyRate"): number | null {
  const hit = points.find((p) => p.period === period);
  const value = hit?.[key];
  return typeof value === "number" ? value : null;
}

export function shiftPeriod(period: string, months: number): string {
  const [yearRaw, monthRaw] = period.split("-");
  const year = Number(yearRaw);
  const month = Number(monthRaw || "12");
  if (!year || !month) return period;
  const date = new Date(year, month - 1 + months, 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

export function formatMacroPeriod(period: string): string {
  const [year, month] = period.split("-");
  if (!month) return year;
  const label = new Date(Number(year), Number(month) - 1, 1).toLocaleDateString("en-GB", {
    month: "short",
    year: "numeric",
  });
  return label;
}

export function formatPct(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function summariseLatest(points: MacroPoint[]): MacroLatest {
  const inflation = lastDefined(points, "inflation");
  const policy = lastDefined(points, "policyRate");
  const inflationYearAgo =
    inflation ? valueAt(points, shiftPeriod(inflation.period, -12), "inflation") : null;
  const policyYearAgo = policy ? valueAt(points, shiftPeriod(policy.period, -12), "policyRate") : null;
  const realRate =
    inflation && policy && inflation.period === policy.period
      ? policy.value - inflation.value
      : inflation && policy
        ? policy.value - inflation.value
        : null;
  return {
    inflationPeriod: inflation?.period ?? null,
    inflation: inflation?.value ?? null,
    inflationYearAgo,
    policyPeriod: policy?.period ?? null,
    policyRate: policy?.value ?? null,
    policyYearAgo,
    realRate,
  };
}

function direction(current: number | null, previous: number | null): "up" | "down" | "flat" | "unknown" {
  if (current == null || previous == null) return "unknown";
  const delta = current - previous;
  if (delta > 0.25) return "up";
  if (delta < -0.25) return "down";
  return "flat";
}

function threeMonthChange(points: MacroPoint[], key: "inflation" | "policyRate"): number | null {
  const latest = lastDefined(points, key);
  if (!latest) return null;
  const prior = valueAt(points, shiftPeriod(latest.period, -3), key);
  if (prior == null) return null;
  return latest.value - prior;
}

export function buildMacroCommentary(points: MacroPoint[]): MacroCommentary {
  const latest = summariseLatest(points);
  if (latest.inflation == null && latest.policyRate == null) {
    return {
      headline: "Macro series could not be loaded, so no Home Care read is possible yet.",
      facts: [],
      behaviours: [],
    };
  }

  const cpiDir = direction(latest.inflation, latest.inflationYearAgo);
  const rateDir = direction(latest.policyRate, latest.policyYearAgo);
  const cpi3m = threeMonthChange(points, "inflation");
  const facts: string[] = [];

  if (latest.inflation != null && latest.inflationPeriod) {
    facts.push(
      `South African headline CPI inflation was ${formatPct(latest.inflation)} in ${formatMacroPeriod(latest.inflationPeriod)}.`,
    );
    if (latest.inflationYearAgo != null) {
      facts.push(
        `Twelve months earlier it was ${formatPct(latest.inflationYearAgo)}, so inflation is ${
          cpiDir === "up" ? "higher" : cpiDir === "down" ? "lower" : "broadly unchanged"
        } than a year ago.`,
      );
    }
    if (cpi3m != null) {
      facts.push(
        `Over the latest three months, CPI has ${
          cpi3m > 0.2 ? "re-accelerated" : cpi3m < -0.2 ? "slowed" : "moved sideways"
        } by ${cpi3m >= 0 ? "+" : ""}${cpi3m.toFixed(1)} percentage points.`,
      );
    }
    if (latest.inflation > CPI_TARGET_HIGH) {
      facts.push("Inflation is above the South African Reserve Bank’s 3–6% target band.");
    } else if (latest.inflation < CPI_TARGET_LOW) {
      facts.push("Inflation is below the bottom of the SARB 3–6% target band.");
    } else {
      facts.push("Inflation is inside the SARB 3–6% target band.");
    }
  }

  if (latest.policyRate != null && latest.policyPeriod) {
    facts.push(
      `The SARB policy rate was ${formatPct(latest.policyRate)} in ${formatMacroPeriod(latest.policyPeriod)}.`,
    );
    if (latest.policyYearAgo != null) {
      facts.push(
        `A year earlier it was ${formatPct(latest.policyYearAgo)}, so the policy stance is ${
          rateDir === "down"
            ? "easier than twelve months ago"
            : rateDir === "up"
              ? "tighter than twelve months ago"
              : "broadly unchanged versus twelve months ago"
        }.`,
      );
    }
  }

  if (latest.realRate != null) {
    facts.push(
      `The implied real policy rate (policy rate minus CPI) is ${latest.realRate.toFixed(1)} percentage points.`,
    );
  }

  const behaviours: string[] = [];
  const cpi = latest.inflation;
  const rate = latest.policyRate;
  const real = latest.realRate;

  if (cpi != null && cpi >= 6) {
    behaviours.push(
      "High inflation typically pushes laundry shoppers down the ladder: OMO Auto toward OMO handwash or Surf, and Unilever liquids toward MAQ and retailer private label. Value banners (Usave, Boxer, Shoprite) take mix.",
    );
    behaviours.push(
      "Pack architecture matters more than brand advertising: smaller OMO and Sunlight packs, laundry bars, and multi-buys outperform large premium bottles until CPI cools.",
    );
  } else if (cpi != null && cpi >= 4 && (cpiDir === "up" || (cpi3m != null && cpi3m > 0.3))) {
    behaviours.push(
      "A CPI rebound inside the target band still tightens the weekly shop. Promo elasticity rises on OMO, Sunlight dishwashing liquid and Comfort; MAQ and Sta-soft features will convert more easily.",
    );
    behaviours.push(
      "Sunlight laundry bars and value dishwash keep a defensive role. Do not read a quiet month in premium SKUs as a brand problem until the CPI bump is overlaid on POS.",
    );
  } else if (cpi != null && cpi < 4) {
    behaviours.push(
      "Lower inflation opens a window to recover mix into mid-tier and premium Home Care — OMO Auto, Comfort, Domestos and Handy Andy — if retailers stop over-featuring value brands.",
    );
    behaviours.push(
      "The recovery is not automatic: households that switched to MAQ or bars during the squeeze often need a price-pack reason to switch back, not only a lower CPI print.",
    );
  }

  if (rate != null && rate >= 8) {
    behaviours.push(
      "A high policy rate squeezes household credit and spaza / independent working capital. Shoppers buy smaller, more frequent Home Care packs; 5ℓ dishwash and bulk fabric conditioner slow first.",
    );
  } else if (rate != null && rateDir === "down") {
    behaviours.push(
      "Policy-rate cuts ease the squeeze with a lag of a quarter or more. Treat any mix recovery in Comfort, Domestos and Handy Andy as tentative until several months of easier rates are in the data.",
    );
  } else if (rate != null && rateDir === "up") {
    behaviours.push(
      "A rate hike on top of still-visible CPI keeps cash tight. Defend OMO and Sunlight versus MAQ and Britelite in grant-week leaflets rather than launching premium variants.",
    );
  }

  if (real != null && real >= 3) {
    behaviours.push(
      "Tight real rates keep discretionary Home Care under pressure — fabric conditioner (Comfort vs Sta-soft) and specialist toilet care (Domestos vs Harpic). Core laundry powder and dishwash are more defensive but still trade down.",
    );
  } else if (real != null && real < 1.5 && cpi != null && cpi <= 4.5) {
    behaviours.push(
      "A thinner real-rate cushion plus contained CPI is the mix-friendly regime: retailers can be pushed to feature OMO and Comfort rather than only the cheapest detergent on the shelf.",
    );
  }

  if (cpiDir === "up" && rateDir === "up") {
    behaviours.push(
      "Inflation and interest rates moving up together is a double squeeze. Expect more down-trade and promo hunting; the commercial response is price-pack architecture and value-banner defence, not a brand burst.",
    );
  } else if (cpiDir === "down" && rateDir === "down") {
    behaviours.push(
      "Both series easing is the conditions for a slow mix repair. Watch whether OMO and Sunlight liquid regain volume from MAQ and bars over the next two POS quarters, not the next leaflet.",
    );
  }

  if (behaviours.length === 0) {
    behaviours.push(
      "Overlay these prints on weekly Home Care POS before reading share moves: grant week, fuel changes and leaflet intensity still explain more of a four-week swing than a 0.2 point CPI move.",
    );
  }

  behaviours.push(
    "This is directional category behaviour, not a sales forecast. Confirm with internal POS on OMO, Surf, Sunlight, Comfort, Domestos and Handy Andy versus MAQ, Sta-soft, Harpic and Britelite.",
  );

  return { headline: buildHeadline(latest, cpiDir, rateDir), facts, behaviours };
}

function buildHeadline(
  latest: MacroLatest,
  cpiDir: "up" | "down" | "flat" | "unknown",
  rateDir: "up" | "down" | "flat" | "unknown",
): string {
  const cpiBit =
    latest.inflation != null
      ? `CPI ${formatPct(latest.inflation)}${
          latest.inflationPeriod ? ` (${formatMacroPeriod(latest.inflationPeriod)})` : ""
        }`
      : "CPI unavailable";
  const rateBit =
    latest.policyRate != null
      ? `policy rate ${formatPct(latest.policyRate)}${
          latest.policyPeriod ? ` (${formatMacroPeriod(latest.policyPeriod)})` : ""
        }`
      : "policy rate unavailable";

  if (cpiDir === "up" && rateDir === "up") {
    return `${cpiBit} and the ${rateBit} are both firmer — value Home Care likely stays in charge.`;
  }
  if (cpiDir === "up" && (rateDir === "down" || rateDir === "flat")) {
    return `${cpiBit} is picking up while the ${rateBit} is not tightening in step — shopper squeeze can still intensify.`;
  }
  if (cpiDir === "down" && rateDir === "down") {
    return `${cpiBit} and the ${rateBit} are easing — mix into OMO, Comfort and Sunlight liquid can start to recover, slowly.`;
  }
  if (cpiDir === "down" && rateDir === "up") {
    return `${cpiBit} is cooling but the ${rateBit} is tighter — real rates, not the CPI print, still set the shopper mood.`;
  }
  return `${cpiBit}; ${rateBit}. Watch value versus mid-tier Home Care mix from here.`;
}
