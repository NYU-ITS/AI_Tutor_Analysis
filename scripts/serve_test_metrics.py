#!/usr/bin/env python3

from __future__ import annotations

import argparse
import base64
import html
import io
import json
import mimetypes
import re
import zipfile
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Iterable
from xml.etree import ElementTree as ET


LIVE_GROUP_LABELS = {
    "api_smoke": "Deployed backend",
    "external_service": "Connected services",
}

LIVE_SERVICE_LABELS = {
    "backend_app": "Analytics backend",
    "backend_api": "Tutor dashboard backend",
    "openwebui_db": "OpenWebUI database",
    "pipeline_db": "Pipeline database",
    "portkey": "Portkey AI gateway",
    "unknown": "Other dependency",
}

LIVE_CHECK_LABELS = {
    "test_health_endpoint_returns_ok": "Health check responds",
    "test_docs_ui_loads": "API documentation opens",
    "test_openapi_document_loads": "API schema loads",
    "test_general_prompts_endpoint_responds": "Prompt list is available",
    "test_pipeline_jobs_endpoint_responds": "Pipeline job list responds",
    "test_homework_endpoint_responds": "Homework list responds",
    "test_conversation_endpoint_responds": "Conversation list responds",
    "test_analysis_endpoint_responds": "Analysis list responds",
    "test_practice_endpoint_responds": "Practice list responds",
    "test_assignment_endpoint_responds": "Assignment list responds",
    "test_db_connection_works": "Database connection works",
    "test_user_table_has_rows": "User records exist",
    "test_group_table_has_rows": "Group records exist",
    "test_chat_table_has_rows": "Chat records exist",
    "test_group_has_user_ids": "Group membership is populated",
    "test_chat_has_expected_json_structure": "Chat payload shape is valid",
    "test_seed_prompts_exist": "Default prompts are seeded",
    "test_tables_exist": "Expected tables exist",
    "test_portkey_api_key_is_valid": "Gateway accepts credentials",
    "test_portkey_returns_nonempty_response_via_ask": "Gateway returns text",
    "test_portkey_json_response_format": "Gateway returns valid JSON",
    "test_portkey_system_prompt_works": "Gateway respects system prompts",
}

PLAYWRIGHT_GROUP_LABELS = {
    "ui_live": "Live user workflows",
    "ui_mocked": "Controlled UI workflows",
}


