import { NextResponse } from "next/server";
import { runScan } from "@/lib/intelligence/service";

export async function POST() {
  const result = runScan();
  return NextResponse.json({
    lastScanAt: result.lastScanAt,
    added: result.added,
    source: "demo",
  });
}
