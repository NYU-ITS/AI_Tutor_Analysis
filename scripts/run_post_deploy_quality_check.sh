#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-rit-genai-naga-dev}"
DEPLOYMENT="${DEPLOYMENT:-open-webui-mastering-homework}"
JOB_NAME="${JOB_NAME:-ai-tutor-backend-post-deploy-quality-check}"
TIMEOUT="${TIMEOUT:-900s}"

echo "Waiting for backend deployment rollout: ${DEPLOYMENT}"
oc rollout status "deployment/${DEPLOYMENT}" -n "${NAMESPACE}" --timeout="${TIMEOUT}"

echo "Starting backend post-deployment quality check: ${JOB_NAME}"
oc delete job "${JOB_NAME}" -n "${NAMESPACE}" --ignore-not-found
oc apply -f k8s/quality-checks/job.yaml -n "${NAMESPACE}"

if ! oc wait --for=condition=complete "job/${JOB_NAME}" -n "${NAMESPACE}" --timeout="${TIMEOUT}"; then
  echo "Backend quality check did not complete successfully. Recent logs:"
  oc logs "job/${JOB_NAME}" -n "${NAMESPACE}" || true
  exit 1
fi

oc logs "job/${JOB_NAME}" -n "${NAMESPACE}"
echo "Backend post-deployment quality check completed."
