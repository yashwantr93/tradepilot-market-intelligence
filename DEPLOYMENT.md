# Deploying TradePilot AI to Render

This document covers **production deployment only**. For local development, see
[README.md](README.md). Nothing in this document changes any trading rule,
ranking, filter, calculation, or intelligence module — it is infrastructure
configuration only.

## Architecture

**One Render service, one disk.** The dashboard and the daily pipeline
refresh run in the same process, sharing the same persistent disk — the
simplest architecture that satisfies "website and daily pipeline operate on
the same database files" without inventing a second service, a shared-disk
workaround, or a database migration.

```
                         ┌───────────────────────────────────────────┐
                         │        Render Web Service                  │
                         │        "tradepilot-ai"                      │
                         │                                             │
   HTTPS  ──────────────▶│  streamlit run app.py                       │
  (Render's URL)         │   --server.port $PORT                       │
                         │   --server.address 0.0.0.0                  │
                         │                                             │
                         │  ┌─────────────────────────────────────┐   │
                         │  │ app.py (main thread)                 │   │
                         │  │  1. v2_init_db()                      │   │
                         │  │  2. scheduler.start_if_enabled()      │───┼──┐
                         │  │  3. render sidebar + selected page    │   │  │
                         │  │     (reads DBs via contracts.py)      │   │  │
                         │  └─────────────────────────────────────┘   │  │
                         │                                             │  │ starts (once,
                         │  ┌─────────────────────────────────────┐   │  │ st.cache_resource)
                         │  │ scheduler.py (background thread)     │◀──┼──┘
                         │  │  loop: every 15 min, check if today's │   │
                         │  │  refresh is due (default 14:30 UTC)   │   │
                         │  │  → subprocess: run_daily.py           │   │
                         │  │  → subprocess: run_daily_v2.py        │   │
                         │  └────────────────┬────────────────────┘   │
                         └───────────────────┼─────────────────────────┘
                                              │ reads/writes
                                              ▼
                         ┌───────────────────────────────────────────┐
                         │   Persistent Disk "tradepilot-data"          │
                         │   mounted at /var/data/tradepilot            │
                         │                                             │
                         │   market.db      (V1 — deal flow, results,   │
                         │                    sector rotation, ...)     │
                         │   market_v2.db   (V2 — sector intelligence,  │
                         │                    cycle, momentum,          │
                         │                    bearish/position opps)    │
                         │   logs/                                     │
                         └───────────────────────────────────────────┘
```

Both the request-serving code (reading via `data/contracts.py` and
`intelligence_v2/contracts/*.py`) and the refresh code (`run_daily.py` /
`run_daily_v2.py`, invoked as subprocesses by `scheduler.py`) run inside this
one service and therefore share this one disk by construction — there is no
cross-service disk-sharing question to answer, because there's only one
service.

## What runs where

| Component | Where | Notes |
|---|---|---|
| Streamlit dashboard | Main thread of the web service | Unchanged: `streamlit run app.py` |
| Daily pipeline refresh | Background thread, same process | New: `scheduler.py`, opt-in via `MID_ENABLE_SCHEDULER=1` |
| `market.db` / `market_v2.db` | Persistent disk, `/var/data/tradepilot` | Both read and written from the same service |

## Startup sequence (verified)

1. Render runs `pip install -r requirements.txt`.
2. Render runs `streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true`.
3. `app.py` executes top to bottom:
   - `v2_init_db()` — creates `market_v2.db`'s schema if missing (idempotent; safe on every rerun).
   - `scheduler.start_if_enabled()` — reads `MID_ENABLE_SCHEDULER`. If unset/`0`, does nothing (verified: zero threads started, `AppTest` shows no exception, identical to every prior version of this app). If `1`, starts exactly one background thread, guarded by `st.cache_resource` so Streamlit's per-interaction reruns of `app.py` never start a second one (verified directly: thread count stays at 1 across multiple reruns).
   - Sidebar renders, selected page renders — reads whatever is currently in the two database files.
4. First deploy on a fresh disk: dashboard renders with "no data yet" messages on every data-driven page (verified in the Phase 6 audit) — not an error state, expected until the first refresh completes.

