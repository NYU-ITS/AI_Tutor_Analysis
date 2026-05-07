FROM prom/prometheus:v3.2.1 AS prometheus

FROM python:3.12-slim

WORKDIR /workspace

COPY --from=prometheus /bin/prometheus /usr/local/bin/prometheus

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY student_analysis_pipeline/requirements.txt /tmp/app-requirements.txt
COPY tests/requirements-testing.txt /tmp/test-requirements.txt

RUN pip install --no-cache-dir -r /tmp/app-requirements.txt -r /tmp/test-requirements.txt

COPY student_analysis_pipeline ./student_analysis_pipeline
COPY tests ./tests
COPY pytest.ini ./pytest.ini
COPY scripts/serve_test_metrics.py scripts/write_grafana_cloud_prometheus_config.py scripts/run_openshift_quality_checks.sh scripts/provision_grafana_quality_assets.py scripts/sync_github_quality_metrics.py scripts/quality_artifact_store.py ./scripts/
COPY k8s/observability/50-grafana-dashboard.yaml k8s/observability/51-github-dashboard.yaml k8s/observability/52-local-dashboard.yaml ./k8s/observability/

RUN chmod +x ./scripts/run_openshift_quality_checks.sh ./scripts/write_grafana_cloud_prometheus_config.py ./scripts/provision_grafana_quality_assets.py ./scripts/sync_github_quality_metrics.py ./scripts/quality_artifact_store.py \
    && chgrp -R 0 /workspace \
    && chmod -R g=u /workspace

ENV HOME=/tmp

CMD ["bash", "scripts/run_openshift_quality_checks.sh"]
