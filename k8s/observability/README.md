# AI Tutor OpenShift Observability

This folder contains the namespace-owned observability baseline for AI Tutor testing in OpenShift dev.

The goal is to move away from Grafana Cloud and keep test observability inside `rit-genai-naga-dev`.

## What This Creates

- `ai-tutor-test-artifacts-bucket` ObjectBucketClaim for Playwright/Allure artifacts.
- `ai-tutor-quality-pushgateway` for short-lived test Jobs to publish final metrics.
- `ai-tutor-quality-prometheus` for time-series test metrics.
- `ai-tutor-quality-grafana` for the team dashboard.
- Grafana datasource pointing at the namespace Prometheus.
- Two deployed Grafana dashboards with the same simple overview layout:
  - `AI Tutor Quality - OpenShift` for post-deployment checks running inside OpenShift.
  - `AI Tutor Quality - GitHub` for GitHub Actions results once GitHub metrics are routed into the OpenShift metrics store.
- The local dashboard remains available for the local Docker/Grafana demo, but it is not imported into shared OpenShift Grafana.
- `ai-tutor-quality-grafana-provisioner` Job to create/update the Grafana datasource and dashboards through the Grafana API.
- `ai-tutor-quality-artifact-viewer` route for the latest Playwright report copied into OpenShift object storage.
- `ai-tutor-github-playwright-artifact-sync` one-time Job manifest for copying Playwright reports/videos after the GitHub read token is approved.

## Why Pushgateway Exists

Prometheus normally pulls metrics from long-running services.

AI Tutor test Jobs are short-lived. They run, publish results, and exit. A normal Prometheus scrape can miss them. Pushgateway gives those batch Jobs a place to push their final metrics so Prometheus can scrape the latest results after the Job exits.

This is only for test result metrics. Application metrics should use normal Prometheus scraping when available.

Pushgateway grouping is intentionally kept stable by `environment` and `repository`. It does not group by run id or commit sha because that would leave old batch results behind and make the dashboard look like stale failures are still current. Prometheus keeps numeric time history for trend panels, while ObjectBucket/S3 keeps heavy artifacts and recent-run indexes.

## Resource Requests

Initial conservative requests:

| Component | Request | Limit | Storage |
|---|---:|---:|---:|
| Pushgateway | `50m CPU`, `128Mi` | `250m CPU`, `256Mi` | none |
| Prometheus | `250m CPU`, `512Mi` | `1 CPU`, `2Gi` | `10Gi` PVC |
| Grafana | `250m CPU`, `512Mi` | `1 CPU`, `1Gi` | `5Gi` PVC |
| Artifact bucket | n/a | n/a | object storage |

These are dev starting values. After deployment, check real usage before increasing them:

```bash
oc adm top pods -n rit-genai-naga-dev | grep ai-tutor-quality
oc get pvc -n rit-genai-naga-dev | grep ai-tutor-quality
```

## Apply Order

```bash
oc apply -f k8s/observability/00-artifact-bucket.yaml -n rit-genai-naga-dev
oc apply -f k8s/observability/10-pushgateway.yaml -n rit-genai-naga-dev
oc apply -f k8s/observability/20-prometheus.yaml -n rit-genai-naga-dev
oc apply -f k8s/observability/30-grafana.yaml -n rit-genai-naga-dev
oc apply -f k8s/observability/40-grafana-datasource.yaml -n rit-genai-naga-dev
oc apply -f k8s/observability/50-grafana-dashboard.yaml -n rit-genai-naga-dev
oc apply -f k8s/observability/51-github-dashboard.yaml -n rit-genai-naga-dev
oc apply -f k8s/observability/60-grafana-provisioner-job.yaml -n rit-genai-naga-dev
oc apply -f k8s/observability/80-artifact-viewer.yaml -n rit-genai-naga-dev
```

The Grafana Operator dashboard/datasource custom resources are kept in place, but dev showed that they can report `NO MATCHING INSTANCES=true` while Grafana itself still has no datasource. The provisioner Job is the canonical path: it uses the Grafana admin secret, creates the Prometheus datasource, imports only the OpenShift and GitHub dashboards, then exits.

If the provisioner Job already exists from an earlier manual run, delete only that completed Job and apply it again:

```bash
oc delete job ai-tutor-quality-grafana-provisioner -n rit-genai-naga-dev
oc apply -f k8s/observability/60-grafana-provisioner-job.yaml -n rit-genai-naga-dev
```

Then point the backend and frontend post-deployment quality Jobs at Pushgateway:

```bash
oc apply -f k8s/quality-checks/job.yaml -n rit-genai-naga-dev
```

For frontend:

```bash
cd ../NAGA-open-webui
oc apply -f k8s/quality-checks/job.yaml -n rit-genai-naga-dev
```

These `Job` manifests are not schedules. They run once when applied. The deploy/rebuild flow should delete the previous completed Job, wait for the related deployment rollout, then apply the Job again.

