# Deploying TradePilot AI to Render (Free)

This document covers **production deployment only**. For local development, see
[README.md](README.md). Nothing in this document changes any trading rule,
ranking, filter, calculation, or intelligence module — it is infrastructure
configuration only.

## Architecture — the Crypto Intel pattern

**Render Free, no persistent disk.** This deployment follows the same
pattern already proven in production by the sibling `yashwantr93/crypto-intel`
project: the cloud service serves a **read-only copy** of whichever
`data_store/market.db` and `data_store/market_v2.db` were most recently
committed and pushed. Data collection stays on your local machine, exactly as
it always has — nothing in the cloud ever writes to these files.

This sidesteps Render Free's two hard constraints directly instead of working
around them:
- **No persistent disk on Free** → don't need one. The databases are tracked
  in git and simply arrive with every `git checkout` Render's build performs.
- **Free instances sleep after ~15 min idle and lose local state on wake** →
  doesn't matter. There's no local state to lose; the shipped files are
  re-delivered fresh on every deploy regardless of sleep/wake cycles.

```
  Local machine (data producer)                Render Free (read-only serving)
  ─────────────────────────────                ───────────────────────────────
  Windows Task Scheduler                        Web Service "tradepilot-ai"
  (SwingTradingIntelligence_DailyRun)              streamlit run app.py
    └─ run_daily_all.py                               --server.port $PORT
         (Phase 11 — chains, in order:                --server.address 0.0.0.0
          V1 → V2 → Event Intelligence
          in ONE command; supersedes the
          old separate run_daily.py +
          run_daily_v2.py calls below)
          │                                    scheduler.py: DISABLED
          ▼                                     (MID_ENABLE_SCHEDULER=0 —
  data_store/market.db                          the cloud instance never
  data_store/market_v2.db                        runs pipelines itself)
          │                                              ▲
          │  git add + commit + push                     │
          ▼                                              │
  GitHub (main branch)  ──────── autoDeploy ─────────────┘
                                 (git checkout delivers the
                                  shipped .db + latest CODE fresh —
                                  both travel together in one push)
```

**Two separate things travel together on every push, and both must be
current**: the application CODE (every `.py` file — pages, pipelines,
`event_intelligence/`) and the two DATA files (`market.db`/`market_v2.db`).
A push that updates only the data without the matching code (or vice versa)
still leaves production out of sync with what was verified locally — see
`refresh_status()`'s production-snapshot notice (Settings page) for the
signal to watch for this.

The V1/V2 read-only bridge (`intelligence_v2/database/v1_reference.py`,
SQLite `mode=ro` URI) is completely unaffected by this pattern — both files
are still plain local SQLite files on the container's filesystem at runtime,
just delivered by `git checkout` instead of written by a live pipeline. No
change to that "hard safety boundary" was needed or made.

## What runs where

| Component | Where | Notes |
|---|---|---|
| Streamlit dashboard | Render Free web service | `streamlit run app.py`, unchanged |
| Daily pipeline refresh | **Your local machine only** | `run_daily_all.py` (Phase 11) via the Windows Task Scheduler entry `SwingTradingIntelligence_DailyRun` |
| `market.db` / `market_v2.db` | Committed to git, shipped with every deploy | Read-only in the cloud |
| In-process scheduler (`scheduler.py`) | Present in the codebase, **disabled** in the cloud | `MID_ENABLE_SCHEDULER=0` — has no job to do here |
| Deployment-mode indicator | Every primary page + Settings | `core.config.IS_RENDER` (Phase 15) — reads Render's own `RENDER=true` env var to label the freshness badge as a static snapshot on production, never on local |

## The new workflow

```
Local refresh  →  git commit  →  git push  →  Render auto-deploy
```

1. **Local refresh** — run the full pipeline chain on your machine (Phase 11's
   unified orchestrator; the Windows Task Scheduler entry already does this
   nightly, so this step is usually already done for you):
   ```bash
   python run_daily_all.py
   ```
2. **Git commit** — stage and commit BOTH the refreshed database files AND
   any pending code changes (check `git status` first — data and code
   deploy together, and shipping data alone while code changes sit
   uncommitted leaves production on stale code even with fresh data):
   ```bash
   git add data_store/market.db data_store/market_v2.db <any changed code>
   git commit -m "Data + code refresh"
   ```
3. **Git push**:
   ```bash
   git push
   ```
4. **Render auto-deploy** — `render.yaml` sets `autoDeploy: true`, so Render
   detects the push and redeploys automatically (~2 minutes), delivering the
   fresh snapshot and the latest code together. No manual action needed on
   Render's side.
