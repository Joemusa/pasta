import { revalidateTag, unstable_cache } from "next/cache";
import { persistLocalFeed, rememberFeed, resolveFeed, resolveLiveFeed, readMemoryFeed } from "./feed-store";
import { readDurableSnapshot, writeDurableSnapshot } from "./durable-store";
import { readBundledCache, readRuntimeCache, writeLiveCache, type LiveCache } from "./live-store";

export const FEED_CACHE_TAG = "sa-home-care-feed";

const liveReaders = {
  readDurable: readDurableSnapshot,
  readRuntime: readRuntimeCache,
};

const readCachedLiveFeed = unstable_cache(
  async () => {
    const live = await resolveLiveFeed(liveReaders);
    return live ?? { lastScanAt: "", signals: [] as LiveCache["signals"] };
  },
  [FEED_CACHE_TAG],
  { tags: [FEED_CACHE_TAG], revalidate: 6 * 60 * 60 },
);

/**
 * Latest Home Care feed for any serverless instance.
 * Order: in-memory → Supabase snapshot → shared Data Cache → /tmp → bundled JSON.
 */
export async function loadSharedFeed(): Promise<LiveCache> {
  const memory = readMemoryFeed();
  if (memory) return memory;

  try {
    const durable = await readDurableSnapshot();
    if (durable?.signals.length) {
      rememberFeed(durable);
      return durable;
    }
  } catch {
    // Supabase is optional.
  }

  try {
    const cached = await readCachedLiveFeed();
    if (cached.signals.length > 0) {
      rememberFeed(cached);
      return cached;
    }
  } catch {
    // Data Cache is unavailable in some test/runtime contexts.
  }

  return resolveFeed({
    readRuntime: readRuntimeCache,
    readBundled: readBundledCache,
  });
}

export async function persistSharedFeed(cache: LiveCache): Promise<LiveCache> {
  const stored = await persistLocalFeed(cache, {
    writeRuntime: writeLiveCache,
    writeDurable: writeDurableSnapshot,
  });
  try {
    revalidateTag(FEED_CACHE_TAG, "max");
    await readCachedLiveFeed();
  } catch {
    // Tag revalidation is best-effort outside Vercel.
  }
  return stored;
}
