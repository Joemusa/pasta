import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import path from "path";
import type { MacroPoint, MacroSnapshot, MacroSource } from "../types";
import { buildMacroCommentary, summariseLatest } from "./macro-commentary";

const CACHE_PATH = process.env.VERCEL
  ? path.join("/tmp", "macro-series.json")
  : path.join(process.cwd(), "data", "macro-series.json");

const CACHE_TTL_MS = 6 * 60 * 60 * 1000;
const FETCH_MS = 20_000;

const BIS_CPI_URL =
  "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_LONG_CPI/1.0/M.ZA.771?format=sdmx-json&startPeriod=2016";
const BIS_RATE_URL =
  "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/M.ZA?format=sdmx-json&startPeriod=2016";
const WB_CPI_URL =
  "https://api.worldbank.org/v2/country/ZAF/indicator/FP.CPI.TOTL.ZG?format=json&per_page=80";
const WB_RATE_URL =
  "https://api.worldbank.org/v2/country/ZAF/indicator/FR.INR.LEND?format=json&per_page=80";

type SeriesPoint = { period: string; value: number };

type CacheFile = {
  savedAt: string;
  snapshot: MacroSnapshot;
};

function headers(): HeadersInit {
  return {
    "User-Agent": "Mozilla/5.0 (compatible; SAHomeCareIntelligence/1.0; +https://cursor.com)",
    Accept: "application/json, application/vnd.sdmx.data+json, */*",
  };
}

