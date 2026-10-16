# Break the Gate

A web game where an AI gate decides if a shell command is safe for a coding agent to run, and players try to trick it into saying yes. Commands are text only. Nothing is ever executed.

Private repo. See `docs/PRD.md` (what), `docs/ARCHITECTURE.md` (how and why), `docs/PLAN.md` (the experiment).

## Layout
```
api/    FastAPI app (gate engine, verifier, sessions, attempts)
web/    Next.js app (game UI, report); proxies /api/* to the API
ml/     offline experiment: scripts/, data/, notes/, results/
infra/  render.yaml, supabase/migrations/
docs/   PRD, PLAN, ARCHITECTURE, endor-facts
```

## Prerequisites
- [uv](https://docs.astral.sh/uv/) (installs Python 3.11 on first sync)
- Node 22 and pnpm 10: `corepack install -g pnpm@10.18.0`

## Run locally
```sh
# API on :8000 (mock decision client, no credits needed)
cd api
cp .env.example .env
uv sync
uv run --env-file .env uvicorn app.main:app --reload --port 8000

# Web on :3000, in a second terminal. The browser only talks to :3000;
# Next.js rewrites /api/* to API_ORIGIN (default http://127.0.0.1:8000).
cd web
cp .env.example .env.local
pnpm install
pnpm dev
```

## Checks (same as CI)
```sh
cd api && uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
cd web && pnpm lint && pnpm tsc && pnpm test && pnpm e2e
```

`pnpm e2e` needs Chromium once: `pnpm exec playwright install chromium`. The barrier lab lives at `/dev/barrier` in dev.

Live decision-API tests are marked `live` and skipped by default: `uv run pytest -m live`.

## Database
Without `DATABASE_URL` the API uses an in-memory store (dev only). For Postgres
(Supabase in production) set `DATABASE_URL` in `api/.env`; for Supabase use the
**Session pooler** connection string from the project's Connect dialog.

```sh
cd api
uv run --env-file .env python -m app.store.migrate --dry-run   # list pending migrations
uv run --env-file .env python -m app.store.migrate             # apply them
```

Migrations live in `infra/supabase/migrations/` (Supabase CLI naming). Store
contract tests run against Postgres too when `TEST_DATABASE_URL` points at a
disposable database; CI uses a `postgres:16` service.
