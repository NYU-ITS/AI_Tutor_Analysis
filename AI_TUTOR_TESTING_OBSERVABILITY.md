# AI Tutor Testing and Observability

Last updated: 2026-05-07

This document describes the current AI Tutor testing and observability setup across local development, GitHub Actions, Grafana Cloud, and OpenShift dev.

## Current Scope

Two repositories are involved:

- Backend analytics service: `AI_Tutor_Analysis`, branch `feature/test-suite-expansion`
- Frontend dashboard: `NAGA-open-webui`, branch `rs/ai-tutor-tests`

The frontend calls the backend analytics service, but the repositories are built and deployed independently.

## Naming Convention

- `backend` means checks for `AI_Tutor_Analysis`.
- `frontend` means checks for `NAGA-open-webui`.
- OpenShift checks are deployed-environment checks. They are intentionally not scheduled because GitHub Actions already runs the code-level test suites.
- We avoid using `live` in Job names where it can be confused with production traffic. When a check touches the deployed dev environment, the docs call that a deployed-environment check.

## Local Backend Checks

Local backend checks are run from `AI_Tutor_Analysis`.

The default pytest setup skips external-service checks:

```bash
conda activate oi
cd AI_Tutor_Analysis
bash scripts/run_pytest_with_reports.sh
```

Outputs:

- `test-results/results.xml`
- `test-results/coverage.xml`

The local metrics exporter can read those files:

```bash
python scripts/serve_test_metrics.py
```

It exposes:

- `http://127.0.0.1:9109/metrics`
- `http://127.0.0.1:9109/`

## Local Frontend Checks

Local frontend checks are run from `NAGA-open-webui`.

Fast AI Tutor frontend checks:

```bash
conda activate oi
cd NAGA-open-webui
npm run test:frontend -- --run \
  src/lib/apis/aiTutor/index.test.ts \
  src/lib/utils/__tests__/aiTutorSessionCache.test.ts \
  src/lib/utils/__tests__/aiTutorTesting.test.ts \
  src/lib/stores/__tests__/aiTutorWorkspaceModels.test.ts
```

Mocked Playwright dashboard checks:

```bash
conda activate oi
cd NAGA-open-webui
PLAYWRIGHT_BROWSERS_PATH=0 npm run test:e2e:ui -- playwright/tests/ai-tutor-dashboard.mocked.spec.ts
```

Live Playwright workflows are scaffolded but require real accounts, a reachable app, and a homework PDF. They are not enabled by default.

## GitHub Actions

### Backend GitHub Workflow

File:

- `.github/workflows/tests.yml`

What it runs:

- backend pytest checks
- default non-live unit and integration tests
- coverage reporting
- test artifact upload
- Grafana Cloud metric forwarding when Grafana secrets are configured

What it does not do:

- it does not log into OpenShift
- it does not use personal `oc login` tokens
- it does not run VPN-only OpenShift dev checks

### Frontend GitHub Workflow

File in `NAGA-open-webui`:

- `.github/workflows/ai-tutor-playwright-tests.yml`

What it runs:

- AI Tutor Vitest unit/component checks
- mocked Playwright dashboard workflows
- Playwright report/video artifacts
- Grafana Cloud metric forwarding when Grafana secrets are configured

Live Playwright checks are environment-gated. They run only when explicitly enabled with the required credentials and URLs.

## Grafana Cloud

Grafana receives test metrics from:

- GitHub backend workflow
- GitHub frontend workflow
- OpenShift backend build-triggered deployed-environment quality checks
- OpenShift frontend live Playwright post-deployment quality checks

Required GitHub repository secrets:

- `GRAFANA_CLOUD_PROMETHEUS_URL`
- `GRAFANA_CLOUD_PROMETHEUS_USER`
- `GRAFANA_CLOUD_PROMETHEUS_PASSWORD`

Required OpenShift secret:

- `ai-tutor-grafana-cloud-secret`

The current metrics are test telemetry only:

- pass/fail/error counts
- check durations
- repository/branch/source labels
- commit SHA
- service/check names

The setup should not send secrets, database rows, student content, API response bodies, or user submissions to Grafana Cloud.

## Grafana Dashboard JSON

Backend/GitHub/OpenShift overview:

- `observability/grafana/dashboards/grafana-cloud-ai-tutor-quality.json`

Frontend GitHub/OpenShift dashboard in `NAGA-open-webui`:

