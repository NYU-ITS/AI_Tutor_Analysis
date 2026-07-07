# AI Tutor Testing and Observability

Last updated: 2026-07-06

This is the source-of-truth overview for AI Tutor test ownership, OpenShift quality checks, metrics, secrets, and dashboard expectations across the backend `AI_Tutor_Analysis` repo and the frontend `NAGA-open-webui` repo.

## Scope and Repositories

Two repositories are involved and are deployed independently:

- Backend analytics service: `AI_Tutor_Analysis`, branch `feature/test-suite-expansion`
- Frontend OpenWebUI app: `NAGA-open-webui`, branch `rs/ai-tutor-tests`

The frontend calls backend analytics services for AI Tutor workflows, but the repos have separate build/deploy lifecycles on OpenShift. The test strategy therefore separates code-level CI from deployed-environment validation.

## Stage Ownership

GitHub Actions owns code-level checks:

- backend pytest unit and non-live integration tests
- frontend Vitest unit/component tests
- mocked Playwright UI checks
- artifacts and Prometheus-format metrics for CI runs; OpenShift imports the latest GitHub metrics through `ai-tutor-github-quality-sync` for the deployed Grafana dashboard

OpenShift owns deployed-environment checks:

- backend smoke checks
- backend live integration checks
- backend health checks
- backend external-service checks, including Portkey and databases
- frontend live Playwright browser workflows against the deployed dev frontend

OpenShift intentionally does not repeat the tests that already ran in GitHub Actions. This keeps resource use low and makes failures easier to interpret: GitHub failures mean code/test regressions, while OpenShift failures mean the deployed dev environment, credentials, route/service wiring, or external dependencies need attention.

## Backend Local Checks

Run from `AI_Tutor_Analysis`:

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

Local defaults skip OpenShift-only live checks unless the required live environment variables are explicitly set.

## Frontend Local Checks

Run from `NAGA-open-webui`:

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
PLAYWRIGHT_BROWSERS_PATH=0 npm run test:e2e:ui -- playwright/tests/ai-tutor-dashboard.mocked.spec.ts
```

Live Playwright requires real dev accounts, a reachable app, and a homework PDF fixture. OpenShift uses the tracked fixture in `NAGA-open-webui/playwright/fixtures/Math_HW.pdf`.

## GitHub Actions

### Backend Workflow

File:

- `.github/workflows/tests.yml`

Runs:

- pytest unit and non-live integration tests
- coverage output
- JUnit artifact upload
- quality metrics artifact upload
- optional legacy Grafana Cloud forwarding when GitHub repository secrets are configured

Does not run:

- OpenShift login
- personal `oc` tokens
- VPN-only OpenShift dev checks
- live Portkey/database/deployed-service checks

### Frontend Workflow

File in `NAGA-open-webui`:

- `.github/workflows/ai-tutor-playwright-tests.yml`

Runs:

- AI Tutor Vitest unit/component checks
- mocked Playwright dashboard workflows
- Playwright report/video artifacts
- quality metrics artifact upload
- optional legacy Grafana Cloud forwarding when GitHub repository secrets are configured

Live Playwright is environment gated and is not the default GitHub path. The preferred deployed-environment live browser validation is the OpenShift frontend quality BuildConfig.

## OpenShift Namespace

Namespace:

- `rit-genai-naga-dev`

Observability endpoint:

- Pushgateway: `http://ai-tutor-quality-pushgateway:9091`

Quality builds and jobs are short-lived. There are no recurring CronJobs for these test runs.

## Backend OpenShift Quality Checks

Files:

- `k8s/quality-checks/buildconfig.yaml`
- `k8s/quality-checks/job.yaml`
- `k8s/quality-checks/README.md`
- `scripts/run_openshift_quality_checks_from_build.sh`
- `scripts/run_openshift_quality_checks.sh`

Objects:

- ImageStream: `ai-tutor-quality-checks`
- BuildConfig: `ai-tutor-quality-checks`
- optional explicit rerun Job: `ai-tutor-backend-post-deploy-quality-check`

Automatic trigger:

