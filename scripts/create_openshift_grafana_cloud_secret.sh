#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${OPENSHIFT_NAMESPACE:-rit-genai-naga-dev}"
SECRET_NAME="${GRAFANA_CLOUD_SECRET_NAME:-ai-tutor-grafana-cloud-secret}"

if [[ -z "${GRAFANA_CLOUD_PROMETHEUS_URL:-}" ]]; then
  read -r -p "Grafana Cloud remote write URL: " GRAFANA_CLOUD_PROMETHEUS_URL
fi
if [[ -z "${GRAFANA_CLOUD_PROMETHEUS_USER:-}" ]]; then
  read -r -p "Grafana Cloud Prometheus user / instance ID: " GRAFANA_CLOUD_PROMETHEUS_USER
fi
if [[ -z "${GRAFANA_CLOUD_PROMETHEUS_PASSWORD:-}" ]]; then
  read -r -s -p "Grafana Cloud Prometheus token: " GRAFANA_CLOUD_PROMETHEUS_PASSWORD
  echo
fi

oc create secret generic "${SECRET_NAME}" \
  --from-literal=GRAFANA_CLOUD_PROMETHEUS_URL="${GRAFANA_CLOUD_PROMETHEUS_URL}" \
  --from-literal=GRAFANA_CLOUD_PROMETHEUS_USER="${GRAFANA_CLOUD_PROMETHEUS_USER}" \
  --from-literal=GRAFANA_CLOUD_PROMETHEUS_PASSWORD="${GRAFANA_CLOUD_PROMETHEUS_PASSWORD}" \
  -n "${NAMESPACE}" \
  --dry-run=client \
  -o yaml | oc apply -f -

echo "Created/updated OpenShift secret ${SECRET_NAME} in namespace ${NAMESPACE}."
