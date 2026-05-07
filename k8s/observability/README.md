# AI Tutor OpenShift Observability

This folder contains the namespace-owned observability baseline for AI Tutor testing in OpenShift dev.

The goal is to move away from Grafana Cloud and keep test observability inside `rit-genai-naga-dev`.

## What This Creates

- `ai-tutor-test-artifacts-bucket` ObjectBucketClaim for Playwright/Allure artifacts.
- `ai-tutor-quality-pushgateway` for short-lived test Jobs to publish final metrics.
- `ai-tutor-quality-prometheus` for time-series test metrics.
- `ai-tutor-quality-grafana` for the team dashboard.
- Grafana datasource pointing at the namespace Prometheus.
- Three starter Grafana dashboards with the same basic layout:
  - `AI Tutor Quality - OpenShift` for scheduled checks running inside OpenShift.
  - `AI Tutor Quality - GitHub` for GitHub Actions results once GitHub metrics are routed into the OpenShift metrics store.
  - `AI Tutor Quality - Local` for local demo/test runs pushed into the same store.
- `ai-tutor-quality-grafana-provisioner` Job to create/update the Grafana datasource and dashboards through the Grafana API.
- `ai-tutor-quality-artifact-viewer` route for the latest Playwright report copied into OpenShift object storage.
- `ai-tutor-github-playwright-artifact-sync` CronJob, suspended by default until the GitHub read token is approved.

## Why Pushgateway Exists

Prometheus normally pulls metrics from long-running services.

AI Tutor test Jobs are short-lived. They run, publish results, and exit. A normal Prometheus scrape can miss them. Pushgateway gives those batch Jobs a place to push their final metrics so Prometheus can scrape the latest results after the Job exits.

This is only for test result metrics. Application metrics should use normal Prometheus scraping when available.

Pushgateway grouping is intentionally kept stable by `environment` and `repository`. It does not group by run id or commit sha because that would leave old batch results behind and make the dashboard look like stale failures are still current. Prometheus still keeps the time history for trend panels.

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
oc apply -f k8s/observability/52-local-dashboard.yaml -n rit-genai-naga-dev
oc apply -f k8s/observability/60-grafana-provisioner-job.yaml -n rit-genai-naga-dev
oc apply -f k8s/observability/70-github-metrics-sync.yaml -n rit-genai-naga-dev
oc apply -f k8s/observability/80-artifact-viewer.yaml -n rit-genai-naga-dev
oc apply -f k8s/observability/90-github-playwright-artifact-sync.yaml -n rit-genai-naga-dev
```

The Grafana Operator dashboard/datasource custom resources are kept in place, but dev showed that they can report success while Grafana itself still has no datasource. The provisioner Job is the reliable path for now: it uses the Grafana admin secret, creates the Prometheus datasource, imports the OpenShift/GitHub/Local dashboards, then exits.

If the provisioner Job already exists from an earlier manual run, delete only that completed Job and apply it again:

```bash
oc delete job ai-tutor-quality-grafana-provisioner -n rit-genai-naga-dev
oc apply -f k8s/observability/60-grafana-provisioner-job.yaml -n rit-genai-naga-dev
```

Then point the backend and frontend quality Jobs at Pushgateway:

```bash
oc apply -f k8s/quality-checks/job.yaml -n rit-genai-naga-dev
oc apply -f k8s/quality-checks/cronjob.yaml -n rit-genai-naga-dev
```

For frontend:

```bash
cd ../NAGA-open-webui
oc apply -f k8s/quality-checks/job.yaml -n rit-genai-naga-dev
oc apply -f k8s/quality-checks/cronjob.yaml -n rit-genai-naga-dev
```

## Access

Grafana is exposed through an OpenShift Route created by the Grafana Operator.

Check the URL:

```bash
oc get route -n rit-genai-naga-dev | grep ai-tutor-quality-grafana
```

The first version uses the Grafana Operator default admin secret. Before wider team sharing, confirm the access model with the platform/team owner.

## Retention Plan

Initial dev retention:

- Prometheus metrics: `15d`
- PostgreSQL detailed test history: planned next, target `90d`
- S3 artifacts: planned next, target `30d`

This folder implements the Prometheus/Grafana/bucket foundation first. PostgreSQL result tables and artifact upload wiring are the next step.

## Current Data Sources

- OpenShift scheduled Jobs can publish directly to `ai-tutor-quality-pushgateway`.
- Local runs can publish to Pushgateway when port-forwarded or run inside the cluster.
- GitHub Actions uploads Prometheus metrics as workflow artifacts. `ai-tutor-github-quality-metrics-sync` runs inside OpenShift, pulls the latest GitHub artifacts, and publishes them to the internal Pushgateway.

The GitHub sync needs a read-only GitHub token stored in OpenShift. Use a fine-grained token with read access to Actions/artifacts and metadata for `AI_Tutor_Analysis` and `NAGA-open-webui`.

```bash
oc create secret generic ai-tutor-github-metrics-sync-secret \
  -n rit-genai-naga-dev \
  --from-literal=GITHUB_TOKEN='<GITHUB_READ_TOKEN>' \
  --dry-run=client -o yaml | oc apply -f -
```

Then apply the sync definition. It is intentionally suspended by default so it will not run until the token is approved:

```bash
oc apply -f k8s/observability/70-github-metrics-sync.yaml -n rit-genai-naga-dev
```

After the token is approved, enable the schedule and optionally run one manual sync:

```bash
oc patch cronjob ai-tutor-github-quality-metrics-sync \
  -n rit-genai-naga-dev \
  --type=merge \
  -p '{"spec":{"suspend":false}}'

oc create job ai-tutor-github-quality-metrics-sync-manual \
  -n rit-genai-naga-dev \
  --from=cronjob/ai-tutor-github-quality-metrics-sync
```

## Artifact Direction

The ObjectBucketClaim stores Playwright HTML reports and videos in OpenShift-owned object storage.

The first artifact path syncs GitHub Playwright artifacts into the bucket. It is suspended until the same GitHub read token is approved:

```bash
oc apply -f k8s/observability/80-artifact-viewer.yaml -n rit-genai-naga-dev
oc apply -f k8s/observability/90-github-playwright-artifact-sync.yaml -n rit-genai-naga-dev
```

After token approval:

```bash
oc patch cronjob ai-tutor-github-playwright-artifact-sync \
  -n rit-genai-naga-dev \
  --type=merge \
  -p '{"spec":{"suspend":false}}'

oc create job ai-tutor-github-playwright-artifact-sync-manual \
  -n rit-genai-naga-dev \
  --from=cronjob/ai-tutor-github-playwright-artifact-sync
```

Get the artifact viewer URL:

```bash
oc get route ai-tutor-quality-artifacts -n rit-genai-naga-dev -o jsonpath='https://{.spec.host}{"\n"}'
```

The viewer shows the latest synced Playwright report. If no artifact has been synced yet, it will show an error until the first sync succeeds.
