# Monark 3D Mining Plan

A 3D geological visualization tool for gold prospects: drillhole traces, assay
grades, lithology, structural readings, topography, trenches, and vein
wireframes, viewed and imported/exported from one app.

## Run it (one command)

Prerequisites (one-time):
- Python venv already created at `venv/` with `backend/requirements.txt` installed
- Node deps already installed: `npm --prefix frontend install`
- A local Postgres instance reachable at the URL in `DATABASE_URL` (default:
  `postgresql://postgres:postgres@localhost:5432/mining_db` — override by
  setting `$env:DATABASE_URL` before running, or editing `run.ps1`)

Then, from the repo root in PowerShell:

```powershell
./run.ps1
```

This builds the frontend, applies database migrations, seeds a demo project
(`Monark Gold Prospect` — safe to re-run, it resets to a clean state each
time), and starts **one process on one port**: open **http://localhost:8000**.

## Logging in

There's no real email delivery in this dev setup. Click **Get Magic Login
Link**, then look at the terminal running `run.ps1` — the login link and a
token are printed there:

```
=== MAGIC LINK GENERATED FOR you@example.com ===
http://localhost:8000/auth/verify?token=...
```

Paste just the token into the "enter the login token directly" field and
click **Confirm Token**.

**New accounts are restricted** (`ALLOWED_SIGNUP_EMAILS` / `ALLOWED_SIGNUP_DOMAINS`
env vars — empty by default, meaning no new account can self-provision).
The seeded demo user `geologist@monark.com` already exists in the database,
so it can always log in. To allow another email to create an account, set
e.g. `$env:ALLOWED_SIGNUP_EMAILS = "me@example.com"` before running `run.ps1`.

## Sample data

`sample_data/` has ready-to-import CSVs (collar, survey, assay, lithology,
topography, trench) with worked examples of QA/QC flags and a
below-detection-limit value — see `sample_data/README_AR.md`. Use them via
**Import Drillholes (CSV)** / **Upload Topo / Trenches / Veins** in the app,
or look at the seeded `Monark Gold Prospect` project for data that's already
loaded and visible immediately after `./run.ps1`.

## Development (active frontend work)

`run.ps1` does a one-time frontend *build*. If you're editing frontend code
and want it to rebuild automatically, run the dev watcher on its own port
instead of (or alongside) the built copy:

```powershell
npm --prefix frontend run dev   # serves on http://localhost:8001 with live rebuild
```

The backend (`venv\Scripts\python -m uvicorn backend.src.api.main:app --reload --port 8000`)
can run independently of which frontend copy you're viewing.

## Tests

```powershell
venv\Scripts\python.exe -m pytest backend/tests -q -c backend/pytest.ini
```

Must be run with the repo root as `rootdir` (imports are `backend.src.*`) —
running from inside `backend/` will fail with `ModuleNotFoundError`.
