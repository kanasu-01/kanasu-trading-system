import asyncio
import json
from datetime import datetime, timezone

import api.main as main_module
import api.routes.research_routes as routes
from api.models.research_models import (
    ResearchProgressResponse,
)
from api.research_application import (
    ResearchRevisionNotFound,
)


REVISION_ID = "sha256:" + ("2" * 64)
STARTED_AT = datetime(
    2026,
    10,
    2,
    10,
    0,
    tzinfo=timezone.utc,
)


def _response() -> ResearchProgressResponse:
    return ResearchProgressResponse(
        study_revision_id=REVISION_ID,
        initial_batch_started_at=STARTED_AT,
        total_registered_trials=4,
        pending_trials=1,
        executed_trials=1,
        reused_trials=1,
        invalid_trials=0,
        insufficient_trials=0,
        failed_trials=1,
        cancelled_trials=0,
        interrupted_trials=0,
        queued_jobs=1,
        running_jobs=0,
        succeeded_jobs=2,
        failed_jobs=1,
        cancelled_jobs=0,
        interrupted_jobs=0,
        total_jobs=4,
    )


def test_progress_route_delegates_to_threadpool(
    monkeypatch,
):
    captured = {}
    expected = _response()

    async def run_in_threadpool(
        function,
        *args,
        **kwargs,
    ):
        captured["function"] = function
        captured["args"] = args
        captured["kwargs"] = kwargs
        return expected

    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        run_in_threadpool,
    )

    actual = asyncio.run(
        routes.get_research_progress(
            REVISION_ID
        )
    )

    assert actual is expected
    assert (
        captured["function"]
        is routes.get_research_progress_application
    )
    assert captured["args"] == (
        REVISION_ID,
    )
    assert captured["kwargs"] == {}


def test_progress_route_returns_stable_404(
    monkeypatch,
):
    async def fail(
        function,
        *args,
        **kwargs,
    ):
        raise ResearchRevisionNotFound(
            "internal revision detail"
        )

    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        fail,
    )

    result = asyncio.run(
        routes.get_research_progress(
            REVISION_ID
        )
    )

    assert result.status_code == 404
    assert json.loads(result.body) == {
        "code": "research_revision_not_found",
        "message": "Research revision was not found",
    }


def test_progress_route_returns_stable_500(
    monkeypatch,
):
    async def fail(
        function,
        *args,
        **kwargs,
    ):
        raise RuntimeError(
            "private database detail"
        )

    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        fail,
    )

    result = asyncio.run(
        routes.get_research_progress(
            REVISION_ID
        )
    )

    assert result.status_code == 500
    assert json.loads(result.body) == {
        "code": "research_progress_failed",
        "message": "Research progress could not be loaded",
    }


def test_research_progress_http_contract_is_typed():
    schema = main_module.app.openapi()

    operation = schema["paths"][
        (
            "/api/research/study-revisions/"
            "{study_revision_id}/progress"
        )
    ]["get"]

    responses = operation["responses"]

    assert (
        responses["200"]["content"][
            "application/json"
        ]["schema"]
        == {
            "$ref": (
                "#/components/schemas/"
                "ResearchProgressResponse"
            )
        }
    )

    for status in (
        "404",
        "422",
        "500",
    ):
        assert (
            responses[status]["content"][
                "application/json"
            ]["schema"]
            == {
                "$ref": (
                    "#/components/schemas/"
                    "ApiErrorResponse"
                )
            }
        )
