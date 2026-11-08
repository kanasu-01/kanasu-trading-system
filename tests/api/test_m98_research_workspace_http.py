import asyncio
import json
from dataclasses import dataclass

from fastapi import FastAPI

import api.routes.research_workspace_routes as routes
from api.models.research_workspace_models import (
    ResearchWorkspaceConfigResponse,
    WorkspacePaperCampaignListResponse,
    WorkspacePaperSendResponse,
    WorkspaceQualificationPolicyResponse,
    WorkspaceQualificationResponse,
    WorkspaceStrategyListResponse,
    WorkspaceStudyResponse,
    WorkspaceWfaResponse,
)
from api.research_workspace_application import ResearchWorkspaceConflict


class FakeApplication:
    def config(self):
        return ResearchWorkspaceConfigResponse(
            markets=[{"id": "NSE", "name": "NSE"}],
            symbols=[{"symbol": "RELIANCE", "exchange": "NSE"}],
            timeframes=[{"id": "15m", "label": "15 Minutes"}],
            strategies=[{"id": "sma_crossover", "name": "SMA Crossover"}],
            timezones=["Asia/Kolkata"],
            studies=[],
            active_qualification_policy=None,
        )

    def create_study(self, display_title):
        return WorkspaceStudyResponse(
            study_id="study-1",
            display_title=display_title,
            created_at="2026-11-07T00:00:00Z",
            archived=False,
        )

    def study_strategies(self, study_id):
        return WorkspaceStrategyListResponse(study_id=study_id, strategies=[])

    def qualify_study(
        self,
        study_id,
        threshold_pct,
        observed_policy_id=None,
    ):
        return WorkspaceQualificationResponse(
            study_id=study_id,
            policy=WorkspaceQualificationPolicyResponse(
                policy_id="policy-1",
                version=1,
                threshold_pct=str(threshold_pct),
            ),
            policy_changed=True,
            policy_current=True,
            results=[],
        )

    def wfa_state(self, study_id):
        return WorkspaceWfaResponse(
            study_id=study_id,
            active_policy_id=None,
            strategies=[],
        )

    def run_wfa(self, study_id, expected_policy_id):
        return WorkspaceWfaResponse(
            study_id=study_id,
            active_policy_id=expected_policy_id,
            strategies=[],
        )

    def send_to_paper(self, study_id, expected_wfa_decision_ids):
        return WorkspacePaperSendResponse(study_id=study_id, campaigns=[])

    def paper_state(self, study_id):
        return WorkspacePaperCampaignListResponse(
            study_id=study_id,
            campaigns=[],
        )


@dataclass(frozen=True)
class AsgiResponse:
    status_code: int
    body: bytes

    def json(self):
        return json.loads(self.body.decode("utf-8"))


def request(app, method, path, *, json_body=None):
    body = (
        json.dumps(json_body).encode("utf-8")
        if json_body is not None
        else b""
    )
    headers = [(b"host", b"testserver")]
    if json_body is not None:
        headers.append((b"content-type", b"application/json"))

    async def invoke():
        messages = []
        received = False

        async def receive():
            nonlocal received
            if received:
                return {"type": "http.disconnect"}
            received = True
            return {
                "type": "http.request",
                "body": body,
                "more_body": False,
            }

        async def send(message):
            messages.append(message)

        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": path,
                "raw_path": path.encode("ascii"),
                "query_string": b"",
                "headers": headers,
                "client": ("testclient", 50000),
                "server": ("testserver", 80),
                "root_path": "",
            },
            receive,
            send,
        )
        return messages

    messages = asyncio.run(invoke())
    start = next(
        message
        for message in messages
        if message["type"] == "http.response.start"
    )
    response_body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return AsgiResponse(start["status"], response_body)


def client(monkeypatch):
    monkeypatch.setattr(
        routes,
        "workspace_application_factory",
        lambda: FakeApplication(),
    )
    app = FastAPI()
    app.include_router(
        routes.router,
        prefix="/api/research-workspace",
    )
    return app


def test_workspace_config_and_study_creation_are_typed(monkeypatch):
    http = client(monkeypatch)

    config = request(http, "GET", "/api/research-workspace/config")
    created = request(
        http,
        "POST",
        "/api/research-workspace/studies",
        json_body={"display_title": "SMA Research"},
    )

    assert config.status_code == 200
    assert config.json()["symbols"][0]["symbol"] == "RELIANCE"
    assert created.status_code == 200
    assert created.json()["display_title"] == "SMA Research"


def test_workspace_qualification_wfa_and_paper_routes_delegate(monkeypatch):
    http = client(monkeypatch)

    qualification = request(
        http,
        "POST",
        "/api/research-workspace/studies/study-1/qualification",
        json_body={
            "threshold_pct": "60",
            "observed_policy_id": None,
        },
    )
    wfa = request(
        http,
        "POST",
        "/api/research-workspace/studies/study-1/wfa/run",
        json_body={"expected_policy_id": None},
    )
    paper = request(
        http,
        "POST",
        "/api/research-workspace/studies/study-1/paper/send",
        json_body={"expected_wfa_decision_ids": []},
    )

    assert qualification.status_code == 200
    assert qualification.json()["policy"]["threshold_pct"] == "60"
    assert wfa.status_code == 200
    assert paper.status_code == 200


