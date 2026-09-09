"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { IntelligenceSignal, PeriodDays, ScanStatus } from "@/lib/types";

type AppState = {
  period: PeriodDays;
  setPeriod: (p: PeriodDays) => void;
  collapsed: boolean;
  setCollapsed: (v: boolean | ((c: boolean) => boolean)) => void;
  mobileNav: boolean;
  setMobileNav: (v: boolean) => void;
  lastScanAt: string;
  scanStatus: ScanStatus;
  signals: IntelligenceSignal[];
  liveCount: number;
  scanMessage: string | null;
  bootDone: boolean;
  runNewScan: () => Promise<void>;
};

const Ctx = createContext<AppState | null>(null);
const FRESH_MS = 15 * 60 * 1000;

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException
    ? error.name === "AbortError"
    : error instanceof Error && error.name === "AbortError";
}

function isFresh(iso: string): boolean {
  if (!iso) return false;
  const ts = Date.parse(iso);
  return Number.isFinite(ts) && Date.now() - ts < FRESH_MS;
}

async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  timeoutMs: number,
  external?: AbortSignal,
): Promise<Response> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  const onAbort = () => ctrl.abort();
  external?.addEventListener("abort", onAbort);
  try {
    return await fetch(url, { ...init, cache: "no-store", signal: ctrl.signal });
  } finally {
    clearTimeout(timer);
    external?.removeEventListener("abort", onAbort);
  }
}

export function AppProvider({
  children,
  initialSignals = [],
  initialLastScanAt = "",
}: {
  children: ReactNode;
  initialSignals?: IntelligenceSignal[];
  initialLastScanAt?: string;
}) {
  const seeded = initialSignals.filter((s) => !s.demo);
  const hasSeed = seeded.length > 0;
  const [period, setPeriod] = useState<PeriodDays>(90);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [lastScanAt, setLastScanAt] = useState(initialLastScanAt);
  const [scanStatus, setStatus] = useState<ScanStatus>(hasSeed ? "online" : "scanning");
  const [signals, setSignals] = useState<IntelligenceSignal[]>(seeded);
  const [liveCount, setLiveCount] = useState(seeded.length);
  const [scanMessage, setScanMessage] = useState<string | null>(
    hasSeed ? null : "Loading live news…",
  );
  const [bootDone, setBootDone] = useState(hasSeed);
  const signalsRef = useRef(seeded);

  useEffect(() => {
    signalsRef.current = signals;
  }, [signals]);

  const applyLive = useCallback((live: IntelligenceSignal[], scannedAt?: string) => {
    const only = live.filter((s) => !s.demo);
    if (only.length === 0) return false;
    setSignals(only);
    setLiveCount(only.length);
    if (scannedAt) setLastScanAt(scannedAt);
    setStatus("online");
    return true;
  }, []);

  const runScan = useCallback(
    async (signal?: AbortSignal, silent = false) => {
      setStatus("scanning");
      if (!silent) setScanMessage("Fetching South African news feeds…");
      try {
        const res = await fetchWithTimeout("/api/scan", { method: "POST" }, 55000, signal);
        const json = (await res.json()) as {
          lastScanAt?: string;
          added?: number;
          signals?: IntelligenceSignal[];
          errors?: { feed: string; error: string }[];
          error?: string;
          source?: string;
        };
        if (signal?.aborted) return;
        if (!res.ok) throw new Error(json.error ?? "Scan failed");
        const applied = applyLive(json.signals ?? [], json.lastScanAt);
        const live = json.signals?.filter((s) => !s.demo).length ?? json.added ?? 0;
        const failed = json.errors?.length ?? 0;
        if (applied || signalsRef.current.length > 0) {
          setStatus("online");
        } else {
          setStatus("degraded");
        }
        setScanMessage(
          live > 0
            ? `Loaded ${live} live articles${failed ? ` (${failed} feeds failed)` : ""}.`
            : signalsRef.current.length > 0
              ? "Scan found no new matching articles; showing the last saved feed."
              : "Scan finished but no matching live articles were found.",
        );
      } catch (error) {
        if (signal?.aborted) {
          if (signalsRef.current.length > 0) setStatus("online");
          return;
        }
        setStatus(signalsRef.current.length > 0 ? "online" : "degraded");
        setScanMessage(
          isAbortError(error)
            ? "Scan timed out. Showing the last saved feed — try Run New Scan again."
            : error instanceof Error
              ? error.message
              : "Scan failed",
        );
      } finally {
        if (!signal?.aborted) setBootDone(true);
      }
    },
    [applyLive],
  );

  const runNewScan = useCallback(async () => {
    await runScan();
  }, [runScan]);

  useEffect(() => {
    const ac = new AbortController();
    async function boot() {
      if (!hasSeed) {
        try {
          const res = await fetchWithTimeout("/api/intelligence?all=1", {}, 8000, ac.signal);
          const json = (await res.json()) as {
            data?: IntelligenceSignal[];
            lastScanAt?: string;
          };
          if (ac.signal.aborted) return;
          const live = (json.data ?? []).filter((s) => !s.demo);
          if (live.length > 0) {
            applyLive(live, json.lastScanAt);
            setScanMessage(null);
            setBootDone(true);
            if (isFresh(json.lastScanAt ?? "")) return;
          }
        } catch {
          if (ac.signal.aborted) return;
        }
      } else if (isFresh(initialLastScanAt)) {
        setBootDone(true);
        return;
      }
      if (!ac.signal.aborted) await runScan(ac.signal, hasSeed);
    }
    void boot();
    return () => ac.abort();
  }, [applyLive, hasSeed, initialLastScanAt, runScan]);

  const value = useMemo(
    () => ({
      period,
      setPeriod,
      collapsed,
      setCollapsed,
      mobileNav,
      setMobileNav,
      lastScanAt,
      scanStatus,
      signals,
      liveCount,
      scanMessage,
      bootDone,
      runNewScan,
    }),
    [
      period,
      collapsed,
      mobileNav,
      lastScanAt,
      scanStatus,
      signals,
      liveCount,
      scanMessage,
      bootDone,
      runNewScan,
    ],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAppState() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAppState must be used within AppProvider");
  return ctx;
}
