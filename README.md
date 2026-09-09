# SA Home Care Intelligence

AI-powered South African FMCG **Home Care news** for Unilever commercial, marketing and category teams.

The app shows sourced headlines. A product note is added only when a story names a Unilever brand (OMO, Surf, Skip, Sunlight, Domestos, Comfort, Handy Andy, Jik) or a mapped competitor (MAQ, Ariel, Harpic, Sta-soft, Britelite, Finish).

Pages: **Intelligence Feed**, **Macro trends**, **Settings**.

## Stack

- Next.js (App Router) · React · TypeScript · Tailwind CSS
- Recharts · Lucide
- Demo intelligence store today; Supabase schema ready in `supabase/schema.sql`

This frontend is new on `main`.

## Run locally

This app only answers on **the computer where `npm run dev` is running**. Opening `http://localhost:3000` in Chrome on your laptop will show **ERR_CONNECTION_REFUSED** if the server is running in a Cloud Agent (or any other machine).

From your own machine, in a terminal:

```bash
git fetch origin
git checkout cursor/sa-home-care-intelligence-4bca
npm install
npm run dev
```

Wait until the terminal prints `Local: http://localhost:3000` (or `Ready`). **Leave that terminal open**, then open [http://localhost:3000](http://localhost:3000) in a browser on the same computer.

## Live news

The dashboard does not scrape websites in the browser. Click **Run New Scan** (or wait for the 6-hour cron) to fetch:

- Google News ZA RSS
- GDELT document search (South Africa)
- Takealot promotions
- HelloPeter Home Care complaints
- X (Twitter) public Home Care conversations, when `X_BEARER_TOKEN` is set

X posts are labelled as social-media opinion, not verified facts. Configure the agent on **Settings**. Low-relevance posts are dropped before they reach the feed.

Set a server-side bearer token from the X developer portal (API v2 recent search). Never expose it in `NEXT_PUBLIC_` variables.

- Headlines show the publisher and a real source URL.
- A product-impact line appears when a Unilever brand or a mapped competitor is named.
- A last-good snapshot ships in `src/data/bundled-signals.json` so Vercel cold starts are not blank.
- Live scans persist across serverless instances: in-memory on the instance that scanned, Next.js Data Cache (shared on Vercel), and — when configured — the `intelligence_feed` Supabase row. `/tmp` is only a same-instance backup.
- Refresh that snapshot with `npm run refresh-bundle`.
- Demo headlines are not shown.

If the tab still refuses to connect:

1. Confirm you are in the repo root (the folder that contains `package.json`).
2. Confirm the terminal still shows the Next.js process — closing it stops the server.
3. Try [http://127.0.0.1:3000](http://127.0.0.1:3000).
4. If port 3000 is already taken, Next will print another port (for example `3001`) — use that URL instead.

## Architecture

```
External sources  →  Scanner  →  Dashboard (headline + source + optional product impact)
```

The browser never scrapes. Pages consume `intelligenceService` (`src/lib/intelligence/service.ts`). HTTP surface:

| Route | Purpose |
| --- | --- |
| `GET /api/intelligence` | Signals |
| `POST /api/scan` | Run a scan (RSS, GDELT, Takealot, HelloPeter, X) |
| `GET /api/cron/scan` | Same scan, used by the existing 6-hour Vercel cron |
| `GET`/`POST /api/x-config` | Enable X, max posts, lookback, relevance threshold (no token) |

Demo records are labelled. Source buttons open the original article URL when the feed provided one.

## Supabase

1. Apply `supabase/schema.sql` (includes `intelligence_feed` for the shared live snapshot)
2. Copy `.env.example` to `.env.local` and set the project URL, anon key, and **`SUPABASE_SERVICE_ROLE_KEY`** on Vercel so scans written on one instance are readable on the next
3. Without the service role, the feed still stays populated from the bundled snapshot and the shared Data Cache after a scan on that deployment

## Deploy

Vercel, from the repository root. No extra build command.
