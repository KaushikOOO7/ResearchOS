@echo off
REM ==========================================================================
REM ResearchOS launcher (Windows)
REM
REM   run.bat
REM
REM First run: creates backend\.env, a Python venv, installs backend + frontend
REM dependencies. Then starts the API (port 8000) and the web app (port 5173).
REM Close the windows to stop the services.
REM ==========================================================================
setlocal
cd /d "%~dp0"

where python >nul 2>&1 || (echo Python 3.11+ is required. & pause & exit /b 1)
where npm    >nul 2>&1 || (echo Node.js 18+ is required. & pause & exit /b 1)

if not exist "backend\.env" (
  copy /y "backend\.env.example" "backend\.env" >nul
  echo [ResearchOS] Created backend\.env - add GEMINI_API_KEY there to enable AI analysis.
  echo [ResearchOS] Search works without a key; get one free at https://aistudio.google.com/apikey
)

if not exist ".venv" (
  echo [ResearchOS] Creating Python virtual environment...
  python -m venv .venv
)

echo [ResearchOS] Installing backend dependencies...
.venv\Scripts\python -m pip install --quiet --upgrade pip
.venv\Scripts\pip install --quiet -r backend\requirements.txt

if not exist "frontend\node_modules" (
  echo [ResearchOS] Installing frontend dependencies (first run only)...
  pushd frontend
  call npm install --no-audit --no-fund
  popd
)

echo [ResearchOS] Starting API on http://127.0.0.1:8000 ...
start "ResearchOS API" cmd /k "cd /d %CD%\backend && ..\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000"

echo [ResearchOS] Starting web app on http://localhost:5173 ...
pushd frontend
call npm run dev
popd
