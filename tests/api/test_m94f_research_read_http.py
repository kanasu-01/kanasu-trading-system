import asyncio
import json

import api.main as main_module
import api.routes.research_routes as routes
from api.research_application import (
    ResearchRevisionNotFound,
    ResearchTrialNotFound,
)


REVISION_ID = "sha256:" + ("6" * 64)
TRIAL_ID = "sha256:" + ("7" * 64)


def test_trial_list_route_delegates_to_threadpool(
    monkeypatch,
):
    captured = {}
    expected = object()

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

    route = getattr(
        routes,
        "list_research_trials",
    )

    actual = asyncio.run(
        route(
            REVISION_ID
        )
    )

    assert actual is expected
    assert (
        captured["function"]
        is getattr(
            routes,
            "list_research_trials_application",
        )
    )
    assert captured["args"] == (
        REVISION_ID,
    )
    assert captured["kwargs"] == {}


def test_trial_list_route_returns_stable_404(
    monkeypatch,
):
    async def fail(
        function,
        *args,
        **kwargs,
    ):
        raise ResearchRevisionNotFound(
            "private revision detail"
        )

    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        fail,
    )

    route = getattr(
        routes,
        "list_research_trials",
    )

    result = asyncio.run(
        route(
            REVISION_ID
        )
    )

    assert result.status_code == 404
    assert json.loads(result.body) == {
        "code": "research_revision_not_found",
        "message": "Research revision was not found",
    }


def test_trial_detail_route_delegates_to_threadpool(
    monkeypatch,
):
    captured = {}
    expected = object()

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

    route = getattr(
        routes,
        "get_research_trial_detail",
    )

    actual = asyncio.run(
        route(
            TRIAL_ID
        )
    )

    assert actual is expected
    assert (
        captured["function"]
        is getattr(
            routes,
            "get_research_trial_detail_application",
        )
    )
    assert captured["args"] == (
        TRIAL_ID,
    )
    assert captured["kwargs"] == {}


def test_trial_detail_route_returns_stable_404(
    monkeypatch,
):
    async def fail(
        function,
        *args,
        **kwargs,
    ):
        raise ResearchTrialNotFound(
            "private trial detail"
        )

    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        fail,
    )

    route = getattr(
        routes,
        "get_research_trial_detail",
    )

    result = asyncio.run(
        route(
            TRIAL_ID
        )
    )

    assert result.status_code == 404
    assert json.loads(result.body) == {
        "code": "research_trial_not_found",
        "message": "Research trial was not found",
    }


def test_aggregation_route_delegates_to_threadpool(
    monkeypatch,
):
    captured = {}
    expected = object()

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

    route = getattr(
        routes,
        "get_research_aggregation",
    )

    actual = asyncio.run(
        route(
            REVISION_ID
        )
    )

    assert actual is expected
    assert (
        captured["function"]
        is getattr(
            routes,
            "get_research_aggregation_application",
        )
    )
    assert captured["args"] == (
        REVISION_ID,
    )
    assert captured["kwargs"] == {}


def test_aggregation_route_returns_stable_500(
    monkeypatch,
):
    async def fail(
        function,
        *args,
        **kwargs,
    ):
        raise RuntimeError(
            "private artifact detail"
        )

    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        fail,
    )

    route = getattr(
        routes,
        "get_research_aggregation",
    )

    result = asyncio.run(
        route(
            REVISION_ID
        )
    )

    assert result.status_code == 500
    assert json.loads(result.body) == {
        "code": "research_aggregation_failed",
        "message": (
            "Research aggregation could not be loaded"
        ),
    }


def test_research_read_http_contracts_are_typed():
    schema = main_module.app.openapi()

    contracts = {
        (
            "/api/research/study-revisions/"
            "{study_revision_id}/trials"
        ): "ResearchTrialListResponse",
        (
            "/api/research/trials/{trial_id}"
        ): "ResearchTrialDetailResponse",
        (
            "/api/research/study-revisions/"
            "{study_revision_id}/aggregation"
        ): "ResearchAggregationResponse",
    }

    for path, response_name in contracts.items():
        operation = schema["paths"][
            path
        ]["get"]

        responses = operation[
            "responses"
        ]

        assert (
            responses["200"]["content"][
                "application/json"
            ]["schema"]
            == {
                "$ref": (
                    "#/components/schemas/"
                    + response_name
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
