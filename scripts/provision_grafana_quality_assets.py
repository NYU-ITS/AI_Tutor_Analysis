#!/usr/bin/env python3

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml


DATASOURCE_UID = "ai_tutor_quality_prometheus"


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def request_json(method: str, base_url: str, path: str, user: str, password: str, payload: dict | None = None) -> tuple[int, object]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    auth = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            parsed: object = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed


def provision_datasource(grafana_url: str, user: str, password: str, prometheus_url: str) -> None:
    payload = {
        "name": "AI Tutor Quality Prometheus",
        "uid": DATASOURCE_UID,
        "type": "prometheus",
        "access": "proxy",
        "url": prometheus_url,
        "isDefault": True,
        "editable": True,
        "jsonData": {"timeInterval": "30s"},
    }

    status, _ = request_json("GET", grafana_url, f"/api/datasources/uid/{DATASOURCE_UID}", user, password)
    if status == 200:
        status, response = request_json("PUT", grafana_url, f"/api/datasources/uid/{DATASOURCE_UID}", user, password, payload)
    else:
        status, response = request_json("POST", grafana_url, "/api/datasources", user, password, payload)

    if status not in {200, 201}:
        raise SystemExit(f"Failed to provision datasource: HTTP {status}: {response}")
    print("Provisioned Grafana datasource: AI Tutor Quality Prometheus")


def dashboard_payload(path: Path) -> dict:
    document = yaml.safe_load(path.read_text())
    dashboard = json.loads(document["spec"]["json"])
    return {
        "dashboard": dashboard,
        "overwrite": True,
        "folderUid": "",
        "message": "Provisioned by AI Tutor OpenShift setup",
    }


def provision_dashboards(grafana_url: str, user: str, password: str, dashboard_paths: list[Path]) -> None:
    for path in dashboard_paths:
        status, response = request_json("POST", grafana_url, "/api/dashboards/db", user, password, dashboard_payload(path))
        if status not in {200, 201}:
            raise SystemExit(f"Failed to provision dashboard {path}: HTTP {status}: {response}")
        title = response.get("slug") if isinstance(response, dict) else path.name
        print(f"Provisioned Grafana dashboard: {title}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision AI Tutor Grafana datasource and dashboards.")
    parser.add_argument("--grafana-url", default=env("GRAFANA_URL", "http://ai-tutor-quality-grafana-service:3000"))
    parser.add_argument("--prometheus-url", default=env("PROMETHEUS_URL", "http://ai-tutor-quality-prometheus:9090"))
    parser.add_argument(
        "--dashboard-yaml",
        action="append",
        default=[
            "k8s/observability/50-grafana-dashboard.yaml",
            "k8s/observability/51-github-dashboard.yaml",
            "k8s/observability/52-local-dashboard.yaml",
        ],
    )
    args = parser.parse_args()

    user = env("GRAFANA_USER")
    password = env("GRAFANA_PASSWORD")
    dashboard_paths = [Path(path) for path in args.dashboard_yaml]
    missing = [str(path) for path in dashboard_paths if not path.exists()]
    if missing:
        raise SystemExit(f"Missing dashboard files: {', '.join(missing)}")

    provision_datasource(args.grafana_url, user, password, args.prometheus_url)
    provision_dashboards(args.grafana_url, user, password, dashboard_paths)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"Grafana provisioning failed: {exc}", file=sys.stderr)
        raise
