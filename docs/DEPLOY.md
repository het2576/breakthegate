# Deploying Break the Gate

Three pieces: Supabase (database), Render (API plus two crons), Vercel (website and the `/api` proxy). Total cost to start is roughly $14 per month (two Render starter services plus crons) plus pennies of Endor usage.

## 0. Before you go public
- Founder approval: create `docs/LAUNCH-APPROVAL.md` containing the line `Approved: yes`. Until it exists, keep the site private and do not mention the Endor beta anywhere user-facing.
- Rotate the Supabase database password (it appeared in a chat log during development).
- Pick the reveal video id (YouTube id) for `REVEAL_VIDEO_ID`.

## 1. Supabase (done)
Schema is applied and recorded in `schema_migrations`. For a new project: set `DATABASE_URL` (Session pooler string), then `cd api && uv run --env-file .env python -m app.store.migrate --dry-run`, then without `--dry-run`. Render also runs the migration on every deploy (`preDeployCommand`).

## 2. Render (API)
1. Push the repo to GitHub.
2. Render dashboard, New, Blueprint, pick the repo. It reads `render.yaml` and creates `btg-api`, `btg-warm` (every 10 min) and `btg-retention` (daily).
3. Fill the secrets it asks for on `btg-api`: `ENDOR_API_KEY`, `DATABASE_URL`, `PROXY_SECRET` (run `openssl rand -hex 32`, keep it, you need it again on Vercel), `TURNSTILE_SECRET`, `REVEAL_VIDEO_ID`.
4. On `btg-warm` set `API_URL` to the API's public URL.
5. The API refuses to start in prod if `PROXY_SECRET`, `IP_HASH_SALT_SEED` (auto-generated) or `DATABASE_URL` are missing or weak. Check `https://<api>/health` returns `{"status":"ok"}`.

## 3. Cloudflare Turnstile
Cloudflare dashboard, Turnstile, add a widget for your domain. The secret key goes to Render as `TURNSTILE_SECRET`, the site key to Vercel as `NEXT_PUBLIC_TURNSTILE_SITE_KEY`. Without them the human check is skipped.

## 4. Vercel (website)
1. Import the repo, set Root Directory to `web`.
2. Environment variables: `API_ORIGIN` = the Render API URL, `PROXY_SECRET` = the same value as on Render, `NEXT_PUBLIC_TURNSTILE_SITE_KEY`.
3. Deploy. Visit the site, accept the consent sheet, play one attempt.
4. Verify the real client IP path (PRD 5.3): play from two networks and confirm in the API logs / `attempts.ip_hash` that the hashes differ. If every player shares one hash, Vercel is not passing `x-real-ip`; stop and fix before launch.
5. Add your domain under Project Settings, Domains.

## 5. Launch checklist
- [ ] `docs/LAUNCH-APPROVAL.md` says yes
- [ ] DB password rotated
- [ ] Turnstile keys set on both sides
- [ ] `MAX_DAILY_USD` set to what you will tolerate (default 5)
- [ ] Kill switch tested: set `GAME_PAUSED=true`, redeploy, attempts return 503 `paused`
- [ ] Warm cron green in Render logs
- [ ] Lighthouse mobile run on the deployed URL (target 90+)
- [ ] Test on a real phone and in Safari and Firefox
