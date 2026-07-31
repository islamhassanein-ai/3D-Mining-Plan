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

.NOTES
  Requires: Python venv at .\venv, Node deps at .\frontend\node_modules, and a
  reachable Postgres instance matching $env:DATABASE_URL (see README.md).
  This script verifies all three and explains how to fix whatever is missing.

  If your local Postgres password isn't "postgres", create a `.env` file
  (gitignored) next to this script with a line like:
    DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/mining_db
  so you don't have to set the env var by hand every run.
#>
[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [switch]$SkipSeed
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
    Write-Host "DATABASE_URL not set -- defaulting to $($env:DATABASE_URL)" -ForegroundColor Yellow
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

# Postgres must be reachable. preflight_db.py also creates the database on a
# fresh checkout -- alembic can migrate one but cannot create it.
& $Python backend\preflight_db.py
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: database preflight failed (see above)." -ForegroundColor Red
    Write-Host ""
    exit 1
}

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

Write-Step "Applying database migrations..."
& $Python -m alembic -c backend/alembic.ini upgrade head
if ($LASTEXITCODE -ne 0) { Fail "Migrations failed" "Check the alembic output above." }

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
Write-Host "    Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

& $Python -m uvicorn backend.src.api.main:app --port $AppPort
