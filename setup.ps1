# Game event progress - Windows setup
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> Check Python..." -ForegroundColor Cyan
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
  Write-Error "Python not found. Install Python 3.10+"
}

Write-Host "==> Create data dirs..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path data, public\data | Out-Null

# Skip pip when requirements.txt is comments-only
$reqLines = @()
if (Test-Path requirements.txt) {
  $reqLines = @(Get-Content requirements.txt | Where-Object { $_ -match '^\s*[^#\s]' })
}
if ($reqLines.Count -gt 0) {
  Write-Host "==> Install dependencies..." -ForegroundColor Cyan
  python -m pip install -r requirements.txt
}

Write-Host "==> Publish data to public/data..." -ForegroundColor Cyan
python scripts/publish_data.py

Write-Host ""
Write-Host "Done. Next:" -ForegroundColor Green
Write-Host "  Update:  python scripts/update.py"
Write-Host "  Preview: python -m http.server 5173"
Write-Host "           http://localhost:5173/public/"
Write-Host "  Docker:  docker compose up -d  -> http://localhost:8080"
Write-Host "  API:     python scripts/server.py  -> http://localhost:8080"
