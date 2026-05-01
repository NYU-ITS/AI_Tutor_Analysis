#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def required_env(name: str) -> str:
    value = env(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def yaml_string(value: str) -> str:
    return json.dumps(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a Prometheus config that forwards AI Tutor metrics to Grafana Cloud.")
    parser.add_argument("--output", required=True, help="Path to write the generated prometheus.yml file.")
    args = parser.parse_args()

    remote_write_url = required_env("GRAFANA_CLOUD_PROMETHEUS_URL")
    username = required_env("GRAFANA_CLOUD_PROMETHEUS_USER")
    password = required_env("GRAFANA_CLOUD_PROMETHEUS_PASSWORD")
    metrics_target = env("QUALITY_METRICS_TARGET", "host.docker.internal:9109")

    labels = {
        "environment": env("QUALITY_ENVIRONMENT", "local"),
        "repository": env("QUALITY_REPOSITORY", "AI_Tutor_Analysis"),
        "branch": env("QUALITY_BRANCH", "local"),
        "source": env("QUALITY_SOURCE", "local"),
        "run_id": env("QUALITY_RUN_ID", "local"),
        "commit_sha": env("QUALITY_COMMIT_SHA", "local"),
    }

    external_labels = "\n".join(f"    {key}: {yaml_string(value)}" for key, value in labels.items())

    config = f"""global:
  scrape_interval: 5s
  evaluation_interval: 5s
  external_labels:
{external_labels}

remote_write:
  - url: {yaml_string(remote_write_url)}
    basic_auth:
      username: {yaml_string(username)}
      password: {yaml_string(password)}

scrape_configs:
  - job_name: ai_tutor_quality_metrics
    static_configs:
      - targets:
          - {yaml_string(metrics_target)}
"""

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(config)
    output_path.chmod(0o600)


if __name__ == "__main__":
    main()
