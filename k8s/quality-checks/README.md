# AI Tutor Backend Scheduled Quality Checks on OpenShift

This runs scheduled AI Tutor backend checks from inside the OpenShift dev namespace and sends the result metrics to Grafana Cloud.

These checks touch the dev deployment and external backend dependencies, so the name uses `scheduled` instead of `live`. That avoids confusing scheduled dev checks with real production/live user traffic.

It does not deploy Grafana or Prometheus as long-running services.

## What It Creates

- `ai-tutor-quality-checks` backend test image build
- one manual backend `Job`: `ai-tutor-backend-scheduled-quality-check`
- one daily backend `CronJob`: `ai-tutor-backend-scheduled-quality-checks`
- one Grafana Cloud secret

The Job/CronJob pods are short-lived. They run checks, send metrics, and exit.

## Before Applying

Do not put real Grafana Cloud tokens in git.

Create or update the OpenShift Secret from environment variables:

```bash
export GRAFANA_CLOUD_PROMETHEUS_URL="https://prometheus-prod-56-prod-us-east-2.grafana.net/api/prom/push"
export GRAFANA_CLOUD_PROMETHEUS_USER="<grafana-cloud-prometheus-user>"
export GRAFANA_CLOUD_PROMETHEUS_PASSWORD="<grafana-cloud-prometheus-token>"

bash scripts/create_openshift_grafana_cloud_secret.sh
```

This creates/updates:

```text
ai-tutor-grafana-cloud-secret
```

The checked-in `secret.example.yaml` is only a reference template.

## One-Time Setup

```bash
oc apply -f k8s/quality-checks/buildconfig.yaml -n rit-genai-naga-dev
oc start-build ai-tutor-quality-checks --follow -n rit-genai-naga-dev
```

Create the Grafana Cloud secret:

```bash
bash scripts/create_openshift_grafana_cloud_secret.sh
```

## Manual Test Run

```bash
oc create job ai-tutor-backend-scheduled-quality-check-$(date +%s) \
  --from=job/ai-tutor-backend-scheduled-quality-check \
  -n rit-genai-naga-dev
```

If the base Job has not been applied yet:

```bash
oc apply -f k8s/quality-checks/job.yaml -n rit-genai-naga-dev
```

Watch it:

```bash
oc get pods -n rit-genai-naga-dev | grep ai-tutor-backend-scheduled-quality
oc logs job/<job-name> -n rit-genai-naga-dev
```

## Daily Schedule

```bash
oc apply -f k8s/quality-checks/cronjob.yaml -n rit-genai-naga-dev
```

This runs daily at 1:00 AM New York time.

## Grafana

After a job finishes, check Grafana Cloud with:

```promql
ai_tutor_quality_checks_total{environment="openshift-dev"}
```

Useful filters:

```promql
ai_tutor_quality_checks_total{source="openshift-backend-scheduled-checks"}
ai_tutor_quality_service_ok{environment="openshift-dev"}
```
