import { NextRequest, NextResponse } from "next/server";
import { runAndPersistScan } from "@/lib/intelligence/scan-persist";

export const maxDuration = 60;
export const runtime = "nodejs";

function authorized(request: NextRequest): boolean {
  const secret = process.env.CRON_SECRET;
  if (!secret) return true;
  const header = request.headers.get("authorization");
  return header === `Bearer ${secret}`;
}

async function scan(request: NextRequest) {
  if (!authorized(request)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  try {
    const result = await runAndPersistScan();
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Scan failed" },
      { status: 500 },
    );
  }
}

export async function GET(request: NextRequest) {
  return scan(request);
}

export async function POST(request: NextRequest) {
  return scan(request);
}
