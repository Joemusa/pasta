import { NextRequest, NextResponse } from "next/server";
import { runInternalQuery } from "@/lib/intelligence/service";

export async function POST(request: NextRequest) {
  const body = (await request.json()) as {
    agent?: string;
    query?: string;
    signalId?: string | null;
  };
  if (!body.query || !body.agent) {
    return NextResponse.json({ error: "agent and query are required" }, { status: 400 });
  }
  return NextResponse.json({
    data: runInternalQuery({
      agent: body.agent,
      query: body.query,
      signalId: body.signalId ?? null,
    }),
    source: "demo",
  });
}
