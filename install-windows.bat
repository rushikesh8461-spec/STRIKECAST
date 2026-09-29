@echo off
setlocal
cd /d "%~dp0"
echo StrikeCast M1-M6 INSTALL
where python >nul 2>&1 || (echo Python not found.& exit /b 1)
where npm.cmd >nul 2>&1 || (echo Node.js/npm.cmd not found.& exit /b 1)
if not exist ".venv\Scripts\python.exe" python -m venv ".venv"
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r "requirements.txt"
cd /d "%~dp0apps\web"
call npm.cmd install
cd /d "%~dp0"
if not exist "apps\web\.env" copy /Y "apps\web\.env.example" "apps\web\.env" >nul
echo INSTALLATION COMPLETE.
pause
