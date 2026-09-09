import type { LiveCache } from "./live-store";

export type FeedOrigin = "memory" | "durable" | "runtime" | "bundled";

export type ResolvedFeed = LiveCache & { origin: FeedOrigin };

export type FeedReaders = {
  readDurable?: () => Promise<LiveCache | null>;
  readRuntime?: () => LiveCache | null | Promise<LiveCache | null>;
  readBundled?: () => LiveCache | null;
};

export type FeedWriters = {
  writeRuntime?: (cache: LiveCache) => void | Promise<void>;
  writeDurable?: (cache: LiveCache) => Promise<void>;
};

let memory: LiveCache | null = null;

export function liveOnly(cache: LiveCache | null | undefined): LiveCache | null {
  if (!cache) return null;
  const signals = cache.signals.filter((s) => s && !s.demo);
  if (signals.length === 0) return null;
  return { lastScanAt: cache.lastScanAt ?? "", signals };
}

export function rememberFeed(cache: LiveCache) {
  memory = liveOnly(cache);
}

export function readMemoryFeed(): LiveCache | null {
  return liveOnly(memory);
}

export function clearMemoryFeed() {
  memory = null;
}

/**
 * Live layers only (memory → durable → /tmp). Never the shipped snapshot.
 * Used to fill the shared Next.js Data Cache after a scan.
 */
export async function resolveLiveFeed(readers: FeedReaders = {}): Promise<LiveCache | null> {
  const fromMemory = readMemoryFeed();
  if (fromMemory) return fromMemory;

  if (readers.readDurable) {
    try {
      const durable = liveOnly(await readers.readDurable());
      if (durable) {
        rememberFeed(durable);
        return durable;
      }
    } catch {
      // Durable is optional.
    }
  }

  if (readers.readRuntime) {
    try {
      const runtime = liveOnly(await readers.readRuntime());
      if (runtime) {
        rememberFeed(runtime);
        return runtime;
      }
    } catch {
      // /tmp is instance-local and may be missing.
    }
  }

  return null;
}

export async function resolveFeed(readers: FeedReaders = {}): Promise<ResolvedFeed> {
  const usingDefaults = !readers.readDurable && !readers.readRuntime && !readers.readBundled;
  if (usingDefaults) {
    const { readRuntimeCache, readBundledCache } = await import("./live-store");
    return resolveFeed({
      readRuntime: readRuntimeCache,
      readBundled: readBundledCache,
    });
  }

  const fromMemory = readMemoryFeed();
  if (fromMemory) return { ...fromMemory, origin: "memory" };

  if (readers.readDurable) {
    try {
      const durable = liveOnly(await readers.readDurable());
      if (durable) {
        rememberFeed(durable);
        return { ...durable, origin: "durable" };
      }
    } catch {
      // Durable is optional.
    }
  }

  if (readers.readRuntime) {
    try {
      const runtime = liveOnly(await readers.readRuntime());
      if (runtime) {
        rememberFeed(runtime);
        return { ...runtime, origin: "runtime" };
      }
    } catch {
      // Runtime file may be missing.
    }
  }

  const bundled = liveOnly(readers.readBundled?.() ?? null);
  if (bundled) return { ...bundled, origin: "bundled" };
  return { lastScanAt: "", signals: [], origin: "bundled" };
}

export async function persistLocalFeed(
  cache: LiveCache,
  writers: FeedWriters = {},
): Promise<LiveCache> {
  const next = liveOnly(cache) ?? { lastScanAt: cache.lastScanAt ?? "", signals: [] };
  rememberFeed(next);
  try {
    if (writers.writeRuntime) {
      await writers.writeRuntime(next);
    } else {
      const { writeLiveCache } = await import("./live-store");
      writeLiveCache(next);
    }
  } catch {
    // /tmp may be missing in some hosts.
  }
  if (writers.writeDurable && next.signals.length > 0) {
    try {
      await writers.writeDurable(next);
    } catch {
      // Durable is optional.
    }
  }
  return next;
}