def test_stale_qualification_policy_observation_is_409(monkeypatch):
    class StalePolicyApplication(FakeApplication):
        def qualify_study(
            self,
            _study_id,
            _threshold_pct,
            _observed_policy_id=None,
        ):
            raise ResearchWorkspaceConflict("stale policy observation")

    monkeypatch.setattr(
        routes,
        "workspace_application_factory",
        lambda: StalePolicyApplication(),
    )
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/research-workspace")
    response = request(
        app,
        "POST",
        "/api/research-workspace/studies/study-1/qualification",
        json_body={
            "threshold_pct": "50",
            "observed_policy_id": "policy-old",
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "qualification_policy_conflict"


def test_paper_lifecycle_conflict_is_409_but_unexpected_runtime_failure_is_500(
    monkeypatch,
):
    from api.paper_trading_application import PaperLifecycleConflict

    class ConflictApplication(FakeApplication):
        def start_paper(self, _campaign_id, _expected_latest_session_id):
            raise PaperLifecycleConflict("already active")

    monkeypatch.setattr(
        routes,
        "workspace_application_factory",
        lambda: ConflictApplication(),
    )
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/research-workspace")
    conflict = request(
        app,
        "POST",
        "/api/research-workspace/paper-campaigns/campaign-1/start",
        json_body={"expected_latest_session_id": None},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "qualified_paper_start_conflict"

    class FailureApplication(FakeApplication):
        def start_paper(self, _campaign_id, _expected_latest_session_id):
            raise RuntimeError("unexpected persistence/runtime failure")

    monkeypatch.setattr(
        routes,
        "workspace_application_factory",
        lambda: FailureApplication(),
    )

    failure = request(
        app,
        "POST",
        "/api/research-workspace/paper-campaigns/campaign-1/start",
        json_body={"expected_latest_session_id": None},
    )
    assert failure.status_code == 500
    assert failure.json()["code"] == "qualified_paper_start_failed"


def test_invalid_timeframe_and_timezone_fail_before_application_factory(monkeypatch):
    calls = []

    def forbidden_factory():
        calls.append(True)
        raise AssertionError("application factory must not run")

    monkeypatch.setattr(routes, "workspace_application_factory", forbidden_factory)
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/research-workspace")
    base = {
        "study_id": "study-1",
        "symbol": "RELIANCE",
        "strategy_id": "sma_crossover",
        "start": "2026-01-05T09:15:00+05:30",
        "end": "2026-01-05T10:45:00+05:30",
        "timezone": "Asia/Kolkata",
        "initial_capital": 100000,
        "strategy_params": {"fast_period": 20, "slow_period": 50},
    }

    invalid_timeframe = request(
        app,
        "POST",
        "/api/research-workspace/backtests/run",
        json_body={**base, "timeframe": "1m"},
    )
    invalid_timezone = request(
        app,
        "POST",
        "/api/research-workspace/backtests/run",
        json_body={**base, "timeframe": "15m", "timezone": "UTC"},
    )

    assert invalid_timeframe.status_code == 422
    assert invalid_timezone.status_code == 422
    assert calls == []


def test_generation_conflicts_are_http_409(monkeypatch):
    class ConflictApplication(FakeApplication):
        def study_strategies(self, _study_id):
            raise ResearchWorkspaceConflict("study generation changed")

        def run_wfa(self, _study_id, _expected_policy_id):
            raise ResearchWorkspaceConflict("policy generation changed")

        def send_to_paper(self, _study_id, _expected_ids):
            raise ResearchWorkspaceConflict("WFA decision set changed")

        def paper_state(self, _study_id):
            raise ResearchWorkspaceConflict("Paper generation changed")

    monkeypatch.setattr(
        routes,
        "workspace_application_factory",
        lambda: ConflictApplication(),
    )
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/research-workspace")

    study = request(app, "GET", "/api/research-workspace/studies/study-1/strategies")
    wfa = request(
        app,
        "POST",
        "/api/research-workspace/studies/study-1/wfa/run",
        json_body={"expected_policy_id": "policy-old"},
    )
    paper_send = request(
        app,
        "POST",
        "/api/research-workspace/studies/study-1/paper/send",
        json_body={"expected_wfa_decision_ids": ["wfa-old"]},
    )
    paper_state = request(
        app,
        "GET",
        "/api/research-workspace/studies/study-1/paper",
    )

    assert study.status_code == 409
    assert wfa.status_code == 409
    assert paper_send.status_code == 409
    assert paper_state.status_code == 409
