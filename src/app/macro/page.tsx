import { MacroSheet } from "@/components/macro/MacroSheet";
import { loadMacroSnapshot } from "@/lib/intelligence/macro";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

export default async function MacroPage() {
  const snapshot = await loadMacroSnapshot();
  return <MacroSheet initial={snapshot} />;
}