```text
open-webui-mastering-homework:latest ImageStreamTag update
-> ai-tutor-quality-checks BuildConfig starts
-> quality_checks/Dockerfile builds the quality image
-> postCommit runs scripts/run_openshift_quality_checks_from_build.sh
-> live pytest checks run from inside OpenShift
-> metrics are pushed to ai-tutor-quality-pushgateway
```

Marker expression:

```bash
live and (smoke or integration or health or external_service)
```

The backend OpenShift runner uses strict live mode:

```bash
QUALITY_STRICT_LIVE_CHECKS=1
```

Missing required OpenShift config, Portkey credentials, database URLs, or service reachability fails the quality signal instead of becoming a quiet skip.

Backend OpenShift environment defaults:

- `LIVE_API_BASE_URL=http://open-webui-mastering-homework.rit-genai-naga-dev.svc:8000`
- `LIVE_FRONTEND_BASE_URL=http://open-webui.rit-genai-naga-dev.svc:80`
- `PORTKEY_BASE_URL=https://ai-gateway.apps.cloud.rt.nyu.edu/v1`
- `QUALITY_ENVIRONMENT=openshift-dev`
- `QUALITY_REPOSITORY=AI_Tutor_Analysis`
- `QUALITY_BRANCH=feature/test-suite-expansion`
- `QUALITY_SOURCE=openshift-backend-build-triggered-checks`
- `QUALITY_PUSHGATEWAY_URL=http://ai-tutor-quality-pushgateway:9091`
- `ARTIFACT_PREFIX=openshift/backend/dev`
- `QUALITY_UPLOAD_BACKEND_ARTIFACTS=1`

Backend OpenShift secret:

- Secret name: `open-webui-mastering-homework-secret`
- Required keys: `portkey-api-key`, `pipeline-database-url`, `database-url`
- BuildConfig mount path: `/var/run/ai-tutor-quality-secrets`

Do not put these values in `dockerStrategy.env`. OpenShift Docker strategy env can be rendered into Docker build instructions, logs, or layers. The BuildConfig uses a read-only secret volume instead.

Backend resource profile:

- quality image build request: `250m CPU`, `512Mi memory`
- quality image build limit: `1 CPU`, `1Gi memory`
- explicit Job request: `100m CPU`, `256Mi memory`
- explicit Job limit: `500m CPU`, `512Mi memory`

