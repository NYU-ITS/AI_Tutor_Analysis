#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


def _suite_for_testcase(testcase: ET.Element) -> str:
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


def _quote_label(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _metric_line(name: str, value: float | int, labels: dict[str, str] | None = None) -> str:
    if labels:
        encoded = ",".join(f'{key}={_quote_label(val)}' for key, val in sorted(labels.items()))
        return f"{name}{{{encoded}}} {value}"
    return f"{name} {value}"


def _iter_testcases(root: ET.Element) -> Iterable[ET.Element]:
    return root.iterfind(".//testcase")


def build_metrics(results_path: Path, coverage_path: Path | None) -> tuple[str, dict[str, object]]:
    lines = [
        "# HELP ai_tutor_pytest_results_available Whether the pytest result file is available.",
        "# TYPE ai_tutor_pytest_results_available gauge",
    ]
    summary: dict[str, object] = {
        "results_available": False,
        "tests": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
        "duration_seconds": 0.0,
        "coverage_percent": None,
        "suite_counts": {},
    }

    if not results_path.exists():
        lines.append(_metric_line("ai_tutor_pytest_results_available", 0))
        return "\n".join(lines) + "\n", summary

    root = ET.parse(results_path).getroot()
    tests = 0
    passed = 0
    failed = 0
    skipped = 0
    errors = 0
    duration_seconds = 0.0
    suite_counts: dict[str, Counter[str]] = defaultdict(Counter)

    lines.extend(
        [
            "# HELP ai_tutor_pytest_run_timestamp_seconds Last modification time of the pytest JUnit file.",
            "# TYPE ai_tutor_pytest_run_timestamp_seconds gauge",
            _metric_line("ai_tutor_pytest_results_available", 1),
            "# HELP ai_tutor_pytest_duration_seconds Total duration of the last pytest run.",
            "# TYPE ai_tutor_pytest_duration_seconds gauge",
            "# HELP ai_tutor_pytest_tests_total Test counts grouped by status.",
            "# TYPE ai_tutor_pytest_tests_total gauge",
            "# HELP ai_tutor_pytest_suite_tests_total Test counts grouped by suite and status.",
            "# TYPE ai_tutor_pytest_suite_tests_total gauge",
            "# HELP ai_tutor_pytest_testcase_duration_seconds Duration of each testcase in the last pytest run.",
            "# TYPE ai_tutor_pytest_testcase_duration_seconds gauge",
            _metric_line("ai_tutor_pytest_run_timestamp_seconds", results_path.stat().st_mtime),
        ]
    )

    for testcase in _iter_testcases(root):
        tests += 1
        suite = _suite_for_testcase(testcase)
        duration_seconds += float(testcase.get("time", "0") or 0)
        status = "passed"
        if testcase.find("failure") is not None:
            status = "failed"
            failed += 1
        elif testcase.find("error") is not None:
            status = "error"
            errors += 1
        elif testcase.find("skipped") is not None:
            status = "skipped"
            skipped += 1
        else:
            passed += 1

        suite_counts[suite][status] += 1
        lines.append(
            _metric_line(
                "ai_tutor_pytest_testcase_duration_seconds",
                float(testcase.get("time", "0") or 0),
                {
                    "suite": suite,
                    "classname": testcase.get("classname", ""),
                    "name": testcase.get("name", ""),
                    "status": status,
                },
            )
        )

    lines.append(_metric_line("ai_tutor_pytest_duration_seconds", duration_seconds))
    for status, value in {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "error": errors,
        "total": tests,
    }.items():
        lines.append(_metric_line("ai_tutor_pytest_tests_total", value, {"status": status}))

    for suite, counts in sorted(suite_counts.items()):
        total_for_suite = sum(counts.values())
        lines.append(_metric_line("ai_tutor_pytest_suite_tests_total", total_for_suite, {"suite": suite, "status": "total"}))
        for status, value in sorted(counts.items()):
            lines.append(_metric_line("ai_tutor_pytest_suite_tests_total", value, {"suite": suite, "status": status}))

    coverage_percent = None
    if coverage_path and coverage_path.exists():
        coverage_root = ET.parse(coverage_path).getroot()
        line_rate = float(coverage_root.get("line-rate", "0") or 0)
        coverage_percent = round(line_rate * 100, 2)
        lines.extend(
            [
                "# HELP ai_tutor_pytest_coverage_percent Line coverage percentage from coverage.xml.",
                "# TYPE ai_tutor_pytest_coverage_percent gauge",
                _metric_line("ai_tutor_pytest_coverage_percent", coverage_percent),
            ]
        )

    summary.update(
        {
            "results_available": True,
            "tests": tests,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "duration_seconds": round(duration_seconds, 3),
            "coverage_percent": coverage_percent,
            "suite_counts": {suite: dict(counter) for suite, counter in suite_counts.items()},
        }
    )
    return "\n".join(lines) + "\n", summary


def build_html(summary: dict[str, object], results_path: Path, coverage_path: Path | None) -> str:
    coverage_text = "n/a" if summary["coverage_percent"] is None else f'{summary["coverage_percent"]}%'
    suite_rows = []
    suite_counts = summary.get("suite_counts", {})
    for suite, counts in sorted(suite_counts.items()):
        suite_rows.append(
            "<tr>"
            f"<td>{html.escape(str(suite))}</td>"
            f"<td>{counts.get('passed', 0)}</td>"
            f"<td>{counts.get('failed', 0)}</td>"
            f"<td>{counts.get('skipped', 0)}</td>"
            f"<td>{counts.get('error', 0)}</td>"
            f"<td>{sum(counts.values())}</td>"
            "</tr>"
        )
    suite_table = "\n".join(suite_rows) or "<tr><td colspan='6'>No test data yet.</td></tr>"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AI Tutor Test Metrics</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 32px; color: #111827; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; max-width: 920px; }}
    .card {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 16px; }}
    .label {{ font-size: 12px; color: #6b7280; text-transform: uppercase; }}
    .value {{ font-size: 28px; margin-top: 8px; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 920px; margin-top: 24px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 10px; text-align: left; }}
    th {{ background: #f9fafb; }}
    code {{ background: #f3f4f6; padding: 2px 5px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>AI Tutor pytest metrics</h1>
  <p>Exporter is reading <code>{html.escape(str(results_path))}</code>{'' if coverage_path is None else f' and <code>{html.escape(str(coverage_path))}</code>'}.</p>
  <div class="stats">
    <div class="card"><div class="label">Tests</div><div class="value">{summary['tests']}</div></div>
    <div class="card"><div class="label">Passed</div><div class="value">{summary['passed']}</div></div>
    <div class="card"><div class="label">Failed</div><div class="value">{summary['failed']}</div></div>
    <div class="card"><div class="label">Skipped</div><div class="value">{summary['skipped']}</div></div>
    <div class="card"><div class="label">Errors</div><div class="value">{summary['errors']}</div></div>
    <div class="card"><div class="label">Coverage</div><div class="value">{coverage_text}</div></div>
    <div class="card"><div class="label">Duration</div><div class="value">{summary['duration_seconds']}s</div></div>
  </div>
  <table>
    <thead>
      <tr><th>Suite</th><th>Passed</th><th>Failed</th><th>Skipped</th><th>Errors</th><th>Total</th></tr>
    </thead>
    <tbody>
      {suite_table}
    </tbody>
  </table>
  <p style="margin-top: 24px;">Machine-readable metrics are available at <a href="/metrics"><code>/metrics</code></a>.</p>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve pytest JUnit and coverage metrics for Prometheus/Grafana.")
    parser.add_argument("--results", default="test-results/results.xml", help="Path to pytest JUnit XML results.")
    parser.add_argument("--coverage", default="test-results/coverage.xml", help="Path to coverage XML report.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    parser.add_argument("--port", default=9109, type=int, help="Port to bind.")
    args = parser.parse_args()

    results_path = Path(args.results).resolve()
    coverage_path = Path(args.coverage).resolve()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            metrics, summary = build_metrics(results_path, coverage_path)
            if self.path == "/metrics":
                payload = metrics.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if self.path in {"/", "/healthz"}:
                html_payload = build_html(summary, results_path, coverage_path).encode("utf-8")
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
    print(f"Serving test metrics on http://{args.host}:{args.port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
