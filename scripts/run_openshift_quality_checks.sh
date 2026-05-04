#!/usr/bin/env bash
set -euo pipefail

mkdir -p live-results

export LIVE_API_BASE_URL="${LIVE_API_BASE_URL:-http://open-webui-mastering-homework.rit-genai-naga-dev.svc:8000}"
export LIVE_FRONTEND_BASE_URL="${LIVE_FRONTEND_BASE_URL:-http://open-webui.rit-genai-naga-dev.svc:80}"
export QUALITY_METRICS_TARGET="${QUALITY_METRICS_TARGET:-127.0.0.1:9109}"
export QUALITY_ENVIRONMENT="${QUALITY_ENVIRONMENT:-openshift-dev}"
export QUALITY_REPOSITORY="${QUALITY_REPOSITORY:-AI_Tutor_Analysis}"
export QUALITY_SOURCE="${QUALITY_SOURCE:-openshift-backend-scheduled-checks}"
export QUALITY_FORWARD_SECONDS="${QUALITY_FORWARD_SECONDS:-75}"
export QUALITY_PROMETHEUS_CONFIG_PATH="${QUALITY_PROMETHEUS_CONFIG_PATH:-/tmp/ai-tutor-grafana-cloud-prometheus.yml}"

pytest_status=0
PYTHONPATH=student_analysis_pipeline python -m pytest \
  --noconftest \
  tests/live \
  -m live \
  --junitxml=live-results/results.xml || pytest_status=$?

python scripts/serve_test_metrics.py \
  --results /tmp/non-live-results.xml \
  --coverage /tmp/non-live-coverage.xml \
  --live-results live-results/results.xml \
  --playwright-report /tmp/playwright-report/index.html \
  --host 127.0.0.1 \
  --port 9109 &
exporter_pid=$!

cleanup() {
  kill "${exporter_pid}" >/dev/null 2>&1 || true
  rm -f "${QUALITY_PROMETHEUS_CONFIG_PATH}"
}
trap cleanup EXIT

sleep 3
curl -fsS "http://${QUALITY_METRICS_TARGET}/metrics" >/dev/null

python scripts/write_grafana_cloud_prometheus_config.py --output "${QUALITY_PROMETHEUS_CONFIG_PATH}"

prometheus \
  --config.file="${QUALITY_PROMETHEUS_CONFIG_PATH}" \
  --storage.tsdb.path=/tmp/prometheus \
  --web.listen-address=127.0.0.1:9090 &
prometheus_pid=$!

sleep "${QUALITY_FORWARD_SECONDS}"
kill "${prometheus_pid}" >/dev/null 2>&1 || true
wait "${prometheus_pid}" >/dev/null 2>&1 || true

exit "${pytest_status}"