## Access

Grafana is exposed through an OpenShift Route created by the Grafana Operator.

Check the URL:

```bash
oc get route -n rit-genai-naga-dev | grep ai-tutor-quality-grafana
```

The first version uses the Grafana Operator default admin secret. Before wider team sharing, confirm the access model with the platform/team owner.

## Retention Plan

Initial dev retention:

- Prometheus metrics: `30d`
- PostgreSQL detailed test history: planned next, target `90d`
- S3 artifacts: target `30d`

This folder implements the Prometheus/Grafana/bucket foundation first. PostgreSQL result tables are intentionally deferred until searchable per-test history is needed.

## Current Data Sources

- OpenShift post-deployment Jobs can publish directly to `ai-tutor-quality-pushgateway`.
- OpenShift frontend Playwright checks can upload reports, screenshots, videos, traces, and raw result files to ObjectBucket/S3 under `openshift/frontend/dev/runs/<run-id>/`.
- Local runs can publish to Pushgateway when port-forwarded or run inside the cluster.
- GitHub Actions uploads Prometheus metrics as workflow artifacts. `ai-tutor-github-quality-metrics-sync` can run inside OpenShift after the GitHub token is approved, pull the latest GitHub artifacts, and publish them to the internal Pushgateway.

The GitHub sync needs a read-only GitHub token stored in OpenShift. Use a fine-grained token with read access to Actions/artifacts and metadata for `AI_Tutor_Analysis` and `NAGA-open-webui`.

```bash
oc create secret generic ai-tutor-github-metrics-sync-secret \
  -n rit-genai-naga-dev \
  --from-literal=GITHUB_TOKEN='<GITHUB_READ_TOKEN>' \
  --dry-run=client -o yaml | oc apply -f -
```

After the token is approved, run the sync Job manually from the deploy/release flow:

```bash
oc delete job ai-tutor-github-quality-metrics-sync -n rit-genai-naga-dev --ignore-not-found
oc apply -f k8s/observability/70-github-metrics-sync.yaml -n rit-genai-naga-dev
oc logs job/ai-tutor-github-quality-metrics-sync -n rit-genai-naga-dev -f
```

This is intentionally not a schedule. It should run only when the team wants GitHub Actions results copied into the OpenShift dashboard.

## Post-Deployment Trigger Pattern

With the current user permissions, the deploy-and-test automation is run by scripts from a logged-in machine. A fully server-side trigger would need a service account with RBAC permissions to start builds, restart/wait for rollouts, create Jobs, and read logs. That permission is not available to this user, so this setup avoids it.

Backend build, rollout, and quality check:

```bash
bash scripts/run_backend_build_deploy_quality_check.sh
```

Backend post-deployment check only:

```bash
oc rollout status deployment/open-webui-mastering-homework -n rit-genai-naga-dev
oc delete job ai-tutor-backend-post-deploy-quality-check -n rit-genai-naga-dev --ignore-not-found
oc apply -f k8s/quality-checks/job.yaml -n rit-genai-naga-dev
oc logs job/ai-tutor-backend-post-deploy-quality-check -n rit-genai-naga-dev -f
```

Frontend build, rollout, and quality check:

```bash
cd ../NAGA-open-webui
bash scripts/run_frontend_build_deploy_quality_check.sh
```

Frontend post-deployment check only:

```bash
cd ../NAGA-open-webui
oc rollout status statefulset/open-webui -n rit-genai-naga-dev
oc delete job ai-tutor-frontend-post-deploy-quality-check -n rit-genai-naga-dev --ignore-not-found
oc apply -f k8s/quality-checks/job.yaml -n rit-genai-naga-dev
oc logs job/ai-tutor-frontend-post-deploy-quality-check -n rit-genai-naga-dev -f
```

## Artifact Direction

The ObjectBucketClaim stores Playwright HTML reports and videos in OpenShift-owned object storage.

The first artifact path syncs GitHub Playwright artifacts into the bucket. The viewer can be applied any time:

```bash
oc apply -f k8s/observability/80-artifact-viewer.yaml -n rit-genai-naga-dev
```

After token approval, run the artifact sync Job manually from the deploy/release flow:

```bash
oc delete job ai-tutor-github-playwright-artifact-sync -n rit-genai-naga-dev --ignore-not-found
oc apply -f k8s/observability/90-github-playwright-artifact-sync.yaml -n rit-genai-naga-dev
oc logs job/ai-tutor-github-playwright-artifact-sync -n rit-genai-naga-dev -f
```

Get the artifact viewer URL:

```bash
oc get route ai-tutor-quality-artifacts -n rit-genai-naga-dev -o jsonpath='https://{.spec.host}{"\n"}'
```

The viewer shows the latest report plus recent runs from configured artifact prefixes:

- `openshift/frontend/dev`
- `github/frontend/rs-ai-tutor-tests`

If no artifact has been synced yet for a prefix, that table shows no runs until the first upload succeeds.
