@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Run install-windows.bat first.& pause& exit /b 1)
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000 .*LISTENING"') do taskkill /F /PID %%P >nul 2>&1
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":5173 .*LISTENING"') do taskkill /F /PID %%P >nul 2>&1
start "StrikeCast API" cmd /k "cd /d "%~dp0" && call .venv\Scripts\activate.bat && python apps\api\run_api.py"
start "StrikeCast Web" cmd /k "cd /d "%~dp0apps\web" && npm.cmd run dev -- --host 127.0.0.1"
timeout /t 5 /nobreak >nul
start "" http://localhost:5173/
