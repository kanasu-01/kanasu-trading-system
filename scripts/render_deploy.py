#!/usr/bin/env python3
"""Deploy the exact tested Git SHA to the two pre-created Render staging services."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.render.com/v1"
WORKSPACE = "tea-dbsnrf8ae00c738ivsa0"
REPO = "https://github.com/kanasu-01/kanasu-trading-system"
BRANCH = "m9-v1-research-platform"
BACKEND_NAME = "kanasu-staging-backend"
FRONTEND_NAME = "kanasu-staging-frontend"
BACKEND_URL = "https://kanasu-staging-backend.onrender.com"
FRONTEND_URL = "https://kanasu-staging-frontend.onrender.com"
BACKEND_BUILD = "pip install -r requirements.txt"
BACKEND_START = (
    "KANASU_STAGING_MODE=true TRADING_MODE=BACKTEST ENABLE_LIVE_TRADING=false "
    "PAPER_DATA_SOURCE=ANGELONE HISTORICAL_SOURCE_POLICY=LOCAL_FIRST "
    "HISTORICAL_DATABASE_PATH=/tmp/kanasu/historical.sqlite3 "
    "RESEARCH_DATABASE_PATH=/tmp/kanasu/research.sqlite3 "
    "RESEARCH_ARTIFACT_ROOT=/tmp/kanasu/research_artifacts "
    f"KANASU_STAGING_ALLOWED_ORIGINS={FRONTEND_URL} "
    "python -m uvicorn api.main:app --host 0.0.0.0 --port ${PORT} --workers 1"
)
FRONTEND_BUILD = (
    "cd frontend && export VITE_KANASU_STAGING_AUTH=true && "
    f"export VITE_API_BASE_URL={BACKEND_URL}/api && npm ci && npm run build"
)
PENDING = {"created", "queued", "build_in_progress", "pre_deploy_in_progress", "update_in_progress"}
FAILED = {"deactivated", "build_failed", "pre_deploy_failed", "update_failed", "canceled"}


class DeployError(RuntimeError):
    pass


def request(method: str, path: str, token: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise DeployError(f"Render API HTTP {exc.code}: {detail}") from None
    except urllib.error.URLError as exc:
        raise DeployError(f"Render API unavailable: {exc.reason}") from None


def commit_id(payload) -> str | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("commit"), dict):
        return None
    value = payload["commit"].get("id")
    return value if isinstance(value, str) else None


def service(token: str, name: str, kind: str, expected_url: str) -> dict:
    query = urllib.parse.urlencode({"ownerId": WORKSPACE, "name": name, "limit": 20})
    status, payload = request("GET", f"/services?{query}", token)
    if status != 200 or not isinstance(payload, list):
        raise DeployError(f"Cannot enumerate {name}")
    matches = [x.get("service") for x in payload if isinstance(x, dict) and isinstance(x.get("service"), dict) and x["service"].get("name") == name]
    if len(matches) != 1:
        raise DeployError(f"Expected one Render service named {name}; found {len(matches)}")
    item = matches[0]
    for key, expected in {"ownerId": WORKSPACE, "type": kind, "repo": REPO, "branch": BRANCH, "autoDeployTrigger": "off"}.items():
        if item.get(key) != expected:
            raise DeployError(f"{name} {key} mismatch")
    details = item.get("serviceDetails")
    actual_url = details.get("url") if isinstance(details, dict) else None
    if actual_url != expected_url:
        raise DeployError(f"{name} public URL mismatch")
    if item.get("suspended") != "not_suspended" or not item.get("id"):
        raise DeployError(f"{name} unavailable")
    return item


def configure(token: str, backend: dict, frontend: dict) -> None:
    status, item = request("PATCH", f"/services/{backend['id']}", token, {
        "autoDeployTrigger": "off", "repo": REPO, "branch": BRANCH,
        "serviceDetails": {"runtime": "python", "plan": "free", "healthCheckPath": "/health", "envSpecificDetails": {"buildCommand": BACKEND_BUILD, "startCommand": BACKEND_START}},
    })
    if status != 200 or not isinstance(item, dict):
        raise DeployError("Backend configuration failed")
    details = item.get("serviceDetails", {})
    native = details.get("envSpecificDetails", {}) if isinstance(details, dict) else {}
    if item.get("autoDeployTrigger") != "off" or details.get("runtime") != "python" or details.get("plan") != "free" or details.get("healthCheckPath") != "/health" or native.get("buildCommand") != BACKEND_BUILD or native.get("startCommand") != BACKEND_START or details.get("url") != BACKEND_URL:
        raise DeployError("Backend configuration verification failed")

    status, item = request("PATCH", f"/services/{frontend['id']}", token, {
        "autoDeployTrigger": "off", "repo": REPO, "branch": BRANCH,
        "serviceDetails": {"buildCommand": FRONTEND_BUILD, "publishPath": "frontend/dist"},
    })
    if status != 200 or not isinstance(item, dict):
        raise DeployError("Frontend configuration failed")
    details = item.get("serviceDetails", {})
    if item.get("autoDeployTrigger") != "off" or details.get("buildCommand") != FRONTEND_BUILD or details.get("publishPath") != "frontend/dist" or details.get("url") != FRONTEND_URL:
        raise DeployError("Frontend configuration verification failed")


def deploy(token: str, service_id: str, sha: str) -> str:
    status, payload = request("POST", f"/services/{service_id}/deploys", token, {"commitId": sha, "clearCache": "do_not_clear", "deployMode": "build_and_deploy"})
    if status != 201 or not isinstance(payload, dict) or commit_id(payload) != sha or not payload.get("id"):
        raise DeployError("Render did not create an unambiguous exact-SHA deploy")
    return payload["id"]


def wait_live(token: str, service_id: str, deploy_id: str, sha: str, timeout: int = 1500) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status, payload = request("GET", f"/services/{service_id}/deploys/{deploy_id}", token)
        if status != 200 or not isinstance(payload, dict) or commit_id(payload) != sha:
            raise DeployError("Render deploy identity changed")
        state = payload.get("status")
        if state == "live":
            return
        if state in FAILED or state not in PENDING:
            raise DeployError(f"Render deploy failed or returned unknown state: {state!r}")
        time.sleep(5)
    raise DeployError("Timed out waiting for Render deploy")


def health(url: str, backend: bool, timeout: int = 180) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                body = response.read().decode(errors="replace")
                if response.status == 200:
                    if backend and json.loads(body).get("status") == "available":
                        return
                    if not backend and '<div id="root"></div>' in body:
                        return
        except Exception:
            pass
        time.sleep(5)
    raise DeployError(f"Health check failed: {url}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    if len(args.sha) != 40 or any(c not in "0123456789abcdef" for c in args.sha.lower()):
        raise DeployError("Invalid Git SHA")
    token = os.getenv("RENDER_API_KEY")
    if not token:
        raise DeployError("RENDER_API_KEY is required")

    backend = service(token, BACKEND_NAME, "web_service", BACKEND_URL)
    frontend = service(token, FRONTEND_NAME, "static_site", FRONTEND_URL)
    configure(token, backend, frontend)

    backend_deploy = deploy(token, backend["id"], args.sha)
    wait_live(token, backend["id"], backend_deploy, args.sha)
    health(f"{BACKEND_URL}/health", True)

    frontend_deploy = deploy(token, frontend["id"], args.sha)
    wait_live(token, frontend["id"], frontend_deploy, args.sha)
    health(FRONTEND_URL, False)
    print(f"Render staging live at tested commit {args.sha}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DeployError as exc:
        print(f"DEPLOYMENT BLOCKED: {exc}", file=os.sys.stderr)
        raise SystemExit(1)
