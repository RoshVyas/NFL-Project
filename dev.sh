#!/usr/bin/env bash
# Starts the Python API (port 8000) and the React dev server (port 5173) together.
# Open http://localhost:5173 in your browser. Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x backend/.venv/bin/uvicorn ] || [ ! -d frontend/node_modules ]; then
  echo "First run: installing dependencies..."
  ./setup.sh
fi

backend/.venv/bin/uvicorn app.main:app --app-dir backend --reload --reload-dir backend/app --port 8000 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT

cd frontend
npm run dev -- --open
