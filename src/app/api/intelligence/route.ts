import { NextRequest, NextResponse } from "next/server";
import { getScanMeta, getSignals, hydrateLiveSignals } from "@/lib/intelligence/service";
import { loadSharedFeed } from "@/lib/intelligence/shared-feed";
import { durableReadConfigured, durableWriteConfigured } from "@/lib/intelligence/durable-store";
import type { PeriodDays, SignalType } from "@/lib/types";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

async function hydrate() {
  const cache = await loadSharedFeed();
  hydrateLiveSignals(cache.signals, cache.lastScanAt);
  return cache;
}

export async function GET(request: NextRequest) {
  const cache = await hydrate();
  const { searchParams } = request.nextUrl;
  const period = Number(searchParams.get("period") ?? 14) as PeriodDays;
  const meta = getScanMeta();
  const live = getSignals({ period: 90, type: "all" }).filter((s) => !s.demo);
  const payload = {
    lastScanAt: meta.lastScanAt || cache.lastScanAt,
    source: live.length > 0 ? "live" : "empty",
    liveCount: live.length,
    durableRead: durableReadConfigured(),
    durableWrite: durableWriteConfigured(),
  };
  if (searchParams.get("all") === "1") {
    return NextResponse.json({ ...payload, data: live });
  }
  const type = (searchParams.get("type") ?? "all") as SignalType | "all";
  return NextResponse.json({
    ...payload,
    data: getSignals({
      period: period === 7 || period === 30 || period === 90 ? period : 14,
      type,
      search: searchParams.get("search") ?? "",
      category: searchParams.get("category") ?? "",
      brand: searchParams.get("brand") ?? "",
      retailer: searchParams.get("retailer") ?? "",
      province: searchParams.get("province") ?? "",
    }).filter((s) => !s.demo),
  });
}