## Daily refresh sequence (verified)

1. The background thread wakes every 15 minutes.
2. It runs once per UTC calendar day, at or after `MID_SCHEDULER_UTC_TIME` (default `14:30` UTC = 20:00 IST, matching the existing local Windows Task Scheduler's time).
3. When due: runs `run_daily.py` (the existing 6-step V1 pipeline orchestrator) as a subprocess, waits for it to finish, then runs `run_daily_v2.py` (the 5-step V2 orchestrator, new in this pass, mirrors `run_daily.py`'s exact pattern) as a subprocess.
4. Both subprocesses inherit this service's environment (`MID_DATA_DIR`, `MID_OFFLINE`, etc.) automatically — they write to the exact same disk-backed `data_store/` the dashboard reads from.
5. Marks today as done; won't run again until tomorrow's UTC date rolls over.
6. Neither subprocess blocks the dashboard — they run on a background thread; the main thread keeps serving requests throughout.
7. Verified locally: `run_daily_v2.py` completes 5/5 steps in ~45s against real data; a failure in one step is logged with the last 10 lines of its output and does not crash the scheduler loop (it simply tries again the next scheduled day).

## Exact Render environment variables

Set these on the `tradepilot-ai` web service (already encoded in `render.yaml` — this table is for reference / manual setup):

| Variable | Value | Required? |
|---|---|---|
| `PYTHON_VERSION` | `3.12.10` | Recommended (also set via `runtime.txt`) |
| `MID_DATA_DIR` | `/var/data/tradepilot` | **Required** — must match the disk's `mountPath` |
| `MID_LOGS_DIR` | `/var/data/tradepilot/logs` | Recommended |
| `MID_OFFLINE` | `0` | **Required** for the refresh to fetch real data (`1` would only ever write seeded/deterministic placeholder data) |
| `MID_ENABLE_SCHEDULER` | `1` | **Required** to get daily refreshes at all — omit only if you intend to refresh data some other way |
| `MID_SCHEDULER_UTC_TIME` | `14:30` | Optional — change only if you want the refresh at a different time of day |
| `PORT` | *(set automatically by Render)* | Never set yourself |

Everything not listed here (`MID_DATABASE_URL`, etc.) can stay unset — defaults are safe and documented in `.env.example`.

## Exact Git commands to create the GitHub repo and push

Run these when you're ready — **not run by this audit** (per your instruction).
This repo currently has one local commit on `main` and no remote configured.

```bash
# 1. Create the GitHub repository (requires GitHub CLI `gh`, already authenticated).
#    Choose --private or --public as you prefer; omitting --private makes it public.
gh repo create tradepilot-ai --private --source=. --remote=origin

# 2. Stage and commit everything currently uncommitted (review with `git status` first).
git add -A
git commit -m "Prepare for Render deployment: env-configurable paths, in-process scheduler, render.yaml"

# 3. Push main and set the upstream tracking branch.
git push -u origin main
```

If you don't have `gh` installed, create the repository manually at
github.com/new (do not initialize it with a README/license — this repo
already has one), then:

```bash
git remote add origin https://github.com/<your-username>/tradepilot-ai.git
git add -A
git commit -m "Prepare for Render deployment: env-configurable paths, in-process scheduler, render.yaml"
git push -u origin main
```

## Deploying (steps — do not run until you're ready)

1. Run the Git commands above.
2. In Render: **New → Blueprint**, point it at the GitHub repo. Render reads `render.yaml` and provisions the web service + disk + all six environment variables automatically.
3. First deploy: dashboard is live but empty (no data yet) until the scheduler's first scheduled run, or you trigger `run_daily.py` / `run_daily_v2.py` manually via Render's shell.
4. Verify: open the deployed URL, open **⚙️ Settings** to confirm database status/paths match `/var/data/tradepilot`, and confirm freshness dates update the day after first deploy.

## Local development is unaffected

`.claude/launch.json` still runs `streamlit run app.py --server.port 8531` exactly as before. No environment variable needs to be set locally — every new one defaults to current behaviour, and `MID_ENABLE_SCHEDULER` defaults to off, so the in-process scheduler never starts locally unless you explicitly opt in.
