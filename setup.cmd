@echo off
cd /d "%~dp0"
python -m venv .venv
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
if errorlevel 1 exit /b 1
cd frontend
call npm ci
if errorlevel 1 exit /b 1
call npm run build
if errorlevel 1 exit /b 1
echo Setup complete. Run start.cmd.
pause

