#!/usr/bin/env bash
set -euo pipefail

SECRET_NAME="${QUALITY_OPENSHIFT_SECRET_NAME:-open-webui-mastering-homework-secret}"
SERVICEACCOUNT_DIR="${SERVICEACCOUNT_DIR:-/var/run/secrets/kubernetes.io/serviceaccount}"
TOKEN_PATH="${SERVICEACCOUNT_DIR}/token"
CA_PATH="${SERVICEACCOUNT_DIR}/ca.crt"
NAMESPACE_PATH="${SERVICEACCOUNT_DIR}/namespace"

if [[ ! -r "${TOKEN_PATH}" || ! -r "${CA_PATH}" || ! -r "${NAMESPACE_PATH}" ]]; then
  echo "Kubernetes service account token is not available; cannot load OpenShift quality-check secrets." >&2
  exit 1
fi

export LIVE_API_BASE_URL="${LIVE_API_BASE_URL:-http://open-webui-mastering-homework.rit-genai-naga-dev.svc:8000}"
export LIVE_FRONTEND_BASE_URL="${LIVE_FRONTEND_BASE_URL:-http://open-webui.rit-genai-naga-dev.svc:80}"
export PORTKEY_BASE_URL="${PORTKEY_BASE_URL:-https://ai-gateway.apps.cloud.rt.nyu.edu/v1}"
export QUALITY_ENVIRONMENT="${QUALITY_ENVIRONMENT:-openshift-dev}"
export QUALITY_REPOSITORY="${QUALITY_REPOSITORY:-AI_Tutor_Analysis}"
export QUALITY_BRANCH="${QUALITY_BRANCH:-feature/test-suite-expansion}"
export QUALITY_SOURCE="${QUALITY_SOURCE:-openshift-backend-build-triggered-checks}"
export QUALITY_COMMIT_SHA="${OPENSHIFT_BUILD_COMMIT:-${QUALITY_COMMIT_SHA:-openshift-build}}"
export QUALITY_RUN_ID="${OPENSHIFT_BUILD_NAME:-${HOSTNAME:-openshift-build}}"
export QUALITY_STRICT_LIVE_CHECKS="${QUALITY_STRICT_LIVE_CHECKS:-1}"
export QUALITY_PUSHGATEWAY_URL="${QUALITY_PUSHGATEWAY_URL:-http://ai-tutor-quality-pushgateway:9091}"

NAMESPACE="$(<"${NAMESPACE_PATH}")"
TOKEN="$(<"${TOKEN_PATH}")"
SECRET_URL="https://kubernetes.default.svc/api/v1/namespaces/${NAMESPACE}/secrets/${SECRET_NAME}"

secret_json="$(
  curl -fsS \
    --cacert "${CA_PATH}" \
    -H "Authorization: Bearer ${TOKEN}" \
    "${SECRET_URL}"
)"

eval "$(
  SECRET_JSON="${secret_json}" python - <<'PY'
import base64
import json
import os
import shlex

secret = json.loads(os.environ["SECRET_JSON"])
data = secret.get("data") or {}
mapping = {
    "PORTKEY_API_KEY": "portkey-api-key",
    "PIPELINE_DATABASE_URL": "pipeline-database-url",
    "DATABASE_URL": "database-url",
}
for env_name, key in mapping.items():
    encoded = data.get(key)
    if not encoded:
        raise SystemExit(f"Missing key {key!r} in OpenShift secret")
    value = base64.b64decode(encoded).decode("utf-8")
    print(f"export {env_name}={shlex.quote(value)}")
PY
)"

exec bash scripts/run_openshift_quality_checks.sh
