import { NextResponse } from "next/server";
import { getMacro, getOpportunities, getOverview, getSignals } from "@/lib/intelligence/service";

export async function GET() {
  const overview = getOverview(14);
  return NextResponse.json({
    source: "demo",
    data: {
      kpis: overview.kpis,
      opportunities: getOpportunities().slice(0, 3),
      threats: overview.threats.slice(0, 3),
      competitorMoves: getSignals({ period: 14, type: "competitor" }),
      retailerMoves: getSignals({ period: 14, type: "retailer" }),
      macro: getMacro(),
    },
  });
}
