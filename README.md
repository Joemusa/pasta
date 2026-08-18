# pasta

A small pasta trattoria web app used to demonstrate a working development environment end to end.

## Stack

- Node.js (>= 20) + [Express](https://expressjs.com/)
- Static frontend (vanilla HTML/CSS/JS) served from `public/`
- Tests via the built-in Node test runner

## Getting started

```bash
npm ci        # install dependencies
npm start     # start the server on http://localhost:3000
npm run dev   # start with auto-reload (node --watch)
npm test      # run the test suite
npm run lint  # syntax-check the source files
```

## API

- `GET /api/health` — health check.
- `GET /api/menu` — list the pasta menu with formatted prices.
- `POST /api/orders` — place an order. Body: `{ "dishId": "penne-arrabbiata", "quantity": 2 }`.

## Project layout

```
src/        Express app and server entrypoint
public/     Static frontend (HTML/CSS/JS)
test/       Node test-runner suite
```

## Cloud Agent environment

The Cloud Agent development environment is configured in `.cursor/environment.json`:
it installs dependencies with `npm ci` and runs the dev server as a named terminal.
