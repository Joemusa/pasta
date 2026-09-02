import { NextRequest, NextResponse } from "next/server";
import {
  getOverview,
  getSignals,
  getAllSignals,
  hydrateLiveSignals,
} from "@/lib/intelligence/service";
import { readLiveSignals } from "@/lib/intelligence/live-store";
import type { PeriodDays, SignalType } from "@/lib/types";

function hydrate() {
  try {
    hydrateLiveSignals(readLiveSignals());
  } catch {
    // ignore
  }
}

export async function GET(request: NextRequest) {
  hydrate();
  const { searchParams } = request.nextUrl;
  const period = Number(searchParams.get("period") ?? 14) as PeriodDays;
  const view = searchParams.get("view");
  const liveCount = getAllSignals().filter((s) => !s.demo).length;
  const source = liveCount > 0 ? "live" : "demo";
  if (view === "overview") {
    return NextResponse.json({ data: getOverview(period), source, liveCount });
  }
  if (searchParams.get("all") === "1") {
    return NextResponse.json({ data: getAllSignals(), source, liveCount });
  }
  const type = (searchParams.get("type") ?? "all") as SignalType | "all";
  return NextResponse.json({
    data: getSignals({
      period: period === 7 || period === 30 ? period : 14,
      type,
      search: searchParams.get("search") ?? "",
      category: searchParams.get("category") ?? "",
      brand: searchParams.get("brand") ?? "",
      retailer: searchParams.get("retailer") ?? "",
      province: searchParams.get("province") ?? "",
    }),
    source,
    liveCount,
  });
}
