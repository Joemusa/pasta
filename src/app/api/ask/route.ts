import { NextRequest, NextResponse } from "next/server";
import { askIntelligence } from "@/lib/intelligence/service";

export async function POST(request: NextRequest) {
  const body = (await request.json()) as { question?: string };
  if (!body.question?.trim()) {
    return NextResponse.json({ error: "question is required" }, { status: 400 });
  }
  return NextResponse.json({ data: askIntelligence(body.question), source: "demo" });
}
