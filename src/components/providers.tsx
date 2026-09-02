"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
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

let bootStarted = false;

export function AppProvider({ children }: { children: ReactNode }) {
  const [period, setPeriod] = useState<PeriodDays>(14);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [lastScanAt, setLastScanAt] = useState("");
  const [scanStatus, setStatus] = useState<ScanStatus>("scanning");
  const [signals, setSignals] = useState<IntelligenceSignal[]>([]);
  const [liveCount, setLiveCount] = useState(0);
  const [scanMessage, setScanMessage] = useState<string | null>("Loading live news…");
  const [bootDone, setBootDone] = useState(false);

  const applyLive = useCallback((live: IntelligenceSignal[], scannedAt?: string) => {
    const only = live.filter((s) => !s.demo);
    setSignals(only);
    setLiveCount(only.length);
    if (scannedAt) setLastScanAt(scannedAt);
    setStatus(only.length > 0 ? "online" : "degraded");
  }, []);

  const runNewScan = useCallback(async () => {
    setStatus("scanning");
    setScanMessage("Fetching South African news feeds…");
    try {
      const res = await fetch("/api/scan", { method: "POST" });
      const json = (await res.json()) as {
        lastScanAt?: string;
        added?: number;
        signals?: IntelligenceSignal[];
        errors?: { feed: string; error: string }[];
        error?: string;
      };
      if (!res.ok) throw new Error(json.error ?? "Scan failed");
      applyLive(json.signals ?? [], json.lastScanAt);
      const live = json.signals?.filter((s) => !s.demo).length ?? json.added ?? 0;
      const failed = json.errors?.length ?? 0;
      setScanMessage(
        live > 0
          ? `Loaded ${live} live articles${failed ? ` (${failed} feeds failed)` : ""}.`
          : "Scan finished but no matching live articles were found.",
      );
    } catch (error) {
      setStatus("degraded");
      setScanMessage(error instanceof Error ? error.message : "Scan failed");
    } finally {
      setBootDone(true);
    }
  }, [applyLive]);

  useEffect(() => {
    if (bootStarted) return;
    bootStarted = true;
    let cancelled = false;
    async function boot() {
      try {
        const res = await fetch("/api/intelligence?all=1");
        const json = (await res.json()) as {
          data?: IntelligenceSignal[];
          lastScanAt?: string;
          liveCount?: number;
        };
        if (cancelled) return;
        const live = (json.data ?? []).filter((s) => !s.demo);
        if (live.length > 0) {
          applyLive(live, json.lastScanAt);
          setScanMessage(null);
          setBootDone(true);
          return;
        }
        await runNewScan();
      } catch {
        if (!cancelled) await runNewScan();
      }
    }
    void boot();
    return () => {
      cancelled = true;
    };
  }, [applyLive, runNewScan]);

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
