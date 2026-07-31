<#
.SYNOPSIS
  One-command start for the MALLOGRIM GOLD MINE 3D Mining Plan app.

  Checks prerequisites, builds the frontend, applies database migrations,
  seeds a demo project (idempotent -- safe to re-run), then starts a single
  backend process that serves both the API and the 3D viewer on
  http://localhost:8000.

.DESCRIPTION
  The port is not configurable. frontend/src/services/api_client.js targets
  http://localhost:8000 whenever the page is served from localhost, so the
  viewer only reaches its API on that exact port.

.PARAMETER SkipBuild
  Reuse the existing frontend/dist bundle instead of rebuilding it.

.PARAMETER SkipSeed
  Do not run backend/seed_demo.py. Use when you already have real project data
  loaded and don't want the demo project recreated.

.PARAMETER UseSQLite
  Run against a local SQLite file (mining_dev.db) instead of PostgreSQL, for a
  quick look at the UI without a database server. Alembic is skipped -- the
  schema is built from the models, because the migrations use ALTER COLUMN,
  which SQLite does not support. Not the supported production path, and the
  choice is per-run: it is never written to .env.

.EXAMPLE
  .\run.ps1
  Normal start. Recovers a forgotten local Postgres password automatically.

.EXAMPLE
  .\run.ps1 -UseSQLite -SkipSeed
  Start against SQLite with no demo data.

.NOTES
  Requires: Python venv at .\venv, Node deps at .\frontend\node_modules, and
  (unless -UseSQLite) a reachable Postgres instance. This script verifies all
  of it and explains how to fix whatever is missing.

  Password handling: if the configured password is rejected by a LOCAL server,
  backend/preflight_db.py tries the common dev passwords, then prompts you, and
  writes whatever works to a gitignored `.env` so it persists. You can always
  write it yourself instead:
    DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/mining_db
#>
[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [switch]$SkipSeed,
    [switch]$UseSQLite
)

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
Set-Location $RepoRoot

$AppPort = 8000
$Python  = Join-Path $RepoRoot "venv\Scripts\python.exe"

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor DarkGray }

function Fail($problem, $fix) {
    Write-Host ""
    Write-Host "ERROR: $problem" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Fix: $fix" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

# ---------------------------------------------------------------------------
# Resolve DATABASE_URL
# ---------------------------------------------------------------------------

if ($UseSQLite) {
    # preflight_db.py --sqlite decides the file path and hands the URL back.
    Write-Host "SQLite mode requested -- PostgreSQL will not be used" -ForegroundColor Yellow
}
else {
    if (-not $env:DATABASE_URL) {
        $envFile = Join-Path $RepoRoot ".env"
        if (Test-Path $envFile) {
            Get-Content $envFile | ForEach-Object {
                if ($_ -match '^\s*DATABASE_URL\s*=\s*(.+)$') {
                    $env:DATABASE_URL = $Matches[1].Trim()
                }
            }
            if ($env:DATABASE_URL) {
                Write-Host "DATABASE_URL loaded from .env" -ForegroundColor Yellow
            }
        }
    }

    if (-not $env:DATABASE_URL) {
        $env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/mining_db"
        Write-Host "DATABASE_URL not set -- defaulting to the standard local Postgres" -ForegroundColor Yellow
    }
}

# ---------------------------------------------------------------------------
# Preflight -- fail early with an actionable message instead of a stack trace
# ---------------------------------------------------------------------------

Write-Step "Checking prerequisites..."

if (-not (Test-Path $Python)) {
    Fail "Python venv not found at .\venv" @"
Create it and install the backend dependencies:
      python -m venv venv
      .\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
"@
}
Write-Ok "venv found"

if (-not $SkipBuild) {
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npm) {
        Fail "npm is not on PATH" "Install Node.js (https://nodejs.org), or re-run with -SkipBuild to reuse the existing bundle."
    }
    if (-not (Test-Path (Join-Path $RepoRoot "frontend\node_modules"))) {
        Fail "Frontend dependencies are not installed" "Run:  npm --prefix frontend install"
    }
    Write-Ok "npm and node_modules found"
}

