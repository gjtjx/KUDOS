@echo off
cd /d "%~dp0"
set "CLINIC_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "CLINIC_PYTHON=.venv\Scripts\python.exe"
"%CLINIC_PYTHON%" -c "import fastapi,uvicorn,httpx,pydantic; from zoneinfo import ZoneInfo; ZoneInfo('America/New_York')" >nul 2>nul
if errorlevel 1 goto missing
if not exist "frontend\dist\index.html" goto missing
echo Open http://127.0.0.1:8000
"%CLINIC_PYTHON%" -m uvicorn app.main:create_app --factory --app-dir backend --host 127.0.0.1 --port 8000
pause
exit /b
:missing
echo Please run setup.cmd first.
pause
exit /b 1

