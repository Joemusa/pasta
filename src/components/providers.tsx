"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { PeriodDays, ScanStatus } from "@/lib/types";
import { getScanMeta, runScan as runScanService, setScanStatus } from "@/lib/intelligence/service";

type AppState = {
  period: PeriodDays;
  setPeriod: (p: PeriodDays) => void;
  collapsed: boolean;
  setCollapsed: (v: boolean | ((c: boolean) => boolean)) => void;
  mobileNav: boolean;
  setMobileNav: (v: boolean) => void;
  lastScanAt: string;
  scanStatus: ScanStatus;
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

  const runNewScan = useCallback(async () => {
    setStatus("scanning");
    setScanStatus("scanning");
    await new Promise((r) => setTimeout(r, 900));
    const result = runScanService();
    setLastScanAt(result.lastScanAt);
    setStatus("online");
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
      runNewScan,
    }),
    [period, collapsed, mobileNav, lastScanAt, scanStatus, runNewScan],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAppState() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAppState must be used within AppProvider");
  return ctx;
}
