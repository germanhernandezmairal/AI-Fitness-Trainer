# AI Fitness Trainer — Frontend

Next.js (App Router) app for the AI Fitness Trainer: register/login, upload a squat
video, poll for and view AI-powered form feedback, browse attempt history, and delete
an attempt. Talks directly to the FastAPI backend over CORS.

## Setup

```bash
cd frontend
cp .env.local.example .env.local
npm install
```

## Run

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Requires the backend (and, for a
real upload to resolve, the CV service) running — see `backend/README.md`'s "Run the
whole loop locally" section.

## Test

Unit tests (Vitest + React Testing Library):

```bash
npm test
```

End-to-end tests (Playwright) — a separate command, since it drives a real browser
against a running app and backend:

```bash
npx playwright test
```

The e2e suite starts its own `next dev` server automatically, but expects the backend
and CV service (fake or real) to already be running locally on `localhost:8000` /
`localhost:9000` — see `backend/README.md`'s "Run the whole loop locally" section.

## Lint / build

```bash
npm run lint
npm run build
```
