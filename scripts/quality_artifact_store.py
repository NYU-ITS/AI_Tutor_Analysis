#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import hmac
import html
import json
import mimetypes
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import PurePosixPath


ARTIFACT_NAMES = ["playwright-report", "playwright-videos"]
BACKEND_GITHUB_ARTIFACT_NAME = "test-results"
SECRET_ENV_NAMES = {
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "DATABASE_URL",
    "GITHUB_TOKEN",
    "PIPELINE_DATABASE_URL",
    "PORTKEY_API_KEY",
}
SECRET_PATTERNS = [
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)((?:api[_-]?key|token|secret|password)\s*[=:]\s*)[^\s,;]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(postgres(?:ql)?://[^:\s/@]+:)[^@\s]+(@)"), r"\1[REDACTED]\2"),
    (re.compile(r"(?i)(https?://[^:\s/@]+:)[^@\s]+(@)"), r"\1[REDACTED]\2"),
]


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def required_env(name: str) -> str:
    value = env(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def load_env_file_mount(path: str) -> None:
    if not path or not os.path.isdir(path):
        return
    for name in os.listdir(path):
        file_path = os.path.join(path, name)
        if not os.path.isfile(file_path) or name in os.environ:
            continue
        with open(file_path, "r", encoding="utf-8") as handle:
            os.environ[name] = handle.read().strip()


def load_bucket_env_from_mounts() -> None:
    load_env_file_mount(env("BUCKET_SECRET_MOUNT_PATH", "/var/run/ai-tutor-artifacts-secret"))
    load_env_file_mount(env("BUCKET_CONFIG_MOUNT_PATH", "/var/run/ai-tutor-artifacts-config"))


def s3_region() -> str:
    return env("BUCKET_REGION") or "us-east-1"


def s3_base_url() -> str:
    scheme = env("BUCKET_SCHEME", "https")
    host = required_env("BUCKET_HOST")
    port = env("BUCKET_PORT")
    authority = f"{host}:{port}" if port and port not in {"80", "443"} else host
    return f"{scheme}://{authority}/{required_env('BUCKET_NAME')}"


def urlopen(request: urllib.request.Request, timeout: int = 60):
    if urllib.parse.urlparse(request.full_url).scheme == "https" and env("BUCKET_TLS_VERIFY", "true").lower() in {"0", "false", "no"}:
        return urllib.request.urlopen(request, timeout=timeout, context=ssl._create_unverified_context())
    return urllib.request.urlopen(request, timeout=timeout)


def signing_key(secret_key: str, date_stamp: str, region: str) -> bytes:
    key = ("AWS4" + secret_key).encode("utf-8")
    for value in (date_stamp, region, "s3", "aws4_request"):
        key = hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()
    return key


def s3_request(method: str, key: str, body: bytes = b"", query: str = "", content_type: str = "application/octet-stream") -> bytes:
    access_key = required_env("AWS_ACCESS_KEY_ID")
    secret_key = required_env("AWS_SECRET_ACCESS_KEY")
    region = s3_region()
    now = dt.datetime.utcnow()
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    parsed = urllib.parse.urlparse(s3_base_url())
    if key:
        encoded_key = "/".join(urllib.parse.quote(part, safe="") for part in key.split("/"))
        canonical_uri = f"{parsed.path.rstrip('/')}/{encoded_key}"
    else:
        canonical_uri = parsed.path.rstrip("/") or "/"
    url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, canonical_uri, "", query, ""))
    payload_hash = hashlib.sha256(body).hexdigest()
    canonical_headers = (
        f"host:{parsed.netloc}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "host;x-amz-content-sha256;x-amz-date"
    canonical_request = "\n".join([method, canonical_uri, query, canonical_headers, signed_headers, payload_hash])
    credential_scope = f"{date_stamp}/{region}/s3/aws4_request"
    string_to_sign = "\n".join(
        ["AWS4-HMAC-SHA256", amz_date, credential_scope, hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()]
    )
    signature = hmac.new(signing_key(secret_key, date_stamp, region), string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        "AWS4-HMAC-SHA256 "
        f"Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )
    headers = {
        "Authorization": authorization,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
        "Content-Type": content_type,
    }
    request = urllib.request.Request(url, data=body if method in {"PUT", "POST"} else None, method=method, headers=headers)
    with urlopen(request, timeout=60) as response:
        return response.read()


def apply_lifecycle(days: int) -> None:
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<LifecycleConfiguration xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Rule>
    <ID>expire-quality-artifacts-after-{days}-days</ID>
    <Status>Enabled</Status>
    <Filter>
      <Prefix></Prefix>
    </Filter>
    <Expiration>
      <Days>{days}</Days>
    </Expiration>
    <AbortIncompleteMultipartUpload>
      <DaysAfterInitiation>1</DaysAfterInitiation>
    </AbortIncompleteMultipartUpload>
  </Rule>
</LifecycleConfiguration>
""".encode("utf-8")
    s3_request("PUT", "", body, query="lifecycle=", content_type="application/xml")
    print(f"Applied S3 lifecycle policy: expire artifacts after {days} day(s).")


def github_headers(token: str) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ai-tutor-artifact-sync",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_json(url: str, token: str) -> dict:
    request = urllib.request.Request(url, headers=github_headers(token))
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def github_bytes(url: str, token: str) -> bytes:
    request = urllib.request.Request(url, headers=github_headers(token))
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def newest_artifact(owner: str, repo: str, artifact_name: str, token: str, branch: str) -> dict | None:
    query = urllib.parse.urlencode({"name": artifact_name, "per_page": "30"})
    artifacts = github_json(f"https://api.github.com/repos/{owner}/{repo}/actions/artifacts?{query}", token).get("artifacts", [])
    candidates = [artifact for artifact in artifacts if not artifact.get("expired")]
    if branch:
        candidates = [artifact for artifact in candidates if artifact.get("workflow_run", {}).get("head_branch") == branch]
    candidates.sort(key=lambda artifact: artifact.get("created_at", ""), reverse=True)
    return candidates[0] if candidates else None


def safe_zip_name(name: str) -> str | None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or name.endswith("/"):
        return None
    return str(path)


def upload_latest_marker(prefix: str, metadata: dict[str, str]) -> None:
    s3_request("PUT", f"{prefix}/latest.json", json.dumps(metadata, indent=2).encode("utf-8"), content_type="application/json")


def read_json_or_default(key: str, default: object) -> object:
    try:
        return json.loads(s3_request("GET", key).decode("utf-8"))
    except Exception:
        return default


def update_index(prefix: str, metadata: dict[str, object], limit: int = 20) -> None:
    index_key = f"{prefix}/index.json"
    index = read_json_or_default(index_key, [])
    if not isinstance(index, list):
        index = []
    run_id = str(metadata.get("run_id", ""))
    index = [item for item in index if item.get("run_id") != run_id]
    index.insert(0, metadata)
    s3_request("PUT", index_key, json.dumps(index[:limit], indent=2).encode("utf-8"), content_type="application/json")


def parse_junit_summary(path: str | None) -> dict[str, int]:
    if not path or not os.path.exists(path):
        return {"passed": 0, "failed": 0, "skipped": 0, "errors": 0, "total": 0}
    import xml.etree.ElementTree as ET

    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites:
        suites = [root]
    total = sum(int(float(suite.attrib.get("tests", "0") or 0)) for suite in suites)
    failed = sum(int(float(suite.attrib.get("failures", "0") or 0)) for suite in suites)
    errors = sum(int(float(suite.attrib.get("errors", "0") or 0)) for suite in suites)
    skipped = sum(int(float(suite.attrib.get("skipped", "0") or 0)) for suite in suites)
    return {"passed": max(total - failed - errors - skipped, 0), "failed": failed, "skipped": skipped, "errors": errors, "total": total}


def parse_junit_summary_bytes(payload: bytes) -> dict[str, int]:
    temp_path = "/tmp/ai-tutor-artifact-junit.xml"
    with open(temp_path, "wb") as handle:
        handle.write(payload)
    return parse_junit_summary(temp_path)


def redact_text(text: str) -> str:
    redacted = text
    for name in SECRET_ENV_NAMES:
        value = os.getenv(name)
        if value and len(value) >= 4:
            redacted = redacted.replace(value, f"[REDACTED:{name}]")
    for pattern, replacement in SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def put_file(key: str, path: str, redact: bool = False) -> bool:
    if not path or not os.path.exists(path):
        return False
    if redact:
        payload = redact_text(open(path, "r", encoding="utf-8", errors="replace").read()).encode("utf-8")
        content_type = "text/plain"
    else:
        with open(path, "rb") as handle:
            payload = handle.read()
        content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    s3_request("PUT", key, payload, content_type=content_type)
    return True


def upload_openshift_backend(args: argparse.Namespace) -> None:
    prefix = env("ARTIFACT_PREFIX", args.prefix).strip("/")
    run_id = env("QUALITY_RUN_ID") or env("OPENSHIFT_BUILD_NAME") or env("HOSTNAME") or str(int(time.time()))
    run_prefix = f"{prefix}/runs/{run_id}"
    results_path = args.results
    summary = parse_junit_summary(results_path)
    uploaded = 0

    uploaded += int(put_file(f"{run_prefix}/junit/results.xml", results_path))
    uploaded += int(put_file(f"{run_prefix}/raw/live-results.xml", results_path))
    if args.log:
        uploaded += int(put_file(f"{run_prefix}/logs/backend-quality-redacted.log", args.log, redact=True))

    status = "passed" if summary["failed"] == 0 and summary["errors"] == 0 else "failed"
    metadata: dict[str, object] = {
        "repository": env("QUALITY_REPOSITORY", "AI_Tutor_Analysis"),
        "environment": env("QUALITY_ENVIRONMENT", "openshift-dev"),
        "branch": env("QUALITY_BRANCH", "feature/test-suite-expansion"),
        "run_id": run_id,
        "commit_sha": env("QUALITY_COMMIT_SHA", ""),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": status,
        "passed": summary["passed"],
        "failed": summary["failed"],
        "skipped": summary["skipped"],
        "errors": summary["errors"],
        "total": summary["total"],
        "report_path": f"/artifact/{run_prefix}/junit/results.xml",
        "raw_results_path": f"/artifact/{run_prefix}/raw/live-results.xml",
        "log_path": f"/artifact/{run_prefix}/logs/backend-quality-redacted.log" if args.log else "",
    }
    s3_request("PUT", f"{run_prefix}/metadata.json", json.dumps(metadata, indent=2).encode("utf-8"), content_type="application/json")
    upload_latest_marker(prefix, metadata)
    update_index(prefix, metadata)
    print(f"Uploaded {uploaded} OpenShift backend artifact file(s) to {run_prefix}.")


def sync_github_playwright(args: argparse.Namespace) -> None:
    token = required_env("GITHUB_TOKEN")
    owner = env("GITHUB_OWNER", "NYU-ITS")
    repo = env("GITHUB_REPOSITORY_NAME", "NAGA-open-webui")
    branch = env("GITHUB_BRANCH_FILTER", "rs/ai-tutor-tests")
    prefix = env("ARTIFACT_PREFIX", "github/NAGA-open-webui/playwright")
    synced = 0

    for artifact_name in ARTIFACT_NAMES:
        artifact = newest_artifact(owner, repo, artifact_name, token, branch)
        if artifact is None:
            print(f"No usable artifact found: {repo}/{artifact_name}")
            continue
        archive_bytes = github_bytes(artifact["archive_download_url"], token)
        run_id = str(artifact.get("workflow_run", {}).get("id") or artifact.get("id"))
        target_prefix = f"{prefix}/runs/{run_id}/{artifact_name}"
        with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
            for member in archive.namelist():
                safe_name = safe_zip_name(member)
                if not safe_name:
                    continue
                payload = archive.read(member)
                content_type = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
                s3_request("PUT", f"{target_prefix}/{safe_name}", payload, content_type=content_type)
                synced += 1
        if artifact_name == "playwright-report":
            metadata = {
                "repository": repo,
                "environment": "github-actions",
                "branch": branch,
                "run_id": run_id,
                "commit_sha": "",
                "created_at": artifact.get("created_at", ""),
                "status": "synced",
                "report_path": f"/artifact/{target_prefix}/index.html",
                "synced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            upload_latest_marker(prefix, metadata)
            update_index(prefix, metadata)
        print(f"Synced {artifact_name} from run {run_id}.")

    if synced == 0:
        raise SystemExit("No Playwright artifact files were synced.")
    print(f"Synced {synced} Playwright artifact file(s).")


def sync_github_backend(args: argparse.Namespace) -> None:
    token = required_env("GITHUB_TOKEN")
    owner = env("GITHUB_OWNER", "NYU-ITS")
    repo = env("GITHUB_REPOSITORY_NAME", "AI_Tutor_Analysis")
    branch = env("GITHUB_BRANCH_FILTER", "feature/test-suite-expansion")
    artifact_name = env("GITHUB_ARTIFACT_NAME", BACKEND_GITHUB_ARTIFACT_NAME)
    prefix = env("ARTIFACT_PREFIX", "github/backend/feature-test-suite-expansion")
    artifact = newest_artifact(owner, repo, artifact_name, token, branch)
    if artifact is None:
        raise SystemExit(f"No usable artifact found: {repo}/{artifact_name}")

    archive_bytes = github_bytes(artifact["archive_download_url"], token)
    run_id = str(artifact.get("workflow_run", {}).get("id") or artifact.get("id"))
    target_prefix = f"{prefix}/runs/{run_id}/{artifact_name}"
    summary = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0, "total": 0}
    results_key = f"{target_prefix}/results.xml"
    synced = 0

    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        for member in archive.namelist():
            safe_name = safe_zip_name(member)
            if not safe_name:
                continue
            payload = archive.read(member)
            content_type = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
            s3_request("PUT", f"{target_prefix}/{safe_name}", payload, content_type=content_type)
            synced += 1
            if safe_name.endswith("results.xml"):
                summary = parse_junit_summary_bytes(payload)
                results_key = f"{target_prefix}/{safe_name}"

    status = "passed" if summary["failed"] == 0 and summary["errors"] == 0 else "failed"
    metadata: dict[str, object] = {
        "repository": repo,
        "environment": "github-actions",
        "branch": branch,
        "run_id": run_id,
        "commit_sha": "",
        "created_at": artifact.get("created_at", ""),
        "status": status,
        "passed": summary["passed"],
        "failed": summary["failed"],
        "skipped": summary["skipped"],
        "errors": summary["errors"],
        "total": summary["total"],
        "report_path": f"/artifact/{results_key}",
        "synced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    s3_request("PUT", f"{prefix}/runs/{run_id}/metadata.json", json.dumps(metadata, indent=2).encode("utf-8"), content_type="application/json")
    upload_latest_marker(prefix, metadata)
    update_index(prefix, metadata)
    print(f"Synced {synced} GitHub backend artifact file(s) from run {run_id}.")


def artifact_prefixes() -> list[tuple[str, str]]:
    raw = env("ARTIFACT_PREFIXES")
    if raw:
        pairs = []
        for item in raw.split(","):
            label, _, prefix = item.partition("=")
            if label and prefix:
                pairs.append((label.strip(), prefix.strip().strip("/")))
        if pairs:
            return pairs
    prefix = env("ARTIFACT_PREFIX", "openshift/frontend/dev")
    return [("OpenShift frontend", prefix)]


def metadata_table_rows(prefix: str, items: list[dict[str, object]]) -> str:
    rows = []
    for item in items:
        report_path = str(item.get("report_path") or "#")
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(item.get('created_at', '')))}</td>"
            f"<td>{html.escape(str(item.get('run_id', '')))}</td>"
            f"<td>{html.escape(str(item.get('environment', '')))}</td>"
            f"<td>{html.escape(str(item.get('branch', '')))}</td>"
            f"<td>{html.escape(str(item.get('status', '')))}</td>"
            f"<td>{html.escape(str(item.get('passed', '')))}</td>"
            f"<td>{html.escape(str(item.get('failed', '')))}</td>"
            f"<td>{html.escape(str(item.get('skipped', '')))}</td>"
            f"<td><a href=\"{html.escape(report_path)}\">Open report</a></td>"
            f"<td><a href=\"/artifact/{html.escape(prefix)}/runs/{html.escape(str(item.get('run_id', '')))}/metadata.json\">metadata</a></td>"
            "</tr>"
        )
    return "".join(rows) or "<tr><td colspan='10'>No runs found yet.</td></tr>"


def serve(args: argparse.Namespace) -> None:
    prefixes = artifact_prefixes()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            try:
                if self.path in {"/", "/latest", "/runs"}:
                    sections = []
                    for label, prefix in prefixes:
                        latest = read_json_or_default(f"{prefix}/latest.json", {})
                        index = read_json_or_default(f"{prefix}/index.json", [])
                        if not isinstance(index, list):
                            index = []
                        latest_link = str(latest.get("report_path") or "#") if isinstance(latest, dict) else "#"
                        sections.append(
                            f"<section><h2>{html.escape(label)}</h2>"
                            f"<p><a href=\"{html.escape(latest_link)}\">Open latest report</a></p>"
                            "<table><thead><tr><th>Created</th><th>Run</th><th>Environment</th><th>Branch</th><th>Status</th>"
                            "<th>Passed</th><th>Failed</th><th>Skipped</th><th>Report</th><th>Raw</th></tr></thead>"
                            f"<tbody>{metadata_table_rows(prefix, index)}</tbody></table></section>"
                        )
                    body = f"""<!doctype html>
<html><head><title>AI Tutor Quality Artifacts</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 32px; color: #111827; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0 32px; }}
  th, td {{ border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; }}
  th {{ background: #f9fafb; }}
  a {{ color: #2563eb; text-decoration: none; }}
  section {{ margin-bottom: 28px; }}
</style></head>
<body>
  <h1>AI Tutor Quality Artifacts</h1>
  <p>Recent heavy test artifacts from OpenShift and GitHub. Numeric trends stay in Prometheus/Grafana.</p>
  {''.join(sections)}
</body></html>""".encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if self.path.startswith("/artifact/"):
                    key = urllib.parse.unquote(self.path.removeprefix("/artifact/").split("?", 1)[0])
                    body = s3_request("GET", key)
                    self.send_response(200)
                    self.send_header("Content-Type", mimetypes.guess_type(key)[0] or "application/octet-stream")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(404)
                self.end_headers()
            except Exception as exc:  # noqa: BLE001
                body = f"Artifact viewer error: {exc}\n".encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving artifact viewer on http://{args.host}:{args.port}")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync and serve AI Tutor quality artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("sync-github-playwright")
    subparsers.add_parser("sync-github-backend")
    upload_backend_parser = subparsers.add_parser("upload-openshift-backend")
    upload_backend_parser.add_argument("--prefix", default="openshift/backend/dev")
    upload_backend_parser.add_argument("--results", default="live-results/results.xml")
    upload_backend_parser.add_argument("--log", default="live-results/pytest.log")
    lifecycle_parser = subparsers.add_parser("apply-lifecycle")
    lifecycle_parser.add_argument("--days", default=30, type=int)
    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host", default="0.0.0.0")
    serve_parser.add_argument("--port", default=8080, type=int)
    args = parser.parse_args()

    load_bucket_env_from_mounts()
    if args.command == "sync-github-playwright":
        sync_github_playwright(args)
    elif args.command == "sync-github-backend":
        sync_github_backend(args)
    elif args.command == "upload-openshift-backend":
        upload_openshift_backend(args)
    elif args.command == "apply-lifecycle":
        apply_lifecycle(args.days)
    elif args.command == "serve":
        serve(args)


if __name__ == "__main__":
    main()