5. **Verify** — open the deployed URL → ⚙️ Settings → confirm the "Build"
   commit SHA matches `git log -1 --format=%h` locally, and the freshness
   badge's reference date matches step 1's run date.

Production data freshness = whenever you last did steps 1–3. This is the
same trade-off Crypto Intel already runs with in production — there is no
automatic cloud-side refresh in this pattern, by design.

## Startup sequence (verified)

1. Render runs `pip install -r requirements.txt`.
2. Render runs `streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true`.
3. `app.py` executes top to bottom:
   - `v2_init_db()` — idempotent; ensures `market_v2.db`'s schema exists (a no-op if the shipped file already has it, which it will).
   - `scheduler.start_if_enabled()` — reads `MID_ENABLE_SCHEDULER=0` (set in `render.yaml`) and does nothing. Verified: zero background threads started, `AppTest` shows no exception — identical to every prior version of this app before the scheduler existed.
   - Sidebar renders, selected page renders — reads whatever is in the two git-shipped database files.
4. Because the files are shipped with real data (once you've done a local refresh + push at least once), the dashboard shows real content immediately on first load — not an empty "no data yet" state, unlike the disk-based pattern this replaces.

## Verified: no additional infrastructure required

- No persistent disk (removed from `render.yaml`).
- No second service, no cron job, no external database, no object storage.
- `render.yaml` defines exactly one service, two environment variables (`PYTHON_VERSION`, `MID_ENABLE_SCHEDULER`), no disk block.
- Everything Render Free provides out of the box (compute + `git checkout` on deploy) is sufficient.

## Exact Render environment variables

Already encoded in `render.yaml` — this table is for reference:

| Variable | Value | Required? |
|---|---|---|
| `PYTHON_VERSION` | `3.12.10` | Recommended |
| `MID_ENABLE_SCHEDULER` | `0` | **Required** — keeps the in-process scheduler off in the cloud; it has no role in this pattern |
| `PORT` | *(set automatically by Render)* | Never set yourself |

Everything else (`MID_DATA_DIR`, `MID_LOGS_DIR`, `MID_DATABASE_URL`, `MID_OFFLINE`) can stay unset. Unset, `MID_DATA_DIR`/`MID_LOGS_DIR` default to `<repo root>/data_store` and `<repo root>/logs` — exactly where the git-checked-out database files land, which is what this pattern needs. Do **not** set `MID_DATA_DIR` to a disk mount path here; there is no disk, and pointing there would make the app look in the wrong (empty) place instead of the shipped files.

## Exact Git commands to create the GitHub repo and push

Run these when you're ready — **not run by this audit** (per your instruction).

```bash
# 1. Create the GitHub repository (requires GitHub CLI `gh`, already authenticated).
gh repo create tradepilot-ai --private --source=. --remote=origin

# 2. Stage and commit everything currently uncommitted (review with `git status` first).
git add -A
git commit -m "Convert to Render Free deployment: git-shipped SQLite snapshot pattern"

# 3. Push main and set the upstream tracking branch.
git push -u origin main
```

If you don't have `gh` installed, create the repository manually at
github.com/new (do not initialize it with a README/license — this repo
already has one), then:

```bash
git remote add origin https://github.com/<your-username>/tradepilot-ai.git
git add -A
git commit -m "Convert to Render Free deployment: git-shipped SQLite snapshot pattern"
git push -u origin main
```

## Deploying (steps — do not run until you're ready)

1. Run the Git commands above.
2. In Render: **New → Blueprint**, point it at the GitHub repo. Render reads `render.yaml` and provisions the free web service + both environment variables automatically.
3. First deploy: dashboard is live with whatever data was in `market.db`/`market_v2.db` at the time you pushed.
4. Verify: open the deployed URL, open **⚙️ Settings** to confirm database status, and confirm the freshness dates match your last local refresh.
5. To refresh production data going forward, repeat the four-step workflow above (§"The new workflow").

## Known limitation, stated plainly

Data only updates when you manually refresh, commit, and push. There is no
automatic daily cloud-side refresh in this pattern — that's the direct trade
for staying on Render's free tier with zero additional infrastructure. If
automatic daily refresh becomes a requirement later, that's a deliberate
architecture decision to revisit (e.g. a paid plan with a persistent disk —
`git log` still has the prior Starter-plan configuration if you want to
return to it — or an external hosted database), not something to solve by
re-enabling `scheduler.py` on Free, which cannot run reliably on an instance
that sleeps.

## Local development is unaffected

`.claude/launch.json` still runs `streamlit run app.py --server.port 8531`
exactly as before. `MID_ENABLE_SCHEDULER` defaults to off locally too (this
was already true before this change), so nothing about local behaviour
changes.
