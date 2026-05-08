# AI Tutor Backend Build-Triggered Quality Checks on OpenShift

This README documents the backend OpenShift quality-check implementation for `AI_Tutor_Analysis`.

For the full cross-repository testing and observability picture, see:

- `../../AI_TUTOR_TESTING_OBSERVABILITY.md`
- `../observability/README.md`

## Purpose

These checks answer one deployed-environment question:

```text
After the backend dev image changes, do the deployed OpenShift services and required external dependencies still work?
```

They do not replace GitHub Actions. GitHub Actions already runs the backend code-level pytest suite. OpenShift runs only the live deployed-environment subset: smoke, integration, health, and external-service checks.

## OpenShift Objects

Applied from `k8s/quality-checks/buildconfig.yaml`:

- ImageStream: `ai-tutor-quality-checks`
- BuildConfig: `ai-tutor-quality-checks`

Optional explicit rerun object from `k8s/quality-checks/job.yaml`:

- Job: `ai-tutor-backend-post-deploy-quality-check`

Namespace:

- `rit-genai-naga-dev`

## Automatic Trigger Flow

The BuildConfig has an ImageChange trigger on:

```text
open-webui-mastering-homework:latest
```

Expected flow:

```text
backend app build finishes
open-webui-mastering-homework:latest ImageStreamTag updates
ai-tutor-quality-checks build starts automatically
quality_checks/Dockerfile builds the quality-check image
postCommit runs scripts/run_openshift_quality_checks_from_build.sh
scripts/run_openshift_quality_checks.sh runs live pytest
metrics are pushed to ai-tutor-quality-pushgateway
build succeeds or fails with the test result
```

This removes the manual test trigger for normal backend builds. It is still a lightweight BuildConfig trigger, not a full rollout gate. The tests poll the deployed services from inside OpenShift. If the team needs a hard "new image has fully rolled out, then tests run" guarantee, the next step should be OpenShift Pipelines/Tekton or an ArgoCD post-sync hook with team-approved RBAC.

## Test Selection

The OpenShift runner executes:

```bash
PYTHONPATH=student_analysis_pipeline python -m pytest \
  --noconftest \
  tests/live \
  -m "live and (smoke or integration or health or external_service)" \
  --junitxml=live-results/results.xml
```

Meaning:

- `smoke`: deployed backend and frontend routes respond without server errors
- `integration`: deployed backend API contract checks through read-only endpoints
- `health`: backend route, frontend route, database connectivity, and Portkey gateway/credential checks
- `external_service`: Portkey AI gateway, OpenWebUI database, and pipeline database checks

Not run here:

- regular backend unit tests
- non-live mocked tests
- local-only tests
- frontend Vitest
- frontend mocked Playwright
- frontend live Playwright

Those belong to GitHub Actions or the frontend quality BuildConfig.

## Strict Failure Behavior

OpenShift sets:

```bash
QUALITY_STRICT_LIVE_CHECKS=1
```

Missing required configuration is a failed quality signal. Examples:

- missing Portkey API key
- missing database URL
- backend route unreachable
- frontend route unreachable
- Portkey gateway unhealthy or unauthorized
- required service URL not configured

This is intentional. A deployed-environment quality check should not look green when the environment is missing a required dependency.

## Required Config

Default non-secret env:

- `LIVE_API_BASE_URL=http://open-webui-mastering-homework.rit-genai-naga-dev.svc:8000`
- `LIVE_FRONTEND_BASE_URL=http://open-webui.rit-genai-naga-dev.svc:80`
- `PORTKEY_BASE_URL=https://ai-gateway.apps.cloud.rt.nyu.edu/v1`
- `QUALITY_ENVIRONMENT=openshift-dev`
- `QUALITY_REPOSITORY=AI_Tutor_Analysis`
- `QUALITY_BRANCH=feature/test-suite-expansion`
- `QUALITY_SOURCE=openshift-backend-build-triggered-checks`
- `QUALITY_PUSHGATEWAY_URL=http://ai-tutor-quality-pushgateway:9091`
- `QUALITY_OPENSHIFT_MARKER_EXPR=live and (smoke or integration or health or external_service)`

Required secret:

- name: `open-webui-mastering-homework-secret`
- keys:
  - `portkey-api-key`
  - `pipeline-database-url`
  - `database-url`

The BuildConfig mounts the secret read-only at:

```text
/var/run/ai-tutor-quality-secrets
```

Do not put secret values in `dockerStrategy.env`. Docker strategy env may appear in image build instructions, logs, or image layers.

## Secret Template

Use placeholders only in docs and scripts:

