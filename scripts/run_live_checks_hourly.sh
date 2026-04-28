#!/usr/bin/env bash

set -euo pipefail

INTERVAL_SECONDS="${1:-3600}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

while true; do
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting live observability refresh"
  if ! bash "${ROOT_DIR}/scripts/run_live_checks_with_reports.sh"; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Live refresh failed"
  fi
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sleeping for ${INTERVAL_SECONDS}s"
  sleep "${INTERVAL_SECONDS}"
done
