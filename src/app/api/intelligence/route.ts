import { NextRequest, NextResponse } from "next/server";
import { getOverview, getSignals } from "@/lib/intelligence/service";
import type { PeriodDays, SignalType } from "@/lib/types";

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const period = Number(searchParams.get("period") ?? 14) as PeriodDays;
  const view = searchParams.get("view");
  if (view === "overview") {
    return NextResponse.json({ data: getOverview(period), source: "demo" });
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
    source: "demo",
  });
}
