"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { IntelligenceSignal, PeriodDays, ScanStatus } from "@/lib/types";
import { getScanMeta } from "@/lib/intelligence/service";

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
  runNewScan: () => Promise<void>;
};

const Ctx = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const meta = getScanMeta();
  const [period, setPeriod] = useState<PeriodDays>(14);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  const [lastScanAt, setLastScanAt] = useState(meta.lastScanAt);
  const [scanStatus, setStatus] = useState<ScanStatus>(meta.scanStatus);
  const [signals, setSignals] = useState<IntelligenceSignal[]>([]);
  const [liveCount, setLiveCount] = useState(0);
  const [scanMessage, setScanMessage] = useState<string | null>(null);

  const runNewScan = useCallback(async () => {
    setStatus("scanning");
    setScanMessage("Fetching South African news feeds…");
    try {
      const res = await fetch("/api/scan", { method: "POST" });
      const json = (await res.json()) as {
        lastScanAt?: string;
        added?: number;
        signals?: IntelligenceSignal[];
        source?: string;
        errors?: { feed: string; error: string }[];
        error?: string;
      };
      if (!res.ok) throw new Error(json.error ?? "Scan failed");
      if (json.lastScanAt) setLastScanAt(json.lastScanAt);
      if (json.signals) setSignals(json.signals);
      const live = json.signals?.filter((s) => !s.demo).length ?? json.added ?? 0;
      setLiveCount(live);
      const failed = json.errors?.length ?? 0;
      setScanMessage(
        live > 0
          ? `Ingested ${live} live articles${failed ? ` (${failed} feeds failed)` : ""}.`
          : "Scan finished but no live articles matched. Demo records remain.",
      );
      setStatus(live > 0 ? "online" : "degraded");
    } catch (error) {
      setStatus("degraded");
      setScanMessage(error instanceof Error ? error.message : "Scan failed");
    }
  }, []);

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
