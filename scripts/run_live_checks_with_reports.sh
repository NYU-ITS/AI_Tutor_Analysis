#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAMESPACE="${OPENSHIFT_NAMESPACE:-rit-genai-naga-dev}"
API_DEPLOYMENT="${OPENSHIFT_API_DEPLOYMENT:-open-webui-mastering-homework}"
OPENWEBUI_SECRET="${OPENSHIFT_OPENWEBUI_SECRET:-rit-genai-naga-dev-pguser-pilotgenai-dev-pg-sa}"
PIPELINE_SECRET="${OPENSHIFT_PIPELINE_SECRET:-rit-genai-naga-dev-pguser-open-webui-mastering-homework-sa}"
LIVE_API_BASE_URL="${LIVE_API_BASE_URL:-http://127.0.0.1:8000}"
QUALITY_LIVE_MARKER_EXPR="${QUALITY_LIVE_MARKER_EXPR:-live and (smoke or integration or health or external_service)}"

mkdir -p "${ROOT_DIR}/live-results"

cleanup() {
  local exit_code=$?
  if [[ -n "${DB_FORWARD_PID:-}" ]]; then
    kill "${DB_FORWARD_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${API_FORWARD_PID:-}" ]]; then
    kill "${API_FORWARD_PID}" >/dev/null 2>&1 || true
  fi
  wait "${DB_FORWARD_PID:-}" "${API_FORWARD_PID:-}" >/dev/null 2>&1 || true
  exit "${exit_code}"
}
trap cleanup EXIT INT TERM

if ! oc whoami >/dev/null 2>&1; then
  echo "OpenShift login not found. Run 'oc login ...' first." >&2
  exit 1
fi

PRIMARY_DB_POD="$(oc get pod -n "${NAMESPACE}" -l postgres-operator.crunchydata.com/role=master -o jsonpath='{.items[0].metadata.name}')"
if [[ -z "${PRIMARY_DB_POD}" ]]; then
  echo "Could not find the primary Postgres pod in namespace ${NAMESPACE}." >&2
  exit 1
fi

oc port-forward "pod/${PRIMARY_DB_POD}" 5432:5432 5433:5432 -n "${NAMESPACE}" >/tmp/ai-tutor-db-port-forward.log 2>&1 &
DB_FORWARD_PID=$!
oc port-forward "deployment/${API_DEPLOYMENT}" 8000:8000 -n "${NAMESPACE}" >/tmp/ai-tutor-api-port-forward.log 2>&1 &
API_FORWARD_PID=$!

python - <<'PY'
import socket
import time

checks = [("127.0.0.1", 5432), ("127.0.0.1", 5433), ("127.0.0.1", 8000)]
deadline = time.time() + 30
while time.time() < deadline:
    ok = True
    for host, port in checks:
        try:
            with socket.create_connection((host, port), timeout=1):
                pass
        except OSError:
            ok = False
            break
    if ok:
        raise SystemExit(0)
    time.sleep(0.5)
raise SystemExit("Timed out waiting for local port-forwards on 5432/5433/8000")
PY

export OPENWEBUI_URI="$(oc extract "secret/${OPENWEBUI_SECRET}" --keys=uri --to=- -n "${NAMESPACE}" 2>/dev/null | tr -d '\n')"
export PIPELINE_URI="$(oc extract "secret/${PIPELINE_SECRET}" --keys=uri --to=- -n "${NAMESPACE}" 2>/dev/null | tr -d '\n')"
export DATABASE_URL="$(python -c 'import os; from urllib.parse import urlparse, urlunparse; u=urlparse(os.environ["OPENWEBUI_URI"]); print(urlunparse((u.scheme, f"{u.username}:{u.password}@127.0.0.1:5433", u.path, u.params, u.query, u.fragment)))')"
export PIPELINE_DATABASE_URL="$(python -c 'import os; from urllib.parse import urlparse, urlunparse; u=urlparse(os.environ["PIPELINE_URI"]); print(urlunparse((u.scheme, f"{u.username}:{u.password}@127.0.0.1:5432", u.path, u.params, u.query, u.fragment)))')"
export PORTKEY_API_KEY="$(python -c 'from dotenv import dotenv_values; env=dotenv_values("student_analysis_pipeline/.env"); print(env.get("PORTKEY_API_KEY",""))')"
export PORTKEY_BASE_URL="$(python -c 'from dotenv import dotenv_values; env=dotenv_values("student_analysis_pipeline/.env"); print(env.get("PORTKEY_BASE_URL","https://ai-gateway.apps.cloud.rt.nyu.edu/v1"))')"
export LIVE_API_BASE_URL

cd "${ROOT_DIR}"
PYTHONPATH=student_analysis_pipeline pytest \
  --noconftest \
  tests/live \
  -m "${QUALITY_LIVE_MARKER_EXPR}" \
  --junitxml=live-results/results.xml \
  -v \
  "$@"
