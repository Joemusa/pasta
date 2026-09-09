"use server";

import { revalidatePath } from "next/cache";
import { writeXSettings } from "@/lib/intelligence/x-config";

export type XSaveState = { ok: boolean; message: string } | null;

export async function saveXSettingsAction(
  _prev: XSaveState,
  formData: FormData,
): Promise<XSaveState> {
  try {
    writeXSettings({
      enabled: formData.get("enabled") === "on",
      maxPosts: Number(formData.get("maxPosts")),
      relevanceThreshold: Number(formData.get("relevanceThreshold")),
      lookbackHours: Number(formData.get("lookbackHours")),
      extraQuery: String(formData.get("extraQuery") ?? ""),
    });
    revalidatePath("/settings");
    return { ok: true, message: "X agent settings saved. They apply on the next scan." };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "Save failed",
    };
  }
}
