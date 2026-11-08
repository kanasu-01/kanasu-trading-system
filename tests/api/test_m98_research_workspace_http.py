from fastapi import FastAPI
from fastapi.testclient import TestClient

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
        return WorkspaceWfaResponse(study_id=study_id, strategies=[])

    def run_wfa(self, study_id):
        return WorkspaceWfaResponse(study_id=study_id, strategies=[])

    def send_to_paper(self, study_id):
        return WorkspacePaperSendResponse(study_id=study_id, campaigns=[])

    def paper_state(self, study_id):
        return WorkspacePaperCampaignListResponse(
            study_id=study_id,
            campaigns=[],
        )


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
    return TestClient(app)


def test_workspace_config_and_study_creation_are_typed(monkeypatch):
    http = client(monkeypatch)

    config = http.get("/api/research-workspace/config")
    created = http.post(
        "/api/research-workspace/studies",
        json={"display_title": "SMA Research"},
    )

    assert config.status_code == 200
    assert config.json()["symbols"][0]["symbol"] == "RELIANCE"
    assert created.status_code == 200
    assert created.json()["display_title"] == "SMA Research"


def test_workspace_qualification_wfa_and_paper_routes_delegate(monkeypatch):
    http = client(monkeypatch)

    qualification = http.post(
        "/api/research-workspace/studies/study-1/qualification",
        json={
            "threshold_pct": "60",
            "observed_policy_id": None,
        },
    )
    wfa = http.post(
        "/api/research-workspace/studies/study-1/wfa/run",
    )
    paper = http.post(
        "/api/research-workspace/studies/study-1/paper/send",
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
    http = TestClient(app)

    response = http.post(
        "/api/research-workspace/studies/study-1/qualification",
        json={
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
        def start_paper(self, _campaign_id):
            raise PaperLifecycleConflict("already active")

    monkeypatch.setattr(
        routes,
        "workspace_application_factory",
        lambda: ConflictApplication(),
    )
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/research-workspace")
    http = TestClient(app)

    conflict = http.post(
        "/api/research-workspace/paper-campaigns/campaign-1/start"
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "qualified_paper_start_conflict"

    class FailureApplication(FakeApplication):
        def start_paper(self, _campaign_id):
            raise RuntimeError("unexpected persistence/runtime failure")

    monkeypatch.setattr(
        routes,
        "workspace_application_factory",
        lambda: FailureApplication(),
    )

    failure = http.post(
        "/api/research-workspace/paper-campaigns/campaign-1/start"
    )
    assert failure.status_code == 500
    assert failure.json()["code"] == "qualified_paper_start_failed"
