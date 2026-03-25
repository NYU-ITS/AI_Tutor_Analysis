#!/bin/bash
# Run Student Analysis Pipeline locally without PostgreSQL.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

if ! python -c "import fastapi, uvicorn, sqlalchemy, dotenv, requests, fitz" >/dev/null 2>&1; then
  echo "Installing dependencies from requirements.txt..."
  pip install --quiet -r requirements.txt
else
  echo "Dependencies already available in .venv; skipping pip install."
fi

# Force SQLite for local boot so Postgres is not required.
export PIPELINE_DATABASE_URL="${PIPELINE_DATABASE_URL:-sqlite:///./student_analysis.db}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///./student_analysis.db}"

echo "Using PIPELINE_DATABASE_URL=$PIPELINE_DATABASE_URL"
echo "Using DATABASE_URL=$DATABASE_URL"

PORT="${PORT:-8000}"
RELOAD="${RELOAD:-false}"
echo "Starting API on http://localhost:$PORT ..."
if [ "$RELOAD" = "true" ]; then
  exec uvicorn app.main:app --reload --port "$PORT"
else
  exec uvicorn app.main:app --port "$PORT"
fi
