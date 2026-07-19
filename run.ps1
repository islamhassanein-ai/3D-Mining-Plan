<#
.SYNOPSIS
  One-command start for the Monark 3D Mining Plan app.

  Builds the frontend, applies database migrations, seeds a demo project
  (idempotent -- safe to re-run), then starts a single backend process that
  serves both the API and the 3D viewer on http://localhost:8000.

.NOTES
  Requires: Python venv already created at .\venv, Node deps already
  installed at .\frontend\node_modules, and a reachable Postgres instance
  matching $env:DATABASE_URL (see README.md).
#>

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
Set-Location $RepoRoot

if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/mining_db"
    Write-Host "DATABASE_URL not set -- defaulting to $($env:DATABASE_URL)" -ForegroundColor Yellow
}

Write-Host "==> Building frontend bundle..." -ForegroundColor Cyan
npm --prefix frontend run build

Write-Host "==> Applying database migrations..." -ForegroundColor Cyan
& "$RepoRoot\venv\Scripts\python.exe" -m alembic -c backend/alembic.ini upgrade head

Write-Host "==> Seeding demo project (safe to re-run)..." -ForegroundColor Cyan
& "$RepoRoot\venv\Scripts\python.exe" backend\seed_demo.py

Write-Host ""
Write-Host "==> Starting app at http://localhost:8000" -ForegroundColor Green
Write-Host "    Demo login: geologist@monark.com (magic-link token prints in this console)" -ForegroundColor Green
Write-Host ""

& "$RepoRoot\venv\Scripts\python.exe" -m uvicorn backend.src.api.main:app --port 8000
