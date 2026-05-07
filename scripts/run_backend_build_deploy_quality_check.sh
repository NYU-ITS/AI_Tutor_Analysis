#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-rit-genai-naga-dev}"
APP_BUILD_CONFIG="${APP_BUILD_CONFIG:-open-webui-mastering-homework}"
QUALITY_BUILD_CONFIG="${QUALITY_BUILD_CONFIG:-ai-tutor-quality-checks}"
DEPLOYMENT="${DEPLOYMENT:-open-webui-mastering-homework}"

echo "Building backend quality-check image: ${QUALITY_BUILD_CONFIG}"
oc start-build "${QUALITY_BUILD_CONFIG}" --follow --wait -n "${NAMESPACE}"

echo "Building backend application image: ${APP_BUILD_CONFIG}"
oc start-build "${APP_BUILD_CONFIG}" --follow --wait -n "${NAMESPACE}"

echo "Waiting for backend deployment rollout: ${DEPLOYMENT}"
oc rollout status "deployment/${DEPLOYMENT}" -n "${NAMESPACE}" --timeout=900s

echo "Running backend post-deployment quality check"
bash scripts/run_post_deploy_quality_check.sh
