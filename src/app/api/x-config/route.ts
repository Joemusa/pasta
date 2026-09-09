import { NextRequest, NextResponse } from "next/server";
import { publicXStatus, writeXSettings, type XAgentSettings } from "@/lib/intelligence/x-config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json(publicXStatus());
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as Partial<XAgentSettings>;
    const saved = writeXSettings({
      enabled: body.enabled,
      maxPosts: body.maxPosts,
      relevanceThreshold: body.relevanceThreshold,
      lookbackHours: body.lookbackHours,
      extraQuery: body.extraQuery,
    });
    return NextResponse.json({ ...publicXStatus(), ...saved });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Could not save X settings" },
      { status: 400 },
    );
  }
}
