import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import type { LiveCache } from "./live-store";
import type { IntelligenceSignal } from "../types";

const SNAPSHOT_ID = "latest";

function adminClient(): SupabaseClient | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_SECRET_KEY;
  if (!url || !key) return null;
  return createClient(url, key, { auth: { persistSession: false } });
}

function readClient(): SupabaseClient | null {
  const admin = adminClient();
  if (admin) return admin;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) return null;
  return createClient(url, key, { auth: { persistSession: false } });
}

function asSignals(value: unknown): IntelligenceSignal[] {
  if (Array.isArray(value)) return value as IntelligenceSignal[];
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value) as unknown;
      return Array.isArray(parsed) ? (parsed as IntelligenceSignal[]) : [];
    } catch {
      return [];
    }
  }
  return [];
}

export function snapshotFromRow(
  row: { last_scan_at?: string | null; signals?: unknown } | null,
): LiveCache | null {
  const signals = asSignals(row?.signals).filter((s) => s && !s.demo);
  if (signals.length === 0) return null;
  return { lastScanAt: row?.last_scan_at ?? "", signals };
}

export function durableReadConfigured(): boolean {
  return Boolean(readClient());
}

export function durableWriteConfigured(): boolean {
  return Boolean(adminClient());
}

export function durableStoreConfigured(): boolean {
  return durableReadConfigured();
}

export async function readDurableSnapshot(): Promise<LiveCache | null> {
  const supabase = readClient();
  if (!supabase) return null;
  const { data, error } = await supabase
    .from("intelligence_feed")
    .select("last_scan_at, signals")
    .eq("id", SNAPSHOT_ID)
    .maybeSingle();
  if (error || !data) return null;
  return snapshotFromRow(data);
}

export async function writeDurableSnapshot(cache: LiveCache): Promise<void> {
  const supabase = adminClient();
  if (!supabase || cache.signals.length === 0) return;
  const { error } = await supabase.from("intelligence_feed").upsert({
    id: SNAPSHOT_ID,
    last_scan_at: cache.lastScanAt || new Date().toISOString(),
    signals: cache.signals.filter((s) => s && !s.demo),
    updated_at: new Date().toISOString(),
  });
  if (error) throw error;
}
