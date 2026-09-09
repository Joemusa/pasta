import { NextResponse } from "next/server";
import { runAndPersistScan } from "@/lib/intelligence/scan-persist";

export const dynamic = "force-dynamic";
export const maxDuration = 60;
export const runtime = "nodejs";

export async function POST() {
  try {
    const result = await runAndPersistScan();
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Scan failed",
        source: "empty",
      },
      { status: 500 },
    );
  }
}