def _quote_label(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _metric_line(name: str, value: float | int, labels: dict[str, str] | None = None) -> str:
    if labels:
        encoded = ",".join(f'{key}={_quote_label(val)}' for key, val in sorted(labels.items()))
        return f"{name}{{{encoded}}} {value}"
    return f"{name} {value}"


def _iter_testcases(root: ET.Element) -> Iterable[ET.Element]:
    return root.iterfind(".//testcase")


def _pytest_suite_for_testcase(testcase: ET.Element) -> str:
    classname = testcase.get("classname", "")
    file_attr = testcase.get("file", "")
    hint = f"{classname} {file_attr}".lower()
    if "tests/unit" in hint or ".unit." in hint:
        return "unit"
    if "tests/integration" in hint or ".integration." in hint:
        return "integration"
    if "tests/live" in hint or ".live." in hint:
        return "live"
    return "unknown"


def _live_service_for_testcase(testcase: ET.Element) -> tuple[str, str]:
    hint = f'{testcase.get("classname", "")} {testcase.get("name", "")}'.lower()
    if "api_smoke" in hint:
        return "api_smoke", "backend_api"
    if "openwebui_db" in hint:
        return "external_service", "openwebui_db"
    if "pipeline_db" in hint:
        return "external_service", "pipeline_db"
    if "portkey" in hint:
        return "external_service", "portkey"
    return "external_service", "unknown"


def _display_check_name(testcase: ET.Element) -> str:
    raw_name = testcase.get("name", "")
    return LIVE_CHECK_LABELS.get(raw_name, raw_name.replace("_", " "))


def _status_for_testcase(testcase: ET.Element) -> str:
    if testcase.find("failure") is not None:
        return "failed"
    if testcase.find("error") is not None:
        return "error"
    if testcase.find("skipped") is not None:
        return "skipped"
    return "passed"


def _empty_source_summary(source: str, display_name: str) -> dict[str, object]:
    return {
        "source": source,
        "display_name": display_name,
        "available": False,
        "ok": False,
        "tests": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
        "duration_seconds": 0.0,
        "timestamp": None,
        "coverage_percent": None,
        "groups": {},
    }


def _emit_source_metrics(lines: list[str], summary: dict[str, object]) -> None:
    source = str(summary["source"])
    lines.append(_metric_line("ai_tutor_quality_source_available", 1 if summary["available"] else 0, {"source": source}))
    lines.append(_metric_line("ai_tutor_quality_source_ok", 1 if summary["ok"] else 0, {"source": source}))
    lines.append(
        _metric_line(
            "ai_tutor_quality_source_duration_seconds",
            float(summary["duration_seconds"]),
            {"source": source},
        )
    )
    if summary["timestamp"] is not None:
        lines.append(
            _metric_line(
                "ai_tutor_quality_source_last_run_timestamp_seconds",
                float(summary["timestamp"]),
                {"source": source},
            )
        )
    for status, value in {
        "passed": summary["passed"],
        "failed": summary["failed"],
        "skipped": summary["skipped"],
        "error": summary["errors"],
        "total": summary["tests"],
    }.items():
        lines.append(_metric_line("ai_tutor_quality_checks_total", int(value), {"source": source, "status": status}))
    for group, counts in sorted(summary["groups"].items()):
        lines.append(
            _metric_line(
                "ai_tutor_quality_group_checks_total",
                sum(counts.values()),
                {"source": source, "group": group, "status": "total"},
            )
        )
        for status, value in sorted(counts.items()):
            lines.append(
                _metric_line(
                    "ai_tutor_quality_group_checks_total",
                    value,
                    {"source": source, "group": group, "status": status},
                )
            )

    for service, counts in sorted(summary.get("services", {}).items()):
        lines.append(
            _metric_line(
                "ai_tutor_quality_service_checks_total",
                sum(counts.values()),
                {"source": source, "service": service, "status": "total"},
            )
        )
        for status, value in sorted(counts.items()):
            lines.append(
                _metric_line(
                    "ai_tutor_quality_service_checks_total",
                    value,
                    {"source": source, "service": service, "status": status},
                )
            )
        lines.append(
            _metric_line(
                "ai_tutor_quality_service_ok",
                1 if counts.get("failed", 0) == 0 and counts.get("error", 0) == 0 and sum(counts.values()) > 0 else 0,
                {"source": source, "service": service},
            )
        )


def _parse_junit_report(
    results_path: Path,
    *,
    source: str,
    display_name: str,
    group_service_mapper: Callable[[ET.Element], tuple[str, str]],
    coverage_path: Path | None = None,
    include_legacy_pytest_metrics: bool = False,
) -> tuple[list[str], dict[str, object]]:
    lines: list[str] = []
    summary = _empty_source_summary(source, display_name)

    if not results_path.exists():
        _emit_source_metrics(lines, summary)
        return lines, summary

    root = ET.parse(results_path).getroot()
    duration_seconds = 0.0
    group_counts: dict[str, Counter[str]] = defaultdict(Counter)
    service_counts: dict[str, Counter[str]] = defaultdict(Counter)
    passed = failed = skipped = errors = tests = 0
    legacy_suite_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for testcase in _iter_testcases(root):
        tests += 1
        status = _status_for_testcase(testcase)
        duration = float(testcase.get("time", "0") or 0)
        duration_seconds += duration
        if status == "passed":
            passed += 1
        elif status == "failed":
            failed += 1
        elif status == "skipped":
            skipped += 1
        else:
            errors += 1

        group, service = group_service_mapper(testcase)
        display_group = LIVE_GROUP_LABELS.get(group, PLAYWRIGHT_GROUP_LABELS.get(group, group))
        display_service = LIVE_SERVICE_LABELS.get(service, service)
        display_name = _display_check_name(testcase)
        group_counts[display_group][status] += 1
        service_counts[display_service][status] += 1
        lines.append(
            _metric_line(
                "ai_tutor_quality_check_duration_seconds",
                duration,
                {
                    "source": source,
                    "group": display_group,
                    "service": display_service,
                    "classname": testcase.get("classname", ""),
                    "name": display_name,
                    "status": status,
                },
            )
        )

        if include_legacy_pytest_metrics:
            suite = _pytest_suite_for_testcase(testcase)
            legacy_suite_counts[suite][status] += 1
            lines.append(
                _metric_line(
                    "ai_tutor_pytest_testcase_duration_seconds",
                    duration,
                    {
                        "suite": suite,
                        "classname": testcase.get("classname", ""),
                        "name": testcase.get("name", ""),
                        "status": status,
                    },
                )
            )

    summary.update(
        {
            "available": True,
            "ok": failed == 0 and errors == 0 and tests > 0,
            "tests": tests,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "duration_seconds": round(duration_seconds, 3),
            "timestamp": results_path.stat().st_mtime,
            "groups": {group: dict(counter) for group, counter in group_counts.items()},
            "services": {service: dict(counter) for service, counter in service_counts.items()},
        }
    )

    _emit_source_metrics(lines, summary)

    if include_legacy_pytest_metrics:
        lines.extend(
            [
                _metric_line("ai_tutor_pytest_results_available", 1),
                _metric_line("ai_tutor_pytest_run_timestamp_seconds", results_path.stat().st_mtime),
                _metric_line("ai_tutor_pytest_duration_seconds", duration_seconds),
            ]
        )
        for status, value in {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "error": errors,
            "total": tests,
        }.items():
            lines.append(_metric_line("ai_tutor_pytest_tests_total", value, {"status": status}))
        for suite, counts in sorted(legacy_suite_counts.items()):
            lines.append(_metric_line("ai_tutor_pytest_suite_tests_total", sum(counts.values()), {"suite": suite, "status": "total"}))
            for status, value in sorted(counts.items()):
                lines.append(_metric_line("ai_tutor_pytest_suite_tests_total", value, {"suite": suite, "status": status}))

        coverage_percent = None
        if coverage_path and coverage_path.exists():
            coverage_root = ET.parse(coverage_path).getroot()
            line_rate = float(coverage_root.get("line-rate", "0") or 0)
            coverage_percent = round(line_rate * 100, 2)
            lines.append(_metric_line("ai_tutor_pytest_coverage_percent", coverage_percent))
            summary["coverage_percent"] = coverage_percent
        else:
            summary["coverage_percent"] = None

    return lines, summary


def _parse_playwright_report(report_path: Path) -> tuple[list[str], dict[str, object]]:
    source = "playwright_ui"
    lines: list[str] = []
    summary = _empty_source_summary(source, "Playwright UI Journeys")

    if not report_path.exists():
        _emit_source_metrics(lines, summary)
        return lines, summary

    text = report_path.read_text(errors="ignore")
    match = re.search(r'<template id="playwrightReportBase64">data:application/zip;base64,(.*?)</template>', text, re.S)
    if not match:
        _emit_source_metrics(lines, summary)
        return lines, summary

    raw = base64.b64decode(match.group(1))
    archive = zipfile.ZipFile(io.BytesIO(raw))
    report = json.loads(archive.read("report.json"))

    passed = failed = skipped = errors = tests = 0
    duration_seconds = round(float(report.get("duration", 0)) / 1000, 3)
    groups: dict[str, Counter[str]] = defaultdict(Counter)

    for file_entry in report.get("files", []):
        file_name = file_entry.get("fileName", "")
        for test in file_entry.get("tests", []):
            tests += 1
            outcome = test.get("outcome", "")
            if test.get("ok") and outcome == "expected":
                status = "passed"
                passed += 1
            elif outcome == "skipped":
                status = "skipped"
                skipped += 1
            else:
                status = "failed"
                failed += 1

            project = test.get("projectName", "unknown")
            workflow = test.get("title", "")
            duration = round(float(test.get("duration", 0)) / 1000, 3)
            journey_group = "ui_live" if "live.spec" in file_name else "ui_mocked"
            display_group = PLAYWRIGHT_GROUP_LABELS[journey_group]
            groups[display_group][status] += 1

            lines.append(
                _metric_line(
                    "ai_tutor_quality_check_duration_seconds",
                    duration,
                    {
                        "source": source,
                        "group": display_group,
                        "service": project,
                        "classname": file_name,
                        "name": workflow,
                        "status": status,
                    },
                )
            )
            lines.append(
                _metric_line(
                    "ai_tutor_playwright_workflow_duration_seconds",
                    duration,
                    {
                        "group": display_group,
                        "project": project,
                        "workflow": workflow,
                        "status": status,
                    },
                )
            )

    stats = report.get("stats", {})
    summary.update(
        {
            "available": True,
            "ok": bool(stats.get("ok", failed == 0)),
            "tests": tests,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "duration_seconds": duration_seconds,
            "timestamp": report_path.stat().st_mtime,
            "groups": {group: dict(counter) for group, counter in groups.items()},
            "services": {},
        }
    )
    _emit_source_metrics(lines, summary)

    lines.append(_metric_line("ai_tutor_playwright_results_available", 1))
    lines.append(_metric_line("ai_tutor_playwright_run_timestamp_seconds", report_path.stat().st_mtime))
    for status, value in {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "total": tests,
    }.items():
        lines.append(_metric_line("ai_tutor_playwright_tests_total", value, {"status": status}))

    return lines, summary


def build_metrics(
    results_path: Path,
    coverage_path: Path | None,
    live_results_path: Path | None,
    playwright_report_path: Path | None,
) -> tuple[str, dict[str, object]]:
    lines = [
        "# HELP ai_tutor_pytest_results_available Whether the pytest result file is available.",
        "# TYPE ai_tutor_pytest_results_available gauge",
        "# HELP ai_tutor_pytest_run_timestamp_seconds Last modification time of the pytest JUnit file.",
        "# TYPE ai_tutor_pytest_run_timestamp_seconds gauge",
        "# HELP ai_tutor_pytest_duration_seconds Total duration of the last pytest run.",
        "# TYPE ai_tutor_pytest_duration_seconds gauge",
        "# HELP ai_tutor_pytest_tests_total Test counts grouped by status.",
        "# TYPE ai_tutor_pytest_tests_total gauge",
        "# HELP ai_tutor_pytest_suite_tests_total Test counts grouped by suite and status.",
        "# TYPE ai_tutor_pytest_suite_tests_total gauge",
        "# HELP ai_tutor_pytest_testcase_duration_seconds Duration of each testcase in the last pytest run.",
        "# TYPE ai_tutor_pytest_testcase_duration_seconds gauge",
        "# HELP ai_tutor_pytest_coverage_percent Line coverage percentage from coverage.xml.",
        "# TYPE ai_tutor_pytest_coverage_percent gauge",
        "# HELP ai_tutor_quality_source_available Whether a quality signal is available.",
        "# TYPE ai_tutor_quality_source_available gauge",
        "# HELP ai_tutor_quality_source_ok Whether the latest quality signal is passing cleanly.",
        "# TYPE ai_tutor_quality_source_ok gauge",
        "# HELP ai_tutor_quality_source_duration_seconds Total duration of the latest quality signal.",
        "# TYPE ai_tutor_quality_source_duration_seconds gauge",
        "# HELP ai_tutor_quality_source_last_run_timestamp_seconds Last run time for a quality signal.",
        "# TYPE ai_tutor_quality_source_last_run_timestamp_seconds gauge",
        "# HELP ai_tutor_quality_checks_total Count of checks by quality source and status.",
        "# TYPE ai_tutor_quality_checks_total gauge",
        "# HELP ai_tutor_quality_group_checks_total Count of checks by quality source, group, and status.",
        "# TYPE ai_tutor_quality_group_checks_total gauge",
        "# HELP ai_tutor_quality_service_checks_total Count of checks by quality source, service, and status.",
        "# TYPE ai_tutor_quality_service_checks_total gauge",
        "# HELP ai_tutor_quality_service_ok Whether the latest checks for a service are all passing.",
        "# TYPE ai_tutor_quality_service_ok gauge",
        "# HELP ai_tutor_quality_check_duration_seconds Duration of an individual quality check.",
        "# TYPE ai_tutor_quality_check_duration_seconds gauge",
        "# HELP ai_tutor_playwright_results_available Whether the Playwright report is available.",
        "# TYPE ai_tutor_playwright_results_available gauge",
        "# HELP ai_tutor_playwright_run_timestamp_seconds Last modification time of the Playwright report.",
        "# TYPE ai_tutor_playwright_run_timestamp_seconds gauge",
        "# HELP ai_tutor_playwright_tests_total Playwright test counts grouped by status.",
        "# TYPE ai_tutor_playwright_tests_total gauge",
        "# HELP ai_tutor_playwright_workflow_duration_seconds Duration of each Playwright workflow result.",
        "# TYPE ai_tutor_playwright_workflow_duration_seconds gauge",
    ]

    pytest_lines, pytest_summary = _parse_junit_report(
        results_path,
        source="backend_regression",
        display_name="Backend Regression",
        group_service_mapper=lambda testcase: (_pytest_suite_for_testcase(testcase), "backend_app"),
        coverage_path=coverage_path,
        include_legacy_pytest_metrics=True,
    )
    lines.extend(pytest_lines)

    if live_results_path is not None:
        live_lines, live_summary = _parse_junit_report(
            live_results_path,
            source="live_observability",
            display_name="Live Services and API",
            group_service_mapper=_live_service_for_testcase,
        )
    else:
        live_lines, live_summary = [], _empty_source_summary("live_observability", "Live Services and API")
        _emit_source_metrics(live_lines, live_summary)
    lines.extend(live_lines)

    if playwright_report_path is not None:
        playwright_lines, playwright_summary = _parse_playwright_report(playwright_report_path)
    else:
        playwright_lines, playwright_summary = [], _empty_source_summary("playwright_ui", "Playwright UI Journeys")
        _emit_source_metrics(playwright_lines, playwright_summary)
    lines.extend(playwright_lines)

    summary = {
        "backend_regression": pytest_summary,
        "live_observability": live_summary,
        "playwright_ui": playwright_summary,
    }
    return "\n".join(lines) + "\n", summary


def build_html(summary: dict[str, object], results_path: Path, coverage_path: Path | None, live_results_path: Path | None, playwright_report_path: Path | None) -> str:
    cards = []
    for source in ("backend_regression", "live_observability", "playwright_ui"):
        data = summary[source]
        coverage_text = ""
        if data.get("coverage_percent") is not None:
            coverage_text = f"<div class='meta'>Coverage: {data['coverage_percent']}%</div>"
        status_text = "Passing" if data["ok"] else ("No data" if not data["available"] else "Needs attention")
        cards.append(
            "<div class='card'>"
            f"<div class='label'>{html.escape(str(data['display_name']))}</div>"
            f"<div class='value'>{html.escape(status_text)}</div>"
            f"<div class='meta'>Tests: {data['tests']} | Passed: {data['passed']} | Failed: {data['failed']} | Skipped: {data['skipped']}</div>"
            f"<div class='meta'>Duration: {data['duration_seconds']}s</div>"
            f"{coverage_text}"
            "</div>"
        )

    info_rows = [
        ("Backend regression report", results_path),
        ("Coverage report", coverage_path),
        ("Live checks report", live_results_path),
        ("Playwright report", playwright_report_path),
    ]
    path_rows = []
    for label, path in info_rows:
        path_rows.append(
            f"<tr><td>{html.escape(label)}</td><td><code>{html.escape(str(path.resolve())) if path is not None else 'n/a'}</code></td></tr>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AI Tutor Quality Metrics</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 32px; color: #111827; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; max-width: 1100px; }}
    .card {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 16px; }}
    .label {{ font-size: 12px; color: #6b7280; text-transform: uppercase; }}
    .value {{ font-size: 28px; margin-top: 8px; }}
    .meta {{ margin-top: 8px; color: #374151; font-size: 14px; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 1100px; margin-top: 24px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 10px; text-align: left; }}
    th {{ background: #f9fafb; }}
    code {{ background: #f3f4f6; padding: 2px 5px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>AI Tutor quality metrics</h1>
  <p>This page summarizes three quality signals: backend regression tests, live service/API checks, and Playwright UI journeys.</p>
  <div class="stats">
    {''.join(cards)}
  </div>
  <table>
    <thead>
      <tr><th>Artifact</th><th>Path</th></tr>
    </thead>
    <tbody>
      {''.join(path_rows)}
    </tbody>
  </table>
  <p style="margin-top: 24px;">Machine-readable metrics are available at <a href="/metrics"><code>/metrics</code></a>.</p>
</body>
</html>
"""


def _safe_relative_path(base_dir: Path, request_path: str) -> Path | None:
    relative = request_path.lstrip("/")
    candidate = (base_dir / relative).resolve()
    try:
        candidate.relative_to(base_dir.resolve())
    except ValueError:
        return None
    return candidate if candidate.exists() else None


def _directory_listing(title: str, base_url: str, files: list[Path], root_dir: Path) -> str:
    rows = []
    for file_path in sorted(files):
        rel_path = file_path.relative_to(root_dir).as_posix()
        rows.append(
            f"<tr><td>{html.escape(rel_path)}</td><td><a href=\"{html.escape(base_url.rstrip('/') + '/' + rel_path)}\">Open</a></td></tr>"
        )
    body = "".join(rows) or "<tr><td colspan='2'>No files found.</td></tr>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 32px; color: #111827; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 1100px; margin-top: 24px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 10px; text-align: left; }}
    th {{ background: #f9fafb; }}
    a {{ color: #2563eb; text-decoration: none; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <table>
    <thead><tr><th>File</th><th>Open</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve pytest, live-check, and Playwright metrics for Prometheus/Grafana.")
    parser.add_argument("--results", default="test-results/results.xml", help="Path to non-live pytest JUnit XML results.")
    parser.add_argument("--coverage", default="test-results/coverage.xml", help="Path to non-live pytest coverage XML report.")
    parser.add_argument("--live-results", default="live-results/results.xml", help="Path to live pytest JUnit XML results.")
    parser.add_argument(
        "--playwright-report",
        default="../NAGA-open-webui/playwright-report/index.html",
        help="Path to the Playwright HTML report.",
    )
    parser.add_argument(
        "--playwright-videos-dir",
        default="../NAGA-open-webui/test-results",
        help="Path to the Playwright test-results directory containing recorded videos.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    parser.add_argument("--port", default=9109, type=int, help="Port to bind.")
    args = parser.parse_args()

    results_path = Path(args.results).resolve()
    coverage_path = Path(args.coverage).resolve()
    live_results_path = Path(args.live_results).resolve()
    playwright_report_path = Path(args.playwright_report).resolve()
    playwright_videos_dir = Path(args.playwright_videos_dir).resolve()
    playwright_report_dir = playwright_report_path.parent.resolve()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            metrics, summary = build_metrics(results_path, coverage_path, live_results_path, playwright_report_path)
            if self.path == "/metrics":
                payload = metrics.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if self.path in {"/playwright-report", "/playwright-report/"} and playwright_report_path.exists():
                payload = playwright_report_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if self.path.startswith("/playwright-report/"):
                asset = _safe_relative_path(playwright_report_dir, self.path.removeprefix("/playwright-report/"))
                if asset is not None:
                    payload = asset.read_bytes()
                    content_type = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
            if self.path in {"/playwright-videos", "/playwright-videos/"}:
                videos = sorted(playwright_videos_dir.rglob("video.webm")) if playwright_videos_dir.exists() else []
                payload = _directory_listing(
                    "Playwright videos",
                    "/playwright-videos",
                    videos,
                    playwright_videos_dir,
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if self.path.startswith("/playwright-videos/"):
                asset = _safe_relative_path(playwright_videos_dir, self.path.removeprefix("/playwright-videos/"))
                if asset is not None:
                    payload = asset.read_bytes()
                    content_type = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
            if self.path in {"/", "/healthz"}:
                html_payload = build_html(summary, results_path, coverage_path, live_results_path, playwright_report_path).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html_payload)))
                self.end_headers()
                self.wfile.write(html_payload)
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving quality metrics on http://{args.host}:{args.port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
