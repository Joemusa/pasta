"use client";

import { Menu, RefreshCw, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formatScanTime } from "@/lib/utils";
import { useAppState } from "../providers";

export function Header() {
  const { lastScanAt, scanStatus, runNewScan, setMobileNav, liveCount } = useAppState();

  return (
    <header className="sticky top-0 z-20 flex items-center gap-4 border-b border-rule bg-paper/95 px-4 py-3 backdrop-blur sm:px-6">
      <button
        type="button"
        className="lg:hidden text-ink-text"
        aria-label="Open navigation"
        onClick={() => setMobileNav(true)}
      >
        <Menu size={20} />
      </button>
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-text">
          SA Home Care Intelligence
        </p>
        <p className="truncate text-xs text-muted">South African Home Care news for Unilever</p>
      </div>
      <div className="hidden items-center gap-4 md:flex">
        <div className="text-right">
          <p className="text-[11px] uppercase tracking-wider text-muted">Last scan</p>
          <p className="text-sm text-ink-text">{formatScanTime(lastScanAt)}</p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span
            className={
              scanStatus === "online"
                ? "h-1.5 w-1.5 rounded-full bg-low"
                : scanStatus === "scanning"
                  ? "h-1.5 w-1.5 rounded-full bg-medium"
                  : "h-1.5 w-1.5 rounded-full bg-high"
            }
          />
          <span className="text-muted">
            {scanStatus === "online"
              ? liveCount > 0
                ? `Live news · ${liveCount} articles`
                : "Ready"
              : scanStatus === "scanning"
                ? "Scanning sources…"
                : "Scan failed"}
          </span>
        </div>
      </div>
      <Button variant="primary" onClick={runNewScan} disabled={scanStatus === "scanning"}>
        <RefreshCw size={14} className={scanStatus === "scanning" ? "animate-spin" : undefined} />
        Run New Scan
      </Button>
      <div className="hidden h-9 items-center gap-2 border border-rule bg-white px-2 sm:flex">
        <span className="flex h-6 w-6 items-center justify-center bg-ink text-[10px] text-white">
          <User size={12} />
        </span>
        <span className="pr-1 text-xs text-ink-text">Category · Unilever</span>
      </div>
    </header>
  );
}
