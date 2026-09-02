"use client";

import { getSources } from "@/lib/intelligence/service";
import { isSupabaseConfigured } from "@/lib/supabase/client";

export default function SettingsPage() {
  const sources = getSources();
  const live = isSupabaseConfigured();

  return (
    <div className="mx-auto max-w-[800px] space-y-8">
      <div>
        <h1 className="text-[32px] font-semibold">Settings</h1>
        <p className="text-sm text-muted">Configuration and data-source settings.</p>
      </div>

      <section className="border border-rule bg-white p-5">
        <h2 className="font-serif text-xl">Data source</h2>
        <p className="mt-2 text-sm">
          Active mode:{" "}
          <strong>
            {live ? "Supabase configured" : "News scanner + demo store"}
          </strong>
        </p>
        <p className="mt-2 text-sm text-muted">
          Click <strong>Run New Scan</strong> in the header to pull live South African RSS
          (Google News ZA, Moneyweb, IOL, The Citizen). The dashboard does not scrape pages
          in the browser. FACT is the headline the source published; interpretation is labelled
          separately and is not a source claim. Supabase is optional later, to persist those
          rows across deploys.
        </p>
      </section>

      <section className="border border-rule bg-white p-5">
        <h2 className="font-serif text-xl">External sources</h2>
        <p className="mt-1 text-sm text-muted">
          South African publications the scanner should prioritise. Demo records currently cite these
          homepages — never fabricated article URLs.
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
          Last demo scan: 1 September 2026, 08:42 SAST. Use Run New Scan in the header to append a
          new Pick n Pay / MAQ leaflet signal.
        </p>
      </section>
    </div>
  );
}
