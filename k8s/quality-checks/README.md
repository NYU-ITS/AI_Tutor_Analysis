# AI Tutor Backend Post-Deployment Quality Checks on OpenShift

This runs AI Tutor backend checks after the OpenShift dev backend deployment is rebuilt and rolled out.

It is intentionally not scheduled. The point is to answer: "Did this newly deployed backend work from inside OpenShift dev?"

For the full local, GitHub Actions, and OpenShift testing picture, see:

- `../../AI_TUTOR_TESTING_OBSERVABILITY.md`
- `../observability/README.md`

## What It Creates

- `ai-tutor-quality-checks` backend test image build
- one short-lived backend `Job`: `ai-tutor-backend-post-deploy-quality-check`

The Job uses resources only while it runs, sends metrics to the OpenShift Pushgateway, then exits.

## What It Checks

- `smoke`: deployed backend and frontend routes respond without server errors
- `integration`: deployed backend API contract checks through read-only endpoints
- `health`: backend health endpoint, frontend health route, database connectivity, Portkey credential/gateway check
- `external_service`: Portkey AI gateway, OpenWebUI database, and pipeline database checks

The OpenShift runner uses:

```bash
pytest --noconftest tests/live -m "live and (smoke or integration or health or external_service)"
```

`QUALITY_STRICT_LIVE_CHECKS=1` is enabled in OpenShift so missing required configuration, such as a Portkey key or database URL, is reported as a failed quality signal instead of being silently skipped.

## One-Time Build Setup

```bash
oc apply -f k8s/quality-checks/buildconfig.yaml -n rit-genai-naga-dev
oc start-build ai-tutor-quality-checks --follow -n rit-genai-naga-dev
```

## Build, Deploy, and Test

This uses the current user's OpenShift permissions. It starts the backend quality image build, starts the backend app build, waits for rollout, runs the quality Job, sends metrics, and exits.

```bash
bash scripts/run_backend_build_deploy_quality_check.sh
```

If the backend was already rebuilt and you only want to run the post-deployment check:

```bash
bash scripts/run_post_deploy_quality_check.sh
```

The script runs these steps: wait for rollout, delete the previous completed Job, apply the Job manifest, wait for completion, and print logs.

## Grafana

After the Job finishes, the OpenShift Grafana dashboard reads the latest pushed metrics from the namespace Prometheus.

Useful PromQL checks:

```promql
ai_tutor_quality_checks_total{environment="openshift-dev",repository="AI_Tutor_Analysis"}
ai_tutor_quality_service_ok{environment="openshift-dev",repository="AI_Tutor_Analysis"}
ai_tutor_quality_group_checks_total{environment="openshift-dev",repository="AI_Tutor_Analysis"}
```