```bash
oc create secret generic open-webui-mastering-homework-secret \
  -n rit-genai-naga-dev \
  --from-literal=portkey-api-key='<portkey-api-key>' \
  --from-literal=pipeline-database-url='<pipeline-database-url>' \
  --from-literal=database-url='<database-url>' \
  --dry-run=client -o yaml | oc apply -f -
```

Do not store Playwright credentials or PDF fixtures in this backend secret.

## Apply or Update

```bash
oc apply -f k8s/quality-checks/buildconfig.yaml -n rit-genai-naga-dev
```

Check the trigger:

```bash
oc get buildconfig ai-tutor-quality-checks \
  -n rit-genai-naga-dev \
  -o jsonpath='{.spec.triggers}'
```

## Manual Reruns

Run the BuildConfig manually:

```bash
oc start-build ai-tutor-quality-checks --follow --wait -n rit-genai-naga-dev
```

Run the explicit Job path:

```bash
bash scripts/run_post_deploy_quality_check.sh
```

The Job script waits for rollout, deletes the previous completed Job, applies `job.yaml`, waits for completion, and prints logs.

## Metrics

The runner starts `scripts/serve_test_metrics.py`, scrapes local metrics, and pushes them to:

```text
http://ai-tutor-quality-pushgateway:9091
```

Pushgateway grouping:

- job: `ai-tutor-quality`
- `environment=openshift-dev`
- `repository=AI_Tutor_Analysis`

Useful PromQL:

```promql
ai_tutor_quality_checks_total{environment="openshift-dev",repository="AI_Tutor_Analysis"}
ai_tutor_quality_service_ok{environment="openshift-dev",repository="AI_Tutor_Analysis"}
ai_tutor_quality_group_checks_total{environment="openshift-dev",repository="AI_Tutor_Analysis"}
```

Metrics must remain telemetry only. Do not export secrets, request bodies, student content, uploaded files, or database rows.

## Resources

Quality build:

- request: `250m CPU`, `512Mi memory`
- limit: `1 CPU`, `1Gi memory`

Explicit Job:

- request: `100m CPU`, `256Mi memory`
- limit: `500m CPU`, `512Mi memory`
- `ttlSecondsAfterFinished: 3600`
- `backoffLimit: 0`

Build history is capped:

- `successfulBuildsHistoryLimit: 2`
- `failedBuildsHistoryLimit: 2`

This keeps resource use low and avoids a pile-up of old quality-check artifacts.

## Backend Artifact Upload

OpenShift backend runs upload deployment-level artifacts to ObjectBucket/S3 after metrics are pushed:

- prefix: `openshift/backend/dev/runs/<run-id>/`
- JUnit XML: `junit/results.xml`
- raw live-results XML: `raw/live-results.xml`
- redacted pytest log: `logs/backend-quality-redacted.log`
- latest marker: `openshift/backend/dev/latest.json`
- recent run index: `openshift/backend/dev/index.json`

Artifact upload is best-effort. A bucket or credential problem is logged and skipped, while the quality result still comes from the pytest exit status and pushed metrics.

The log uploader redacts known secret environment values and common bearer token, API key, password, and database URL patterns before any log content is written to the bucket. Do not add request payloads, student content, uploaded homework contents, tokens, or raw database rows to test logs.

Required artifact bucket wiring:

- BuildConfig mounts `ai-tutor-test-artifacts-bucket` at `/var/run/ai-tutor-artifacts-secret` and sets non-secret bucket host/name/port values.
- BuildConfig pins quality builds to `topology.kubernetes.io/region=rcdc`, matching the artifact components and avoiding cross-region object-storage connectivity surprises.
- Explicit Job uses `envFrom` for the ObjectBucketClaim Secret and ConfigMap.
- In-cluster bucket clients set `BUCKET_TLS_VERIFY=false` because the internal bucket endpoint uses the OpenShift self-signed service chain.

## Troubleshooting

Check recent builds:

```bash
oc get builds -n rit-genai-naga-dev | grep ai-tutor-quality-checks
```

Follow a build:

```bash
oc logs -f build/ai-tutor-quality-checks-<number> -n rit-genai-naga-dev
```

Check pods:

```bash
oc get pods -n rit-genai-naga-dev | grep quality
```

Common failures:

- `Missing mounted secret file`: update `open-webui-mastering-homework-secret`
- Portkey unauthorized/unreachable: verify `portkey-api-key` and `PORTKEY_BASE_URL`
- database health failure: verify `database-url` and `pipeline-database-url`
- route/service unreachable: verify OpenShift services and rollout state
- no metrics in Grafana: verify Pushgateway and dashboard source labels
