$ErrorActionPreference = 'Stop'

Write-Host 'Starting StrikeCast API...' -ForegroundColor Cyan
Start-Process powershell -ArgumentList '-NoExit','-Command','cd apps/api; if (!(Test-Path ../../.venv)) { python -m venv ../../.venv }; ../../.venv/Scripts/Activate.ps1; python run_api.py'

Write-Host 'Starting StrikeCast web app...' -ForegroundColor Cyan
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList '-NoExit','-Command','cd apps/web; if (!(Test-Path node_modules)) { npm install }; npm run dev'

Write-Host 'API: http://localhost:8000' -ForegroundColor Green
Write-Host 'Web: http://localhost:5173' -ForegroundColor Green
