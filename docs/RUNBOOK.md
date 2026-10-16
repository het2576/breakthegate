# Runbook

## Pause the game
Render, `btg-api`, Environment, set `GAME_PAUSED=true`, save (it redeploys in about a minute). Players see "The game is paused." No Endor calls are made. Set it back to `false` to resume.

## Spend is climbing
The API stops calling Endor once `MAX_DAILY_USD` or `MAX_DAILY_TOKENS` is reached for the UTC day and answers 503 `paused`. Raise the env var to continue, or pause. Check real spend in the Endor dashboard (it lags a few minutes).

## Delete a player
Player self-serve: the "Delete my data" button. By hand, in the Supabase SQL editor (cascades to attempts, reveals, keys):
`delete from sessions where handle = 'their handle';`
Raw rows also expire automatically after 90 days (`btg-retention` cron).

## Rotate keys
- Endor: create a new key in the Endor dashboard, set `ENDOR_API_KEY` on Render, redeploy, revoke the old key.
- Proxy secret: set the same new `PROXY_SECRET` on Render and Vercel, redeploy both (brief 403s in between are expected).
- DB password: Supabase, Project Settings, Database, reset; update `DATABASE_URL` on Render (and both crons that reference it).
- Salt seed: changing `IP_HASH_SALT_SEED` only breaks same-day rate-limit continuity.

## Endor models are slow
First request after 15 idle minutes can take 1 to 3 minutes (cold start). The warm cron prevents it. If the circuit breaker opens, players see "warming up" and the API retries on its own; check Render logs for `outcome=` lines.

## Backups
Supabase free tier has no point-in-time restore. Before launch either upgrade to Pro (daily backups) or schedule `pg_dump` weekly. Eval files and raw attempts are the only irreplaceable data.
