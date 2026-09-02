# SA Home Care Intelligence

AI-powered South African FMCG **Home Care news** for Unilever commercial, marketing and category teams.

The app shows sourced headlines. A product note is added only when a story names a Unilever brand (OMO, Surf, Skip, Sunlight, Domestos, Comfort, Handy Andy, Jik) or a mapped competitor (MAQ, Ariel, Harpic, Sta-soft, Britelite, Finish).

Pages: **Home**, **Intelligence Feed**, **Settings**.

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

The dashboard does not scrape websites in the browser. Click **Run New Scan** to fetch public RSS feeds (Google News ZA, Moneyweb, IOL, The Citizen) on the server.

- Headlines show the publisher and a real source URL.
- A product-impact line appears only when a Unilever brand or a direct competitor is named.
- Home Care brand articles are uncommon; retailer and macro stories (Shoprite, fuel, SASSA) are the usual live hits, shown without extra commentary unless a product is named.
- Demo cards remain so the product still has category examples when news is thin.
- Supabase is optional later, to persist rows across deploys. You do not need it to run a live scan.

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
| `POST /api/scan` | Run a scan |

Demo records are labelled. Source buttons open the original article URL when the feed provided one.

## Supabase

1. Apply `supabase/schema.sql`
2. Copy `.env.example` to `.env.local` and set the project URL and anon key

## Deploy

Vercel, from the repository root. No extra build command.