async function fetchJson(url: string): Promise<unknown> {
  const res = await fetch(url, {
    headers: headers(),
    signal: AbortSignal.timeout(FETCH_MS),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  return res.json();
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

function normalizePeriod(raw: string): string | null {
  const monthly = raw.match(/^(\d{4})-(\d{2})(?:-\d{2})?$/);
  if (monthly) return `${monthly[1]}-${monthly[2]}`;
  const annual = raw.match(/^(\d{4})$/);
  if (annual) return `${annual[1]}-12`;
  return null;
}

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function parseBisSdmx(raw: unknown, preferredUnit?: string): SeriesPoint[] {
  const root = asRecord(raw);
  const data = asRecord(root?.data) ?? root;
  const dataSets = data?.dataSets;
  const dataset = Array.isArray(dataSets) ? asRecord(dataSets[0]) : null;
  const structure = asRecord(data?.structure) ?? asRecord(root?.structure);
  if (!dataset || !structure) return [];

  const dimensions = asRecord(structure.dimensions);
  const obsDims = Array.isArray(dimensions?.observation)
    ? (dimensions.observation as Record<string, unknown>[])
    : [];
  const seriesDims = Array.isArray(dimensions?.series)
    ? (dimensions.series as Record<string, unknown>[])
    : [];
  const timeDim =
    obsDims.find((d) => d.id === "TIME_PERIOD" || d.id === "TIME") ?? obsDims[0];
  const timeValues = Array.isArray(timeDim?.values)
    ? (timeDim.values as Record<string, unknown>[])
    : [];

  const seriesMap = asRecord(dataset.series);
  const entries: [string, Record<string, unknown>][] = seriesMap
    ? Object.entries(seriesMap).flatMap(([key, value]) => {
        const rec = asRecord(value);
        return rec ? [[key, rec] as [string, Record<string, unknown>]] : [];
      })
    : dataset.observations
      ? [["0", dataset]]
      : [];

  const unitIdx = seriesDims.findIndex((d) => d.id === "UNIT_MEASURE");
  let chosen = entries[0];
  if (preferredUnit && unitIdx >= 0) {
    const unitDim = seriesDims[unitIdx];
    const unitValues = Array.isArray(unitDim?.values)
      ? (unitDim.values as Record<string, unknown>[])
      : [];
    const match = entries.find(([key]) => {
      const parts = key.split(":").map(Number);
      const unit = unitValues[parts[unitIdx]];
      return String(unit?.id) === preferredUnit || String(unit?.name).includes("Year-on-year");
    });
    if (match) chosen = match;
  }
  if (!chosen) return [];

  const observations = asRecord(chosen[1].observations);
  if (!observations) return [];

  const points: SeriesPoint[] = [];
  for (const [indexKey, cell] of Object.entries(observations)) {
    const idx = Number(indexKey);
    const timeId = String(timeValues[idx]?.id ?? timeValues[idx]?.name ?? "");
    const period = normalizePeriod(timeId);
    const value = toNumber(Array.isArray(cell) ? cell[0] : cell);
    if (!period || value == null) continue;
    points.push({ period, value });
  }
  return points.sort((a, b) => a.period.localeCompare(b.period));
}

function parseWorldBank(raw: unknown): SeriesPoint[] {
  if (!Array.isArray(raw) || raw.length < 2 || !Array.isArray(raw[1])) return [];
  const points: SeriesPoint[] = [];
  for (const row of raw[1]) {
    const rec = asRecord(row);
    const period = normalizePeriod(String(rec?.date ?? ""));
    const value = toNumber(rec?.value);
    if (!period || value == null) continue;
    points.push({ period, value });
  }
  return points.sort((a, b) => a.period.localeCompare(b.period));
}

function mergeSeries(inflation: SeriesPoint[], rates: SeriesPoint[]): MacroPoint[] {
  const map = new Map<string, MacroPoint>();
  for (const point of inflation) {
    map.set(point.period, { period: point.period, inflation: point.value, policyRate: null });
  }
  for (const point of rates) {
    const existing = map.get(point.period);
    if (existing) existing.policyRate = point.value;
    else map.set(point.period, { period: point.period, inflation: null, policyRate: point.value });
  }
  return [...map.values()].sort((a, b) => a.period.localeCompare(b.period));
}

function readCache(): CacheFile | null {
  try {
    if (!existsSync(CACHE_PATH)) return null;
    return JSON.parse(readFileSync(CACHE_PATH, "utf8")) as CacheFile;
  } catch {
    return null;
  }
}

function writeCache(snapshot: MacroSnapshot) {
  mkdirSync(path.dirname(CACHE_PATH), { recursive: true });
  const payload: CacheFile = { savedAt: snapshot.fetchedAt, snapshot };
  writeFileSync(CACHE_PATH, JSON.stringify(payload, null, 2));
}

function cacheIsFresh(cache: CacheFile | null): cache is CacheFile {
  if (!cache?.snapshot?.points?.length) return false;
  const age = Date.now() - +new Date(cache.savedAt);
  return Number.isFinite(age) && age >= 0 && age < CACHE_TTL_MS;
}

async function loadInflation(): Promise<{ points: SeriesPoint[]; source: MacroSource | null; error?: string }> {
  try {
    const points = parseBisSdmx(await fetchJson(BIS_CPI_URL), "771");
    if (points.length === 0) throw new Error("BIS CPI returned no observations");
    return {
      points,
      source: {
        id: "bis-cpi",
        name: "BIS long CPI · South Africa, year-on-year % (Stats SA via BIS)",
        series: "inflation",
        url: "https://data.bis.org/topics/CPI",
        frequency: "monthly",
      },
    };
  } catch (error) {
    const bisError = error instanceof Error ? error.message : "BIS CPI failed";
    try {
      const points = parseWorldBank(await fetchJson(WB_CPI_URL));
      if (points.length === 0) throw new Error("World Bank CPI returned no observations");
      return {
        points,
        source: {
          id: "wb-cpi",
          name: "World Bank · South Africa CPI inflation (annual %)",
          series: "inflation",
          url: "https://data.worldbank.org/indicator/FP.CPI.TOTL.ZG?locations=ZA",
          frequency: "annual",
        },
        error: `BIS CPI fallback used (${bisError})`,
      };
    } catch (fallbackError) {
      const extra = fallbackError instanceof Error ? fallbackError.message : "World Bank CPI failed";
      return { points: [], source: null, error: `${bisError}; ${extra}` };
    }
  }
}

async function loadPolicyRate(): Promise<{ points: SeriesPoint[]; source: MacroSource | null; error?: string }> {
  try {
    const points = parseBisSdmx(await fetchJson(BIS_RATE_URL));
    if (points.length === 0) throw new Error("BIS policy rate returned no observations");
    return {
      points,
      source: {
        id: "bis-repo",
        name: "BIS central bank policy rates · South Africa (SARB repo)",
        series: "policyRate",
        url: "https://data.bis.org/topics/CBPOL",
        frequency: "monthly",
      },
    };
  } catch (error) {
    const bisError = error instanceof Error ? error.message : "BIS policy rate failed";
    try {
      const points = parseWorldBank(await fetchJson(WB_RATE_URL));
      if (points.length === 0) throw new Error("World Bank lending rate returned no observations");
      return {
        points,
        source: {
          id: "wb-lend",
          name: "World Bank · South Africa lending interest rate (annual %)",
          series: "policyRate",
          url: "https://data.worldbank.org/indicator/FR.INR.LEND?locations=ZA",
          frequency: "annual",
        },
        error: `BIS policy-rate fallback used (${bisError})`,
      };
    } catch (fallbackError) {
      const extra = fallbackError instanceof Error ? fallbackError.message : "World Bank lending rate failed";
      return { points: [], source: null, error: `${bisError}; ${extra}` };
    }
  }
}

function buildSnapshot(
  inflation: SeriesPoint[],
  rates: SeriesPoint[],
  sources: MacroSource[],
  errors: string[],
): MacroSnapshot {
  const points = mergeSeries(inflation, rates);
  return {
    fetchedAt: new Date().toISOString(),
    points,
    latest: summariseLatest(points),
    commentary: buildMacroCommentary(points),
    sources,
    errors,
  };
}

export async function loadMacroSnapshot(options?: { refresh?: boolean }): Promise<MacroSnapshot> {
  if (!options?.refresh) {
    const cached = readCache();
    if (cacheIsFresh(cached)) return cached.snapshot;
  }

  const [inflation, rates] = await Promise.all([loadInflation(), loadPolicyRate()]);
  const sources = [inflation.source, rates.source].filter((s): s is MacroSource => Boolean(s));
  const errors = [inflation.error, rates.error].filter((e): e is string => Boolean(e));
  const snapshot = buildSnapshot(inflation.points, rates.points, sources, errors);

  if (snapshot.points.length > 0) {
    try {
      writeCache(snapshot);
    } catch {
      // Persist is best-effort on Vercel /tmp.
    }
  }
  return snapshot;
}

export function macroCsv(snapshot: MacroSnapshot): string {
  const header = "period,inflation_yoy_pct,policy_rate_pct";
  const rows = snapshot.points.map((p) => {
    const inflation = p.inflation == null ? "" : p.inflation.toFixed(3);
    const rate = p.policyRate == null ? "" : p.policyRate.toFixed(3);
    return `${p.period},${inflation},${rate}`;
  });
  const notes = snapshot.commentary.behaviours.map((line) => csvCell(line));
  return `\uFEFF${header}\n${rows.join("\n")}\n\ncommentary\n${notes.join("\n")}\n`;
}

function csvCell(value: string): string {
  const text = value.replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
  if (/[",\n]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

export function macroCsvFilename(now = new Date()): string {
  return `unilever-sa-homecare-macro-${now.toISOString().slice(0, 10)}.csv`;
}