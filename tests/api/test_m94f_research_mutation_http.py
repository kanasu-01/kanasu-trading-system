import asyncio
import json
from datetime import datetime

import api.main as main_module
import api.routes.research_routes as routes
from api.research_application import (
    ResearchRevisionNotFound,
    ResearchStudyNotFound,
)


REVISION_ID = "sha256:" + ("8" * 64)
STUDY_ID = "study-http-001"


def test_create_study_route_delegates_display_title(
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

    request_type = getattr(
        routes,
        "ResearchStudyCreateRequest",
    )

    request = request_type(
        display_title="HTTP research study",
    )

    route = getattr(
        routes,
        "create_research_study",
    )

    actual = asyncio.run(
        route(request)
    )

    assert actual is expected

    assert (
        captured["function"]
        is getattr(
            routes,
            "create_research_study_application",
        )
    )

    assert captured["args"] == (
        "HTTP research study",
    )
    assert captured["kwargs"] == {}


def test_reopen_study_route_delegates_identity(
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
        "reopen_research_study",
    )

    actual = asyncio.run(
        route(STUDY_ID)
    )

    assert actual is expected

    assert (
        captured["function"]
        is getattr(
            routes,
            "reopen_research_study_application",
        )
    )

    assert captured["args"] == (
        STUDY_ID,
    )
    assert captured["kwargs"] == {}


def test_reopen_study_route_returns_stable_404(
    monkeypatch,
):
    async def fail(
        function,
        *args,
        **kwargs,
    ):
        raise ResearchStudyNotFound(
            "private study detail"
        )

    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        fail,
    )

    route = getattr(
        routes,
        "reopen_research_study",
    )

    result = asyncio.run(
        route(STUDY_ID)
    )

    assert result.status_code == 404
    assert json.loads(result.body) == {
        "code": "research_study_not_found",
        "message": "Research study was not found",
    }


def test_start_revision_route_uses_server_timestamp(
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
        "start_research_revision",
    )

    actual = asyncio.run(
        route(REVISION_ID)
    )

    assert actual is expected

    assert (
        captured["function"]
        is getattr(
            routes,
            "start_research_revision_application",
        )
    )

    assert captured["args"] == (
        REVISION_ID,
    )

    started_at = captured[
        "kwargs"
    ]["started_at"]

    assert isinstance(
        started_at,
        datetime,
    )
    assert started_at.utcoffset() is not None


def test_start_revision_route_maps_precondition_to_409(
    monkeypatch,
):
    async def fail(
        function,
        *args,
        **kwargs,
    ):
        raise ValueError(
            "private lifecycle detail"
        )

    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        fail,
    )

    route = getattr(
        routes,
        "start_research_revision",
    )

    result = asyncio.run(
        route(REVISION_ID)
    )

    assert result.status_code == 409
    assert json.loads(result.body) == {
        "code": "research_revision_start_conflict",
        "message": (
            "Research revision could not be started "
            "in its current state"
        ),
    }


def test_start_revision_route_maps_missing_revision_to_404(
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
        "start_research_revision",
    )

    result = asyncio.run(
        route(REVISION_ID)
    )

    assert result.status_code == 404
    assert json.loads(result.body) == {
        "code": "research_revision_not_found",
        "message": "Research revision was not found",
    }


def test_cancel_revision_route_uses_server_timestamp(
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
        "cancel_research_revision",
    )

    actual = asyncio.run(
        route(REVISION_ID)
    )

    assert actual is expected

    assert (
        captured["function"]
        is getattr(
            routes,
            "cancel_research_revision_application",
        )
    )

    assert captured["args"] == (
        REVISION_ID,
    )

    requested_at = captured[
        "kwargs"
    ]["requested_at"]

    assert isinstance(
        requested_at,
        datetime,
    )
    assert requested_at.utcoffset() is not None


def test_cancel_revision_route_maps_precondition_to_409(
    monkeypatch,
):
    async def fail(
        function,
        *args,
        **kwargs,
    ):
        raise ValueError(
            "private lifecycle detail"
        )

    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        fail,
    )

    route = getattr(
        routes,
        "cancel_research_revision",
    )

    result = asyncio.run(
        route(REVISION_ID)
    )

    assert result.status_code == 409
    assert json.loads(result.body) == {
        "code": "research_revision_cancel_conflict",
        "message": (
            "Research revision could not be cancelled "
            "in its current state"
        ),
    }


def test_mutation_http_contracts_are_typed():
    schema = main_module.app.openapi()

    contracts = {
        (
            "/api/research/studies",
            "post",
        ): "ResearchStudyResponse",
        (
            "/api/research/studies/"
            "{study_id}/reopen",
            "post",
        ): "ResearchStudyResponse",
        (
            "/api/research/study-revisions/"
            "{study_revision_id}/start",
            "post",
        ): "ResearchProgressResponse",
        (
            "/api/research/study-revisions/"
            "{study_revision_id}/cancel",
            "post",
        ): "ResearchProgressResponse",
    }

    for (
        path,
        method,
    ), response_name in contracts.items():
        operation = schema["paths"][
            path
        ][method]

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

        assert (
            responses["500"]["content"][
                "application/json"
            ]["schema"]
            == {
                "$ref": (
                    "#/components/schemas/"
                    "ApiErrorResponse"
                )
            }
        )

    create_operation = schema["paths"][
        "/api/research/studies"
    ]["post"]

    assert (
        create_operation[
            "requestBody"
        ]["content"][
            "application/json"
        ]["schema"]
        == {
            "$ref": (
                "#/components/schemas/"
                "ResearchStudyCreateRequest"
            )
        }
    )

    reopen_responses = schema["paths"][
        "/api/research/studies/{study_id}/reopen"
    ]["post"]["responses"]

    assert "404" in reopen_responses

    for suffix in (
        "start",
        "cancel",
    ):
        responses = schema["paths"][
            (
                "/api/research/study-revisions/"
                "{study_revision_id}/"
                + suffix
            )
        ]["post"]["responses"]

        assert "404" in responses
        assert "409" in responses
        assert "422" in responses
        assert "500" in responses
