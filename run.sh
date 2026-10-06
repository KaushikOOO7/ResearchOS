#!/usr/bin/env bash
# ===========================================================================
# ResearchOS launcher (macOS / Linux)
#
#   ./run.sh
#
# First run: creates backend/.env, a Python venv, installs backend + frontend
# dependencies. Then starts the API (port 8000) and the web app (port 5173).
# Press Ctrl+C to stop both.
# ===========================================================================
set -euo pipefail

cd "$(dirname "$0")"

info() { printf "\033[1;36m[ResearchOS]\033[0m %s\n" "$1"; }
warn() { printf "\033[1;33m[ResearchOS]\033[0m %s\n" "$1"; }

# --- prerequisites ---------------------------------------------------------
command -v python3 >/dev/null 2>&1 || { echo "Python 3.11+ is required."; exit 1; }
command -v npm     >/dev/null 2>&1 || { echo "Node.js 18+ is required."; exit 1; }

# --- environment -----------------------------------------------------------
if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  warn "Created backend/.env — add GEMINI_API_KEY there to enable AI paper analysis."
  warn "Search works without a key; get one free at https://aistudio.google.com/apikey"
fi

# --- python venv + backend deps -------------------------------------------
if [ ! -d .venv ]; then
  info "Creating Python virtual environment…"
  python3 -m venv .venv
fi

info "Installing backend dependencies…"
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r backend/requirements.txt

# --- frontend deps ---------------------------------------------------------
if [ ! -d frontend/node_modules ]; then
  info "Installing frontend dependencies (first run only)…"
  (cd frontend && npm install --no-audit --no-fund)
fi

# --- start both services ---------------------------------------------------
info "Starting API on http://127.0.0.1:8000  (docs: /docs)"
(cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload --port 8000) &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM

sleep 2
info "Starting web app on http://localhost:5173"
echo
info "Open http://localhost:5173 in your browser. Ctrl+C stops both services."
(cd frontend && npm run dev)
