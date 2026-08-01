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

## Adding planned (proposed) boreholes

A planned hole is one that has been designed but not yet drilled. There is no
separate import for them — they go through the same collar/combined CSV as
drilled holes, with a **`Status`** column.

| `Status` value | Result |
| --- | --- |
| `planned`, `plan`, `proposed`, `design`, `target`, `true`, `yes`, `1` | Rendered as a planned hole |
| `drilled`, `drill`, `complete`, `completed`, `existing`, `actual`, `false`, `no`, `0`, or blank/absent | Rendered as a drilled hole |

**There are only two statuses.** Everything in the first row is an alias for the
same thing — `proposed` and `planned` are identical, and so are `design` and
`target`; they exist so a collar file exported from someone else's software
imports without being edited first. The database stores `planned` either way,
and the viewer draws them identically. If you want a distinction between "we
intend to drill this" and "this is a formal design", it has to be a separate
column, not a `Status` value.

Minimal collar CSV — the only difference from a drilled hole is the last column:

```csv
hole_id,easting,northing,elevation,hole_type,status
DDH-001,515000,4515000,1050,DD,drilled
PL-001,515080,4515040,1048,DD,planned
```

In the combined CSV the same column sits alongside the assay rows, and a
planned hole may carry **target** intervals — the grades you expect to
intersect — which render as translucent sleeves over the trajectory:

```csv
Hole Id,Zone,X,Y,Z,Dip,Azimuth,Total_Length,Type,Status,Sample_ID,From,To,Grade
AAPL001,Abo Elmajd,208270.00,2467915.00,300.00,-65,110,90.0,DD,planned,AAPL001-T01,30,45,1.20
AAPL001,,,,,,,,,,AAPL001-T02,60,72,2.80
```

`sample_data/09_planned_and_unsampled.csv` and
`sample_data/10_collar_with_planned.csv` are working examples — import either
via **Import Drillholes (CSV)**.

**How they look.** A planned hole is drawn as a white collar marker with a black
dashed trace beneath it, so it can never be mistaken for a drilled hole at a
glance. The marker is white rather than a bright colour on purpose: white is
the only high-contrast colour the data palette never uses, so it can't be
misread as a grade result. Give a hole a dip and azimuth (and `Total_Length`) and its
trajectory is desurveyed exactly like a real one, which is the point — you are
looking at where the hole would actually go, not a vertical stick.

Planned holes are their own layer: the **Planned Holes** row in the floating
legend (or **Planned Boreholes** in the sidebar's Layers panel) hides both the
dashed traces and the target intervals together.

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
