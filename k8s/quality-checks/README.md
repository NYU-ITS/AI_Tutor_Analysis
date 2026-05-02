# AI Tutor OpenShift Quality Checks

This runs live AI Tutor checks from inside the OpenShift dev namespace and sends the result metrics to Grafana Cloud.

It does not deploy Grafana or Prometheus as long-running services.

## What It Creates

- `ai-tutor-quality-checks` image build
- one manual `Job`
- one hourly `CronJob`
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
oc create job ai-tutor-live-quality-check-$(date +%s) \
  --from=job/ai-tutor-live-quality-check \
  -n rit-genai-naga-dev
```

If the base Job has not been applied yet:

```bash
oc apply -f k8s/quality-checks/job.yaml -n rit-genai-naga-dev
```

Watch it:

```bash
oc get pods -n rit-genai-naga-dev | grep ai-tutor-live-quality
oc logs job/<job-name> -n rit-genai-naga-dev
```

## Hourly Schedule

```bash
oc apply -f k8s/quality-checks/cronjob.yaml -n rit-genai-naga-dev
```

This runs every hour.

## Grafana

After a job finishes, check Grafana Cloud with:

```promql
ai_tutor_quality_checks_total{environment="openshift-dev"}
```

Useful filters:

```promql
ai_tutor_quality_checks_total{source="openshift-live-checks"}
ai_tutor_quality_checks_total{source="openshift-live-checks-hourly"}
ai_tutor_quality_service_ok{environment="openshift-dev"}
```
