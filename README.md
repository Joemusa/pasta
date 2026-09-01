# SA Home Care Intelligence

AI-powered South African FMCG market intelligence for the **Home Care** category. Built for Unilever commercial, marketing and category teams.

The product answers:

> What changed in the South African Home Care market, why does it matter to Unilever, and where is the next opportunity to move the needle?

## Stack

- Next.js (App Router) · React · TypeScript · Tailwind CSS
- Recharts · Lucide
- Demo intelligence store today; Supabase schema ready in `supabase/schema.sql`

This frontend is new on `main`. Internal POS agents (Price, Promotion, Distribution, Commercial Brain) already exist on other `pasta` branches — Internal Analysis is the connection layer.

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

If the tab still refuses to connect:

1. Confirm you are in the repo root (the folder that contains `package.json`).
2. Confirm the terminal still shows the Next.js process — closing it stops the server.
3. Try [http://127.0.0.1:3000](http://127.0.0.1:3000).
4. If port 3000 is already taken, Next will print another port (for example `3001`) — use that URL instead.

## Architecture

```
External sources  →  Scanner / research agent  →  Normalisation
        →  Supabase (or demo store)  →  AI analysis  →  Dashboard
```

The browser never scrapes. Pages consume `intelligenceService` (`src/lib/intelligence/service.ts`). HTTP surface:

| Route | Purpose |
| --- | --- |
| `GET /api/intelligence` | Signals and overview |
| `POST /api/scan` | Run a scan |
| `POST /api/internal/query` | Internal agent query |
| `POST /api/ask` | Ask Intelligence |
| `GET /api/brief` | Weekly brief payload |

Demo records are labelled. Source buttons open the **publication homepage**, not invented article URLs. Financial impact is shown as **Requires Internal Validation** until POS is joined.

## Supabase

1. Apply `supabase/schema.sql`
2. Copy `.env.example` to `.env.local` and set the project URL and anon key

## Deploy

Vercel, from the repository root. No extra build command.