- `observability/grafana/dashboards/ai-tutor-frontend-github-quality.json`

Important dashboard behavior:

- stat panels show the latest reported run per source
- pass counts do not stack across repeated runs in the selected time window
- failure panels separate GitHub checks from OpenShift deployed-environment checks

## Local Grafana Demo

The backend repo still includes a local Prometheus/Grafana demo:

```bash
cd AI_Tutor_Analysis/observability
docker compose up -d
```

Use this for local demos only. The OpenShift dev setup uses the namespace Pushgateway, Prometheus, and Grafana manifests in `k8s/observability`.

## OpenShift Dev Setup

Namespace:

- `rit-genai-naga-dev`

### Backend Build-Triggered Quality Checks

Files:

- `k8s/quality-checks/buildconfig.yaml`
- `k8s/quality-checks/job.yaml`
- `k8s/quality-checks/README.md`

OpenShift objects:

- BuildConfig/ImageStream image: `ai-tutor-quality-checks`
- post-deployment Job: `ai-tutor-backend-post-deploy-quality-check`

Automatic trigger:

- `ai-tutor-quality-checks` has an `ImageChange` trigger on `open-webui-mastering-homework:latest`
- when the backend app build updates that image stream tag, OpenShift starts the quality-check image build
- the quality-check build runs `scripts/run_openshift_quality_checks_from_build.sh` as its `postCommit` hook
- the hook reads required live-check secrets from `open-webui-mastering-homework-secret` through a read-only BuildConfig secret volume
- metrics are pushed to the in-namespace Pushgateway

What it checks:

- `smoke`: deployed backend/frontend routes respond
- `integration`: deployed backend API contract checks through read-only endpoints
- `health`: backend health, frontend health route, database connectivity, and Portkey credential/gateway checks
- `external_service`: Portkey AI gateway, OpenWebUI database, and pipeline database checks

The OpenShift backend quality runner is strict. Missing required deployed-environment config fails the quality signal instead of being treated as an acceptable skip.

The build-triggered quality check is short-lived. It runs checks, forwards metrics, then exits. The Job runner remains available for explicit reruns after a rollout.

### Frontend Post-Deployment Checks

Files in `NAGA-open-webui`:

- `k8s/quality-checks/buildconfig.yaml`
- `k8s/quality-checks/job.yaml`
- `k8s/quality-checks/README.md`

OpenShift objects:

- BuildConfig/ImageStream image: `ai-tutor-frontend-quality-checks`
- post-deployment Job: `ai-tutor-frontend-post-deploy-quality-check`

What it checks today:

- live Playwright AI Tutor workflows against the deployed OpenShift frontend

What it does not run:

- Vitest unit/component checks
- mocked Playwright checks

Reason:

- those tests already run in GitHub Actions and should not be repeated in OpenShift

## Post-Deploy Testing Direction

Run the OpenShift checks only after a new dev build/rollout, or when explicitly validating the deployed environment:

```bash
cd AI_Tutor_Analysis
bash scripts/run_backend_build_deploy_quality_check.sh

cd ../NAGA-open-webui
bash scripts/run_frontend_build_deploy_quality_check.sh
```

Longer term, this should be handled by OpenShift Pipelines/Tekton or ArgoCD post-sync hooks instead of personal tokens or manual terminal commands.

## Current Limitations

- OpenShift live Playwright requires real dev test accounts and a small homework PDF fixture ConfigMap.
- GitHub Actions should not access VPN-only OpenShift dev services unless a secure service-account-based path is approved.
- Grafana Cloud is external SaaS; if that is not acceptable, move metrics to OpenShift user-workload monitoring or an in-cluster Grafana/Prometheus setup.
- The local Grafana stack is for demos and development, not production operation.

## Resource Guidance

Current backend post-deployment checks:

- request: `100m CPU`, `256Mi memory`
- limit: `500m CPU`, `512Mi memory`
- marker expression: `live and (smoke or integration or health or external_service)`

Current frontend live Playwright post-deployment checks:

- request: `1 CPU`, `2Gi memory`
- limit: `2 CPU`, `4Gi memory`
- workers: `1`
- video: `off`

Internal Grafana OSS demo/team dashboard:

- small demo request: `250m CPU`, `512Mi memory`
- small demo limit: `1 CPU`, `1Gi memory`
- shared dev request: `500m CPU`, `1Gi memory`
- shared dev limit: `1 CPU`, `2Gi memory`
- storage: `5Gi` to `10Gi`
