"use client";

import { useAppState } from "@/components/providers";
import { getSources } from "@/lib/intelligence/service";
import { formatScanTime } from "@/lib/utils";

export default function SettingsPage() {
  const sources = getSources();
  const { liveCount, lastScanAt, scanStatus } = useAppState();

  return (
    <div className="mx-auto max-w-[800px] space-y-8">
      <div>
        <h1 className="text-[32px] font-semibold">Settings</h1>
        <p className="text-sm text-muted">Live news source settings.</p>
      </div>

      <section className="border border-rule bg-white p-5">
        <h2 className="font-serif text-xl">Data source</h2>
        <p className="mt-2 text-sm">
          Active mode: <strong>Live RSS scanner</strong>
        </p>
        <p className="mt-2 text-sm text-muted">
          The feed keeps only stories that can affect Unilever Home Care
          categories (laundry detergent and bars, dishwashing, toilet care,
          fabric conditioner, hard-surface cleaners). Fuel, SASSA, gold and
          general retailer headlines are dropped unless they name a Home Care
          brand or category.
        </p>
        <p className="mt-3 text-sm">
          Last scan: {formatScanTime(lastScanAt)} · Status: {scanStatus} · {liveCount} live articles
        </p>
      </section>

      <section className="border border-rule bg-white p-5">
        <h2 className="font-serif text-xl">External sources</h2>
        <p className="mt-1 text-sm text-muted">
          Publications the scanner reads. Each story links to the original article when the feed
          provides a URL.
        </p>
        <ul className="mt-4 divide-y divide-rule">
          {sources.map((s) => (
            <li key={s.id} className="flex items-center justify-between py-2 text-sm">
              <span>{s.name}</span>
              <a className="text-teal hover:underline" href={s.url} target="_blank" rel="noreferrer">
                {s.url.replace("https://", "")}
              </a>
            </li>
          ))}
        </ul>
      </section>

      <section className="border border-rule bg-white p-5">
        <h2 className="font-serif text-xl">Scan</h2>
        <p className="mt-2 text-sm text-muted">
          Use Run New Scan in the header to refresh headlines from the live feeds.
        </p>
      </section>
    </div>
  );
}
