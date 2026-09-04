import { NextRequest, NextResponse } from "next/server";
import { getSignals, hydrateLiveSignals } from "@/lib/intelligence/service";
import { readLiveCache } from "@/lib/intelligence/live-store";
import { newsCsvFilename, newsSignalsToCsv } from "@/lib/news-csv";
import type { PeriodDays } from "@/lib/types";

export const maxDuration = 30;

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
  const periodRaw = Number(request.nextUrl.searchParams.get("period") ?? 90);
  const period = (periodRaw === 7 || periodRaw === 14 || periodRaw === 30 || periodRaw === 90
    ? periodRaw
    : 90) as PeriodDays;
  const stories = getSignals({ period, type: "all" }).filter((s) => !s.demo);
  const csv = newsSignalsToCsv(stories);
  return new NextResponse(csv, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${newsCsvFilename()}"`,
      "Cache-Control": "no-store",
    },
  });
}
