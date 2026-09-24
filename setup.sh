#!/usr/bin/env bash
# One-time setup: Python virtual environment + backend packages + frontend packages.
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
echo "Using $($PY --version)"
$PY -m venv backend/.venv
backend/.venv/bin/pip install --upgrade pip >/dev/null
backend/.venv/bin/pip install -r backend/requirements.txt

(cd frontend && npm install)

echo
echo "Setup done. Start the app with:  ./dev.sh"
