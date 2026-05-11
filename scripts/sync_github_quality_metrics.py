#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from io import BytesIO


DEFAULT_ARTIFACTS = [
    ("AI_Tutor_Analysis", "ai-tutor-backend-quality-metrics"),
    ("NAGA-open-webui", "ai-tutor-frontend-quality-metrics"),
]


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def headers(token: str) -> dict[str, str]:
    output = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ai-tutor-quality-metrics-sync",
    }
    if token:
        output["Authorization"] = f"Bearer {token}"
    return output


def request_bytes(url: str, token: str, *, method: str = "GET", body: bytes | None = None, content_type: str | None = None) -> tuple[int, bytes]:
    request_headers = headers(token)
    if content_type:
        request_headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def download_artifact(url: str, token: str) -> bytes:
    request = urllib.request.Request(url, headers=headers(token))
    opener = urllib.request.build_opener(NoRedirectHandler)
    try:
        with opener.open(request, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        if exc.code not in {301, 302, 303, 307, 308}:
            raise RuntimeError(f"Failed to download artifact: HTTP {exc.code}")
        redirect_url = exc.headers.get("Location")
        if not redirect_url:
            raise RuntimeError("GitHub artifact download did not include a redirect Location header.")
        redirect_request = urllib.request.Request(redirect_url, headers={"User-Agent": "ai-tutor-quality-metrics-sync"})
        with urllib.request.urlopen(redirect_request, timeout=60) as response:
            return response.read()


def request_json(url: str, token: str) -> dict:
    status, body = request_bytes(url, token)
    if status >= 400:
        raise RuntimeError(f"GitHub API returned HTTP {status} for {url}: {body.decode('utf-8', errors='ignore')[:500]}")
    return json.loads(body.decode("utf-8"))


def artifact_pairs(raw: str) -> list[tuple[str, str]]:
    if not raw:
        return DEFAULT_ARTIFACTS
    pairs: list[tuple[str, str]] = []
    for item in raw.split(","):
        repo, _, artifact = item.partition(":")
        if not repo or not artifact:
            raise SystemExit(f"Invalid artifact mapping: {item}. Expected repo:artifact-name")
        pairs.append((repo.strip(), artifact.strip()))
    return pairs


def newest_artifact(owner: str, repo: str, artifact_name: str, token: str, branch: str) -> dict | None:
    query = urllib.parse.urlencode({"name": artifact_name, "per_page": "30"})
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/artifacts?{query}"
    artifacts = request_json(url, token).get("artifacts", [])
    candidates = [artifact for artifact in artifacts if not artifact.get("expired")]
    if branch:
        candidates = [artifact for artifact in candidates if artifact.get("workflow_run", {}).get("head_branch") == branch]
    candidates.sort(key=lambda artifact: artifact.get("created_at", ""), reverse=True)
    return candidates[0] if candidates else None


def extract_prometheus_payload(archive_bytes: bytes) -> bytes:
    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        names = [name for name in archive.namelist() if name.endswith(".prom")]
        if not names:
            raise RuntimeError("Artifact did not contain a .prom metrics file.")
        return archive.read(sorted(names)[0])


def push_to_gateway(pushgateway_url: str, environment: str, repository: str, metrics: bytes) -> None:
    path = "/".join(
        [
            pushgateway_url.rstrip("/"),
            "metrics/job/ai-tutor-quality",
            "environment",
            urllib.parse.quote(environment, safe=""),
            "repository",
            urllib.parse.quote(repository, safe=""),
        ]
    )
    request = urllib.request.Request(path, data=metrics, method="POST", headers={"Content-Type": "text/plain; version=0.0.4"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status >= 400:
            raise RuntimeError(f"Pushgateway returned HTTP {response.status} for {repository}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync latest GitHub Actions quality metrics artifacts into OpenShift Pushgateway.")
    parser.add_argument("--owner", default=env("GITHUB_OWNER", "NYU-ITS"))
    parser.add_argument("--token", default=env("GITHUB_TOKEN"))
    parser.add_argument("--artifact", action="append", help="Repo/artifact mapping in repo:artifact-name format.")
    parser.add_argument("--branch", default=env("GITHUB_BRANCH_FILTER"))
    parser.add_argument("--environment", default=env("QUALITY_ENVIRONMENT", "github-actions"))
    parser.add_argument("--pushgateway-url", default=env("QUALITY_PUSHGATEWAY_URL", "http://ai-tutor-quality-pushgateway:9091"))
    args = parser.parse_args()

    mappings = artifact_pairs(",".join(args.artifact or []) or env("GITHUB_QUALITY_ARTIFACTS"))
    synced = 0
    for repo, artifact_name in mappings:
        artifact = newest_artifact(args.owner, repo, artifact_name, args.token, args.branch)
        if artifact is None:
            print(f"No usable artifact found for {repo}/{artifact_name}.")
            continue
        print(f"Syncing {repo}/{artifact_name} from {artifact.get('created_at')}...")
        archive = download_artifact(artifact["archive_download_url"], args.token)
        metrics = extract_prometheus_payload(archive)
        push_to_gateway(args.pushgateway_url, args.environment, repo, metrics)
        synced += 1

    if synced == 0:
        print("No GitHub quality metrics were synced.")
        sys.exit(2)
    print(f"Synced {synced} GitHub quality metric artifact(s) at {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}.")


if __name__ == "__main__":
    main()
