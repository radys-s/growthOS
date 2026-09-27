# Spustí growthOS lokálně: backend (8000) a frontend (3000) v samostatných oknech, pak otevře prohlížeč.
# Použití:  powershell -ExecutionPolicy Bypass -File .\start.ps1
$root = $PSScriptRoot

Start-Process powershell -ArgumentList @(
    '-NoExit', '-Command',
    "Set-Location '$root\backend'; uv run python -m alembic upgrade head; uv run python -m uvicorn app.main:app --reload --port 8000"
)
Start-Process powershell -ArgumentList @(
    '-NoExit', '-Command',
    "Set-Location '$root\frontend'; npm run dev"
)

# Počkej, až frontend odpoví (max ~60 s), pak otevři dashboard.
for ($i = 0; $i -lt 30; $i++) {
    try {
        Invoke-WebRequest -Uri 'http://localhost:3000' -UseBasicParsing -TimeoutSec 2 | Out-Null
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}
Start-Process 'http://localhost:3000'
