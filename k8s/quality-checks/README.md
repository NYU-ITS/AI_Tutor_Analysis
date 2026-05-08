# AI Tutor Backend Build-Triggered Quality Checks on OpenShift

This runs AI Tutor backend deployed-environment checks from OpenShift whenever the dev backend app image is rebuilt.

It is intentionally not scheduled. The point is to answer: "Did this backend build still work from inside OpenShift dev?"

For the full local, GitHub Actions, and OpenShift testing picture, see:

- `../../AI_TUTOR_TESTING_OBSERVABILITY.md`
- `../observability/README.md`

## What It Creates

- `ai-tutor-quality-checks` backend test image build

The quality checks run as the `postCommit` hook of the quality-check image build. The build uses resources only while it runs, sends metrics to the OpenShift Pushgateway, then exits.

The quality-check BuildConfig has an `ImageChange` trigger on:

```text
open-webui-mastering-homework:latest
```

When the backend app BuildConfig pushes a new `open-webui-mastering-homework:latest` image, OpenShift starts `ai-tutor-quality-checks`. The quality build then runs the OpenShift smoke, integration, health, and external-service checks.

This is a lightweight BuildConfig-only automation. It removes the manual test trigger, but it is not a full deployment pipeline gate. The hook runs after the quality-check image is built, and the checks poll the deployed services. If strict "new image is fully rolled out before tests start" guarantees are required, use OpenShift Pipelines/Tekton or an ArgoCD post-sync hook.

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

## One-Time Setup

```bash
oc apply -f k8s/quality-checks/buildconfig.yaml -n rit-genai-naga-dev
```

## Automatic Build-Triggered Test Flow

After setup, the normal backend app build triggers these checks automatically:

```bash
oc start-build open-webui-mastering-homework --follow -n rit-genai-naga-dev
```

Expected OpenShift flow:

```text
open-webui-mastering-homework build finishes
open-webui-mastering-homework:latest image stream updates
ai-tutor-quality-checks build starts from the image-change trigger
ai-tutor-quality-checks postCommit runs scripts/run_openshift_quality_checks.sh
metrics are pushed to ai-tutor-quality-pushgateway
```

If the quality checks fail, the `ai-tutor-quality-checks` build fails and the logs show the pytest failure.

## Manual Validation

```bash
oc start-build ai-tutor-quality-checks --follow -n rit-genai-naga-dev
```

The older Job-based runner is still available for explicit reruns after a rollout:

```bash
bash scripts/run_post_deploy_quality_check.sh
```

The Job script runs these steps: wait for rollout, delete the previous completed Job, apply the Job manifest, wait for completion, and print logs.

## Grafana

After the Job finishes, the OpenShift Grafana dashboard reads the latest pushed metrics from the namespace Prometheus.

Useful PromQL checks:

```promql
ai_tutor_quality_checks_total{environment="openshift-dev",repository="AI_Tutor_Analysis"}
ai_tutor_quality_service_ok{environment="openshift-dev",repository="AI_Tutor_Analysis"}
ai_tutor_quality_group_checks_total{environment="openshift-dev",repository="AI_Tutor_Analysis"}
```