Backend OpenShift artifact outputs (written to the artifact PVC, see [Artifact Storage](#artifact-storage)):

- `openshift/backend/dev/runs/<run-id>/junit/results.xml`
- `openshift/backend/dev/runs/<run-id>/raw/live-results.xml`
- `openshift/backend/dev/runs/<run-id>/logs/backend-quality-redacted.log`
- `openshift/backend/dev/latest.json`
- `openshift/backend/dev/index.json`

The backend log artifact is sanitized before upload. The uploader replaces known secret environment values and common bearer token, API key, password, and database URL patterns with redaction markers. Artifact upload is best-effort and cannot turn a passing pytest run into a failed test run, but it logs the skip reason.

> **Build-vs-Job gotcha.** The BuildConfig sets `QUALITY_UPLOAD_BACKEND_ARTIFACTS=0` (frontend: `QUALITY_UPLOAD_ARTIFACTS=0`) because build pods cannot mount the artifact PVC. As noted above, OpenShift Docker-strategy `env` is baked into the output image, so that `0` also reaches the post-deploy Job at runtime. The post-deploy Job therefore **explicitly overrides the flag back to `1`** (and mounts the PVC). If you add a new upload toggle, set it in both places or the Job will silently skip uploads while still passing.

## Frontend OpenShift Quality Checks

Files in `NAGA-open-webui`:

- `k8s/quality-checks/buildconfig.yaml`
- `k8s/quality-checks/job.yaml`
- `k8s/quality-checks/README.md`
- `scripts/run_openshift_frontend_quality_checks_from_build.sh`
- `scripts/run_openshift_frontend_quality_checks.sh`
- `playwright/README.md`

Objects:

- ImageStream signal: `open-webui:latest`
- ImageStream: `ai-tutor-frontend-quality-checks`
- BuildConfig: `ai-tutor-frontend-quality-checks`
- optional explicit rerun Job: `ai-tutor-frontend-post-deploy-quality-check`

The existing frontend deployment flow is preserved:

- the frontend app BuildConfig can still push to `registry.cloud.rt.nyu.edu/rit-genai-poc/naga-open-webui:latest`
- the Helm-managed `StatefulSet/open-webui` can still pull that external image
- `open-webui:latest` in OpenShift tracks the external image as an automation signal only

Automatic trigger:

```text
external frontend image digest is imported into open-webui:latest
-> ai-tutor-frontend-quality-checks BuildConfig starts
-> quality_checks/Dockerfile builds the Playwright quality image
-> postCommit runs scripts/run_openshift_frontend_quality_checks_from_build.sh
-> live Playwright runs against the deployed OpenShift frontend
-> metrics are pushed to ai-tutor-quality-pushgateway
```

OpenShift scheduled image import is automatic, but it may not fire the exact second the external registry push completes. For an immediate test run after a manual frontend build, import the external image explicitly:

```bash
oc import-image open-webui:latest \
  --from=registry.cloud.rt.nyu.edu/rit-genai-poc/naga-open-webui:latest \
  --reference-policy=source \
  --confirm \
  -n rit-genai-naga-dev
```

Frontend OpenShift environment defaults:

- `PLAYWRIGHT_RUN_LIVE=1`
- `PLAYWRIGHT_STRICT_LIVE_CHECKS=1`
- `PLAYWRIGHT_SKIP_WEB_SERVER=1`
- `PLAYWRIGHT_BASE_URL=http://open-webui.rit-genai-naga-dev.svc:80`
- `PLAYWRIGHT_WORKERS=1`
- `PLAYWRIGHT_RETRIES=0`
- `PLAYWRIGHT_TIMEOUT=60000`
- `PLAYWRIGHT_VIDEO=on`
- `PLAYWRIGHT_HOMEWORK_PDF_PATH=/workspace/playwright/fixtures/Math_HW.pdf`
- `QUALITY_ENVIRONMENT=openshift-dev`
- `QUALITY_REPOSITORY=NAGA-open-webui`
- `QUALITY_BRANCH=rs/ai-tutor-tests`
- `QUALITY_SOURCE=openshift-frontend-build-triggered-playwright`
- `QUALITY_PUSHGATEWAY_URL=http://ai-tutor-quality-pushgateway:9091`

The OpenShift frontend runner uses the Playwright projects from `NAGA-open-webui/playwright.config.ts` without a `--project` filter. The live workflow therefore runs on Chromium, Firefox, and WebKit. With the current three live workflows, each OpenShift frontend quality run executes nine browser checks while keeping `PLAYWRIGHT_WORKERS=1` for the first resource measurement.

Frontend OpenShift secret:

- Secret name: `ai-tutor-playwright-live-secret`
- Required keys: `admin-email`, `admin-password`, `student-email`, `student-password`
- BuildConfig mount path: `/var/run/ai-tutor-playwright-live-secret`

The homework upload fixture is not stored in a secret. It is tracked in Git:

- repo path: `NAGA-open-webui/playwright/fixtures/Math_HW.pdf`
- OpenShift image path: `/workspace/playwright/fixtures/Math_HW.pdf`

To change the OpenShift test PDF, replace that repo file with the same filename, commit, push, and rebuild the frontend quality image.

Frontend resource profile:

- quality image build request: `500m CPU`, `1Gi memory`
- quality image build limit: `2 CPU`, `4Gi memory`
- explicit Job request: `1 CPU`, `2Gi memory`
- explicit Job limit: `2 CPU`, `4Gi memory`
- Playwright workers: `1`
- Playwright timeout: `60000ms`
- video: `on`

## Metrics and Dashboards

Metrics are test telemetry only. They include:

- pass/fail/error counts
- check duration
- repository, branch, source, environment, run id, and commit labels
- service/check status labels

They must not include:

- secrets
- database rows
- student submissions
- API response bodies
- uploaded PDF contents
- user credentials

Optional legacy Grafana Cloud GitHub repository secrets:

- `GRAFANA_CLOUD_PROMETHEUS_URL`
- `GRAFANA_CLOUD_PROMETHEUS_USER`
- `GRAFANA_CLOUD_PROMETHEUS_PASSWORD`

OpenShift Pushgateway grouping:

- job: `ai-tutor-quality`
- group labels: `environment`, `repository`

Dashboard JSON:

- deployed OpenShift dashboard: `AI_Tutor_Analysis/k8s/observability/50-grafana-dashboard.yaml`
- deployed GitHub dashboard: `AI_Tutor_Analysis/k8s/observability/51-github-dashboard.yaml`
- legacy/import-only Grafana Cloud backend overview: `AI_Tutor_Analysis/observability/grafana/dashboards/grafana-cloud-ai-tutor-quality.json`
- legacy/import-only Grafana Cloud frontend overview: `NAGA-open-webui/observability/grafana/dashboards/ai-tutor-frontend-github-quality.json`

Dashboard expectations:

- GitHub and OpenShift sources are shown separately
- backend and frontend repos are shown separately
- stat panels use latest-run style queries so repeated runs do not stack pass counts in the selected time window
- OpenShift panels identify deployed-environment failures separately from CI failures
- the local dashboard is kept for local Docker/Grafana only and is not imported into shared OpenShift Grafana

Heavy artifacts are stored on the artifact PVC instead of Prometheus (see [Artifact Storage](#artifact-storage)):

- OpenShift backend artifacts: `openshift/backend/dev/runs/<run-id>/`
- OpenShift backend latest marker: `openshift/backend/dev/latest.json`
- OpenShift backend recent run index: `openshift/backend/dev/index.json`
- OpenShift frontend artifacts: `openshift/frontend/dev/runs/<run-id>/`
- OpenShift frontend latest marker: `openshift/frontend/dev/latest.json`
- OpenShift frontend recent run index: `openshift/frontend/dev/index.json`
- GitHub backend artifacts: `github/backend/<branch>/runs/<run-id>/`
- GitHub frontend artifacts: `github/frontend/<branch>/runs/<run-id>/`

The deployed artifact viewer exposes the latest report plus recent runs. Prometheus keeps numeric history for 30 days via `--storage.tsdb.retention.time=30d`; the artifact PVC keeps heavy artifact history for 30 days via the daily cleanup CronJob.

## Artifact Storage

Heavy test artifacts (JUnit/raw XML, redacted logs, Playwright reports/videos/traces, synced GitHub artifacts) live on a dedicated `ReadWriteMany` PVC, `ai-tutor-quality-artifacts` (`vastdata-cloud`, `20Gi`), mounted at `/artifacts` in the backend Job, frontend Job, artifact viewer, GitHub sync CronJob, and cleanup CronJob. This replaced a NooBaa ObjectBucketClaim whose S3 endpoint accepted TCP/TLS but never returned HTTP responses (retired 2026-07-07).

The artifact tooling is storage-backend-neutral:

- `AI_Tutor_Analysis/scripts/quality_artifact_store.py` and `NAGA-open-webui/scripts/upload_openshift_playwright_artifacts.py` select a backend via `ARTIFACT_STORAGE_BACKEND` (`filesystem` today, `s3` retained for a future object-storage migration) and a root via `ARTIFACT_ROOT` (`/artifacts`).
- Logical artifact paths and the viewer's `/artifact/...` URLs are identical across backends, so Grafana links and dashboards do not change if storage moves back to S3.
- Retention is enforced by the daily `ai-tutor-quality-artifact-cleanup` CronJob (`k8s/observability/02-artifact-cleanup-cronjob.yaml`), which deletes files older than 30 days strictly under `/artifacts` and prunes `index.json`/`latest.json` entries for removed runs. The former S3 bucket lifecycle rule is retired.

Manifests: `k8s/observability/01-artifact-pvc.yaml` (PVC), `02-artifact-cleanup-cronjob.yaml` (retention), `80-artifact-viewer.yaml` (viewer). The deprecated OBC in `00-artifact-bucket.yaml` is kept unreferenced for a possible future S3 restoration.

## Operational Commands

Backend setup:

```bash
cd AI_Tutor_Analysis
oc apply -f k8s/quality-checks/buildconfig.yaml -n rit-genai-naga-dev
```

Artifact storage (PVC) and retention:

```bash
cd AI_Tutor_Analysis
oc apply -f k8s/observability/01-artifact-pvc.yaml -n rit-genai-naga-dev
oc apply -f k8s/observability/02-artifact-cleanup-cronjob.yaml -n rit-genai-naga-dev
# dry-run the retention pass from the viewer pod (same image + PVC mount) before the real thing:
oc exec deploy/ai-tutor-quality-artifact-viewer -n rit-genai-naga-dev -- \
  python scripts/quality_artifact_store.py cleanup-filesystem --days 30 --dry-run
```

GitHub metrics and artifact sync:

```bash
cd AI_Tutor_Analysis
oc apply -f k8s/observability/70-github-quality-sync.yaml -n rit-genai-naga-dev
oc create job ai-tutor-github-quality-sync-manual \
  -n rit-genai-naga-dev \
  --from=cronjob/ai-tutor-github-quality-sync
oc logs job/ai-tutor-github-quality-sync-manual -n rit-genai-naga-dev -f
```

The CronJob imports both backend and frontend GitHub metrics/artifacts when the
read-only GitHub token has access. Keep it suspended if token access is not
ready, and resume it once GitHub Actions/artifact reads are confirmed.

Backend manual quality rerun:

```bash
oc start-build ai-tutor-quality-checks --follow --wait -n rit-genai-naga-dev
```

Frontend setup:

```bash
cd NAGA-open-webui
oc apply -f k8s/quality-checks/buildconfig.yaml -n rit-genai-naga-dev
```

Frontend immediate external-image import and quality trigger:

```bash
oc import-image open-webui:latest \
  --from=registry.cloud.rt.nyu.edu/rit-genai-poc/naga-open-webui:latest \
  --reference-policy=source \
  --confirm \
  -n rit-genai-naga-dev
```

Frontend manual quality rerun:

```bash
oc start-build ai-tutor-frontend-quality-checks --follow --wait -n rit-genai-naga-dev
```

Check recent quality pods:

```bash
oc get pods -n rit-genai-naga-dev | grep quality
```

## Resource and Waste Controls

The implementation is intentionally event-driven and short-lived:

- no always-running test pods
- the only CronJobs are lightweight housekeeping: `ai-tutor-quality-artifact-cleanup` (daily retention) and `ai-tutor-github-quality-sync` (suspended until GitHub token access is confirmed); the quality checks themselves run as one-shot Jobs
- limited build history with `successfulBuildsHistoryLimit: 2` and `failedBuildsHistoryLimit: 2`
- completed explicit Jobs use `ttlSecondsAfterFinished: 3600`
- Playwright runs one worker in OpenShift and records video for passing and failing browser checks
- OpenShift runs only deployed-environment validation, not duplicate CI suites

Before requesting more resources, use real OpenShift runs to inspect actual build/job usage. Increase CPU or memory only if observed runs show consistent throttling, out-of-memory kills, or unacceptable runtime.

## Current Limitations and Next Improvements

- BuildConfig image-change triggers start checks automatically after image updates, but they are not a full rollout gate.
- The frontend trigger depends on OpenShift importing the external registry digest into the `open-webui:latest` ImageStreamTag.
- For strict "build, rollout, then test immediately" orchestration, use OpenShift Pipelines/Tekton or ArgoCD post-sync hooks with team-approved service-account RBAC.
- GitHub Actions should not access VPN-only OpenShift dev services unless a secure service-account-based path is approved.
- Grafana Cloud forwarding remains optional/legacy. The deployed dev dashboard path is the in-cluster Prometheus, Pushgateway, and Grafana stack in `rit-genai-naga-dev`.
