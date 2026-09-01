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

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

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
