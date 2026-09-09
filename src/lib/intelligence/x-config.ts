import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import path from "path";

export type XAgentSettings = {
  enabled: boolean;
  maxPosts: number;
  relevanceThreshold: number;
  lookbackHours: number;
  extraQuery: string;
};

const DEFAULTS: XAgentSettings = {
  enabled: true,
  maxPosts: 12,
  relevanceThreshold: 40,
  lookbackHours: 48,
  extraQuery: "",
};

const FILE_PATH = process.env.VERCEL
  ? path.join("/tmp", "x-agent.json")
  : path.join(process.cwd(), "data", "x-agent.json");

function clampInt(value: unknown, min: number, max: number, fallback: number): number {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(min, Math.min(max, Math.round(n)));
}

function fromEnv(): Partial<XAgentSettings> {
  const enabledRaw = process.env.X_AGENT_ENABLED;
  return {
    enabled: enabledRaw == null ? undefined : enabledRaw !== "false" && enabledRaw !== "0",
    maxPosts: process.env.X_MAX_POSTS ? Number(process.env.X_MAX_POSTS) : undefined,
    relevanceThreshold: process.env.X_RELEVANCE_THRESHOLD
      ? Number(process.env.X_RELEVANCE_THRESHOLD)
      : undefined,
    lookbackHours: process.env.X_LOOKBACK_HOURS ? Number(process.env.X_LOOKBACK_HOURS) : undefined,
    extraQuery: process.env.X_QUERY_EXTRA,
  };
}

function readFileSettings(): Partial<XAgentSettings> {
  try {
    if (!existsSync(FILE_PATH)) return {};
    return JSON.parse(readFileSync(FILE_PATH, "utf8")) as Partial<XAgentSettings>;
  } catch {
    return {};
  }
}

export function normalizeXSettings(input: Partial<XAgentSettings>): XAgentSettings {
  return {
    enabled: input.enabled ?? DEFAULTS.enabled,
    maxPosts: clampInt(input.maxPosts, 1, 40, DEFAULTS.maxPosts),
    relevanceThreshold: clampInt(input.relevanceThreshold, 0, 90, DEFAULTS.relevanceThreshold),
    lookbackHours: clampInt(input.lookbackHours, 1, 168, DEFAULTS.lookbackHours),
    extraQuery: (input.extraQuery ?? "").trim().slice(0, 400),
  };
}

export function getXBearerToken(): string {
  return (process.env.X_BEARER_TOKEN || process.env.TWITTER_BEARER_TOKEN || "").trim();
}

export function xTokenConfigured(): boolean {
  return getXBearerToken().length > 0;
}

export function getXSettings(): XAgentSettings {
  const file = readFileSettings();
  const env = fromEnv();
  return normalizeXSettings({
    ...DEFAULTS,
    ...file,
    ...Object.fromEntries(Object.entries(env).filter(([, v]) => v !== undefined && v !== "")),
  });
}

export function writeXSettings(patch: Partial<XAgentSettings>): XAgentSettings {
  const next = normalizeXSettings({ ...getXSettings(), ...patch });
  mkdirSync(path.dirname(FILE_PATH), { recursive: true });
  writeFileSync(FILE_PATH, JSON.stringify(next, null, 2));
  return next;
}

export function publicXStatus() {
  const settings = getXSettings();
  return {
    ...settings,
    tokenConfigured: xTokenConfigured(),
    source: "X",
    sourceType: "social_media" as const,
    api: "X API v2 recent search",
    maxLookbackHours: 168,
  };
}
