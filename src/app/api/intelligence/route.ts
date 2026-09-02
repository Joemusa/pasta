import { NextRequest, NextResponse } from "next/server";
import { getScanMeta, getSignals, hydrateLiveSignals } from "@/lib/intelligence/service";
import { readLiveCache } from "@/lib/intelligence/live-store";
import type { PeriodDays, SignalType } from "@/lib/types";

function hydrate() {
  try {
    const cache = readLiveCache();
    hydrateLiveSignals(cache.signals, cache.lastScanAt);
  } catch {
    // ignore
  }
}

export async function GET(request: NextRequest) {
  hydrate();
  const { searchParams } = request.nextUrl;
  const period = Number(searchParams.get("period") ?? 14) as PeriodDays;
  const meta = getScanMeta();
  const live = getSignals({ period: 30, type: "all" }).filter((s) => !s.demo);
  const payload = {
    lastScanAt: meta.lastScanAt,
    source: live.length > 0 ? "live" : "empty",
    liveCount: live.length,
  };
  if (searchParams.get("all") === "1") {
    return NextResponse.json({ ...payload, data: live });
  }
  const type = (searchParams.get("type") ?? "all") as SignalType | "all";
  return NextResponse.json({
    ...payload,
    data: getSignals({
      period: period === 7 || period === 30 ? period : 14,
      type,
      search: searchParams.get("search") ?? "",
      category: searchParams.get("category") ?? "",
      brand: searchParams.get("brand") ?? "",
      retailer: searchParams.get("retailer") ?? "",
      province: searchParams.get("province") ?? "",
    }).filter((s) => !s.demo),
  });
}
