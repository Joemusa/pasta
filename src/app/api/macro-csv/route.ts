import { NextResponse } from "next/server";
import { loadMacroSnapshot, macroCsv, macroCsvFilename } from "@/lib/intelligence/macro";

export const maxDuration = 60;
export const dynamic = "force-dynamic";

export async function GET() {
  const snapshot = await loadMacroSnapshot();
  const csv = macroCsv(snapshot);
  return new NextResponse(csv, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${macroCsvFilename()}"`,
      "Cache-Control": "no-store",
    },
  });
}
