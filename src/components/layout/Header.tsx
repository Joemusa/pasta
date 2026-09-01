"use client";

import { Bell, Menu, RefreshCw, User } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { SeverityDot } from "@/components/ui/severity";
import { getNotifications } from "@/lib/intelligence/service";
import { formatScanTime } from "@/lib/utils";
import { useAppState } from "../providers";

export function Header() {
  const { lastScanAt, scanStatus, runNewScan, setMobileNav } = useAppState();
  const [open, setOpen] = useState(false);
  const notes = getNotifications();

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
        <p className="truncate text-xs text-muted">
          South African Home Care Market & Competitive Intelligence
        </p>
      </div>
      <div className="hidden items-center gap-4 md:flex">
        <div className="text-right">
          <p className="text-[11px] uppercase tracking-wider text-muted">Last scan</p>
          <p className="text-sm text-ink-text">{formatScanTime(lastScanAt, new Date("2026-09-01T12:00:00+02:00"))}</p>
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
              ? "Intelligence System Online"
              : scanStatus === "scanning"
                ? "Scanning sources…"
                : "System degraded"}
          </span>
        </div>
      </div>
      <Button
        variant="primary"
        onClick={runNewScan}
        disabled={scanStatus === "scanning"}
      >
        <RefreshCw size={14} className={scanStatus === "scanning" ? "animate-spin" : undefined} />
        Run New Scan
      </Button>
      <div className="relative">
        <button
          type="button"
          className="relative flex h-9 w-9 items-center justify-center border border-rule bg-white text-ink-text"
          aria-label="Notifications"
          onClick={() => setOpen((o) => !o)}
        >
          <Bell size={16} />
          <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-high" />
        </button>
        {open ? (
          <div className="absolute right-0 mt-2 w-72 border border-rule bg-white p-3 shadow-none">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted">
              Alerts
            </p>
            <ul className="space-y-2">
              {notes.map((n) => (
                <li key={n.id} className="border-b border-rule pb-2 last:border-0 last:pb-0">
                  <p className="text-sm text-ink-text">{n.title}</p>
                  <div className="mt-1 flex items-center justify-between">
                    <SeverityDot level={n.severity} />
                    <span className="text-[11px] text-muted">{n.time}</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
      <div className="hidden h-9 items-center gap-2 border border-rule bg-white px-2 sm:flex">
        <span className="flex h-6 w-6 items-center justify-center bg-ink text-[10px] text-white">
          <User size={12} />
        </span>
        <span className="pr-1 text-xs text-ink-text">Category · Unilever</span>
      </div>
    </header>
  );
}
