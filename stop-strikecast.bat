@echo off
taskkill /FI "WINDOWTITLE eq StrikeCast M5 Backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq StrikeCast M6 Frontend*" /T /F >nul 2>&1
echo StrikeCast stopped.
pause
