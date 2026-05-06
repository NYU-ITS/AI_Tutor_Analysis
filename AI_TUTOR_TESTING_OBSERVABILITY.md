# AI Tutor Testing and Observability

Last updated: 2026-05-05

This document describes the current AI Tutor testing and observability setup across local development, GitHub Actions, Grafana Cloud, and OpenShift dev.

## Current Scope

Two repositories are involved:

- Backend analytics service: `AI_Tutor_Analysis`, branch `feature/test-suite-expansion`
- Frontend dashboard: `NAGA-open-webui`, branch `rs/ai-tutor-tests`

The frontend calls the backend analytics service, but the repositories are built and deployed independently.

## Naming Convention

- `backend` means checks for `AI_Tutor_Analysis`.
- `frontend` means checks for `NAGA-open-webui`.
- `scheduled` means OpenShift runs the check automatically on a timer.
- We avoid using `live` in Job/CronJob names because it can be confused with production traffic. When a check touches the deployed dev environment, the docs call that a deployed-environment check.

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

Grafana Cloud currently receives test metrics from:

- GitHub backend workflow
- GitHub frontend workflow
- OpenShift backend scheduled quality checks
- OpenShift frontend scheduled quality checks

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
- failure panels separate GitHub checks from OpenShift scheduled checks

## Local Grafana Demo

The backend repo still includes a local Prometheus/Grafana demo:

```bash
cd AI_Tutor_Analysis/observability
docker compose up -d
```

Use this for local demos only. The OpenShift dev setup currently sends metrics to Grafana Cloud instead of running a long-lived Grafana/Prometheus stack inside the namespace.

## OpenShift Dev Setup

Namespace:

- `rit-genai-naga-dev`

### Backend Scheduled Checks

Files:

- `k8s/quality-checks/buildconfig.yaml`
- `k8s/quality-checks/job.yaml`
- `k8s/quality-checks/cronjob.yaml`
- `k8s/quality-checks/README.md`

OpenShift objects:

- BuildConfig/ImageStream image: `ai-tutor-quality-checks`
- manual Job: `ai-tutor-backend-scheduled-quality-check`
- scheduled CronJob: `ai-tutor-backend-scheduled-quality-checks`

Schedule:

- daily at `1:00 AM America/New_York`

What it checks:

- deployed backend service reachability
- tutor dashboard backend API smoke checks
- Portkey AI gateway reachability
- OpenWebUI database connection
- pipeline database connection
- lightweight OpenWebUI frontend route reachability

The Job is short-lived. It runs checks, forwards metrics, then exits.

### Frontend Scheduled Checks

Files in `NAGA-open-webui`:

- `k8s/quality-checks/buildconfig.yaml`
- `k8s/quality-checks/job.yaml`
- `k8s/quality-checks/cronjob.yaml`
- `k8s/quality-checks/README.md`

OpenShift objects:

- BuildConfig/ImageStream image: `ai-tutor-frontend-quality-checks`
- manual Job: `ai-tutor-frontend-scheduled-quality-check`
- scheduled CronJob: `ai-tutor-frontend-scheduled-quality-checks`

Schedule:

- daily at `1:00 AM America/New_York`

What it checks today:

- AI Tutor frontend Vitest unit/component checks

What is intentionally disabled in OpenShift today:

- Playwright browser checks

Reason:

- Chromium + Vite exceeded the small dev memory budget during testing. GitHub Actions remains the current place for mocked Playwright checks until a larger OpenShift runner/pod budget is approved.

## Post-Deploy Testing Direction

The current OpenShift scheduled checks run nightly.

To also run checks after a new dev deployment, trigger Jobs from the existing CronJobs after rollout:

```bash
oc rollout status deployment/<deployment-name> -n rit-genai-naga-dev

oc create job ai-tutor-backend-post-deploy-check-$(date +%s) \
  --from=cronjob/ai-tutor-backend-scheduled-quality-checks \
  -n rit-genai-naga-dev

oc create job ai-tutor-frontend-post-deploy-check-$(date +%s) \
  --from=cronjob/ai-tutor-frontend-scheduled-quality-checks \
  -n rit-genai-naga-dev
```

Longer term, this should be handled by OpenShift Pipelines/Tekton or ArgoCD post-sync hooks instead of personal tokens or manual terminal commands.

## Current Limitations

- OpenShift Playwright browser checks are not enabled by default because they need more memory.
- GitHub Actions should not access VPN-only OpenShift dev services unless a secure service-account-based path is approved.
- Grafana Cloud is external SaaS; if that is not acceptable, move metrics to OpenShift user-workload monitoring or an in-cluster Grafana/Prometheus setup.
- The local Grafana stack is for demos and development, not production operation.

## Resource Guidance

Current backend scheduled checks:

- request: `100m CPU`, `256Mi memory`
- limit: `500m CPU`, `512Mi memory`

Current frontend Vitest scheduled checks:

- request: `250m CPU`, `768Mi memory`
- limit: `1 CPU`, `2Gi memory`

Recommended OpenShift Playwright budget:

- minimum request: `1 CPU`, `2Gi memory`
- recommended limit: `2 CPU`, `4Gi memory`
- safer for video/report-heavy runs: `2 CPU`, `6Gi memory`

Internal Grafana OSS demo/team dashboard:

- small demo request: `250m CPU`, `512Mi memory`
- small demo limit: `1 CPU`, `1Gi memory`
- shared dev request: `500m CPU`, `1Gi memory`
- shared dev limit: `1 CPU`, `2Gi memory`
- storage: `5Gi` to `10Gi`