# Port must be free -- the viewer's API base URL is hardcoded to :8000.
$inUse = Get-NetTCPConnection -LocalPort $AppPort -State Listen -ErrorAction SilentlyContinue
if ($inUse) {
    $owner = ""
    try {
        $p = Get-Process -Id $inUse[0].OwningProcess -ErrorAction Stop
        $owner = " (held by $($p.ProcessName), PID $($p.Id))"
    } catch { }
    Fail "Port $AppPort is already in use$owner" @"
The 3D viewer can only reach its API on port $AppPort, so this one is required.
      Stop the other process, then re-run. To find it:
        Get-NetTCPConnection -LocalPort $AppPort -State Listen
"@
}
Write-Ok "port $AppPort is free"

# Resolve the database. preflight_db.py creates the database on a fresh
# checkout (alembic can migrate one but cannot create it), recovers a rejected
# local password, and persists whatever works to .env.
#
# Its stdout is echoed line by line so an interactive password prompt is
# visible; the final DATABASE_URL=... line is captured rather than printed,
# because resolution may have changed the value this script started with.
$preflightArgs = @("backend\preflight_db.py")
if ($UseSQLite) { $preflightArgs += "--sqlite" }
# Only offer the interactive password prompt from a real console. getpass reads
# the console handle directly, so prompting from a scheduled task or a piped
# run would block forever on a question nobody can see.
if ([Environment]::UserInteractive) { $preflightArgs += "--prompt" }

$resolvedUrl = $null
& $Python @preflightArgs | ForEach-Object {
    if ($_ -match '^DATABASE_URL=(.+)$') { $resolvedUrl = $Matches[1] }
    else { Write-Host "    $_" -ForegroundColor DarkGray }
}

if ($LASTEXITCODE -ne 0 -or -not $resolvedUrl) {
    Write-Host ""
    Write-Host "ERROR: database preflight failed (see above)." -ForegroundColor Red
    Write-Host ""
    exit 1
}

# Every later step (alembic, seed, uvicorn) reads this.
$env:DATABASE_URL = $resolvedUrl

# ---------------------------------------------------------------------------
# Build / migrate / seed
# ---------------------------------------------------------------------------

if ($SkipBuild) {
    if (-not (Test-Path (Join-Path $RepoRoot "frontend\dist\bundle.js"))) {
        Fail "-SkipBuild was passed but frontend\dist\bundle.js does not exist" "Re-run without -SkipBuild to build it."
    }
    Write-Step "Skipping frontend build (-SkipBuild)"
} else {
    Write-Step "Building frontend bundle..."
    npm --prefix frontend run build
    if ($LASTEXITCODE -ne 0) { Fail "Frontend build failed" "Check the esbuild output above." }
}

if ($UseSQLite) {
    # The schema was built from the models by preflight_db.py --sqlite. The
    # migrations cannot run here: they use ALTER COLUMN / DROP COLUMN, which
    # SQLite does not support outside batch mode.
    Write-Step "Skipping migrations (SQLite schema comes from the models)"
} else {
    Write-Step "Applying database migrations..."
    & $Python -m alembic -c backend/alembic.ini upgrade head
    if ($LASTEXITCODE -ne 0) { Fail "Migrations failed" "Check the alembic output above." }
}

if ($SkipSeed) {
    Write-Step "Skipping demo seed (-SkipSeed)"
} else {
    Write-Step "Seeding demo project (safe to re-run)..."
    & $Python backend\seed_demo.py
    if ($LASTEXITCODE -ne 0) { Fail "Demo seed failed" "Check the output above, or re-run with -SkipSeed." }
}

# ---------------------------------------------------------------------------
# Serve
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "==> MALLOGRIM GOLD MINE -- starting at http://localhost:$AppPort" -ForegroundColor Green
Write-Host "    Demo login: geologist@monark.com (magic-link token prints in this console)" -ForegroundColor Green
if ($UseSQLite) {
    Write-Host "    Database: SQLite (mining_dev.db) -- quick-test mode, not for real data" -ForegroundColor Yellow
}
Write-Host "    Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

& $Python -m uvicorn backend.src.api.main:app --port $AppPort
