import { NextRequest, NextResponse } from "next/server";
import { loadMacroSnapshot } from "@/lib/intelligence/macro";

export const maxDuration = 60;
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const refresh = request.nextUrl.searchParams.get("refresh") === "1";
    const snapshot = await loadMacroSnapshot({ refresh });
    return NextResponse.json(snapshot, {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    return NextResponse.json(
      {
        fetchedAt: new Date().toISOString(),
        points: [],
        latest: {
          inflationPeriod: null,
          inflation: null,
          inflationYearAgo: null,
          policyPeriod: null,
          policyRate: null,
          policyYearAgo: null,
          realRate: null,
        },
        commentary: {
          headline: "Macro series could not be loaded.",
          facts: [],
          behaviours: [],
        },
        sources: [],
        errors: [error instanceof Error ? error.message : "Macro fetch failed"],
      },
      { status: 500 },
    );
  }
}
