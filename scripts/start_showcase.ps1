# Starts the loopback-only showcase: Postgres (127.0.0.1:54329), API :8000, web :3000.
# Run from the repository root. Stop with: powershell -File scripts\stop_showcase.ps1
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$db = docker ps -a --filter "publish=54329" --format "{{.Names}}" | Select-Object -First 1
if (-not $db) { throw 'No audit Postgres container publishes 127.0.0.1:54329. Create it first (see docs/LOCAL_RUNTIME.md).' }
docker start $db | Out-Null
.venv\Scripts\python.exe scripts\dev_native.py prepare
Start-Process -FilePath .venv\Scripts\python.exe -ArgumentList 'scripts\dev_native.py','api' -WindowStyle Hidden `
    -RedirectStandardOutput artifacts\showcase_api.log -RedirectStandardError artifacts\showcase_api.err
Start-Process -FilePath .venv\Scripts\python.exe -ArgumentList 'scripts\dev_native.py','web' -WindowStyle Hidden `
    -RedirectStandardOutput artifacts\showcase_web.log -RedirectStandardError artifacts\showcase_web.err
"Starting. Web: http://127.0.0.1:3000  API health: http://127.0.0.1:8000/healthz"
