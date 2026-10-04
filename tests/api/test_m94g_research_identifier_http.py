import asyncio
import json

from urllib.parse import unquote, urlsplit
import pytest

import api.main as main_module
import api.research_application as application
import api.routes.research_routes as routes
from api.research_application import (
    ResearchIdentifierValidationError,
)


@pytest.mark.parametrize(
    ("function", "argument_name"),
    (
        (
            application.list_research_trials,
            "study_revision_id",
        ),
        (
            application.get_research_trial_detail,
            "trial_id",
        ),
        (
            application.get_research_progress,
            "study_revision_id",
        ),
        (
            application.get_research_aggregation,
            "study_revision_id",
        ),
    ),
)
@pytest.mark.parametrize(
    "identifier",
    (
        "",
        "   ",
    ),
)
def test_read_application_rejects_malformed_identifier_before_io(
    monkeypatch,
    function,
    argument_name,
    identifier,
):
    def must_not_resolve_config(*args, **kwargs):
        pytest.fail(
            "malformed identifier reached configuration/store I/O"
        )

    monkeypatch.setattr(
        application,
        "_resolved_config",
        must_not_resolve_config,
    )

    with pytest.raises(
        ResearchIdentifierValidationError,
    ):
        function(
            **{
                argument_name: identifier,
            }
        )


@pytest.mark.parametrize(
    "function",
    (
        application.start_research_revision,
        application.cancel_research_revision,
    ),
)
@pytest.mark.parametrize(
    "identifier",
    (
        "",
        "   ",
    ),
)
def test_lifecycle_application_rejects_malformed_identifier_before_io(
    monkeypatch,
    function,
    identifier,
):
    def must_not_resolve_config(*args, **kwargs):
        pytest.fail(
            "malformed identifier reached configuration/store I/O"
        )

    monkeypatch.setattr(
        application,
        "_resolved_config",
        must_not_resolve_config,
    )

    kwargs = {
        "study_revision_id": identifier,
    }

    if function is application.start_research_revision:
        from datetime import datetime, timezone

        kwargs["started_at"] = datetime.now(
            timezone.utc
        )
    else:
        from datetime import datetime, timezone

        kwargs["requested_at"] = datetime.now(
            timezone.utc
        )

    with pytest.raises(
        ResearchIdentifierValidationError,
    ):
        function(**kwargs)


async def _raise_identifier_error(
    function,
    *args,
    **kwargs,
):
    raise ResearchIdentifierValidationError(
        "private identifier detail"
    )


@pytest.mark.parametrize(
    "route",
    (
        routes.get_research_progress,
        routes.list_research_trials,
        routes.get_research_aggregation,
    ),
)
def test_revision_read_routes_map_malformed_identifier_to_422(
    monkeypatch,
    route,
):
    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        _raise_identifier_error,
    )

    result = asyncio.run(
        route("   ")
    )

    assert result.status_code == 422
    assert json.loads(result.body) == {
        "code": "invalid_research_identifier",
        "message": "Research identifier was invalid",
    }


def test_trial_detail_route_maps_malformed_identifier_to_422(
    monkeypatch,
):
    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        _raise_identifier_error,
    )

    result = asyncio.run(
        routes.get_research_trial_detail("   ")
    )

    assert result.status_code == 422
    assert json.loads(result.body) == {
        "code": "invalid_research_identifier",
        "message": "Research identifier was invalid",
    }


@pytest.mark.parametrize(
    "route",
    (
        routes.start_research_revision,
        routes.cancel_research_revision,
    ),
)
def test_lifecycle_routes_map_malformed_identifier_to_422(
    monkeypatch,
    route,
):
    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        _raise_identifier_error,
    )

    result = asyncio.run(
        route("   ")
    )

    assert result.status_code == 422
    assert json.loads(result.body) == {
        "code": "invalid_research_identifier",
        "message": "Research identifier was invalid",
    }


@pytest.mark.parametrize(
    ("route", "expected_code"),
    (
        (
            routes.start_research_revision,
            "research_revision_start_conflict",
        ),
        (
            routes.cancel_research_revision,
            "research_revision_cancel_conflict",
        ),
    ),
)
def test_plain_lifecycle_value_error_remains_409(
    monkeypatch,
    route,
    expected_code,
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

    result = asyncio.run(
        route(
            "sha256:" + ("a" * 64)
        )
    )

    assert result.status_code == 409
    assert (
        json.loads(result.body)["code"]
        == expected_code
    )


class _AsgiResponse:
    def __init__(
        self,
        *,
        status_code,
        body,
    ):
        self.status_code = status_code
        self.body = body

    def json(self):
        return json.loads(
            self.body.decode("utf-8")
        )


async def _asgi_request(
    method,
    path,
):
    parsed = urlsplit(path)

    scope = {
        "type": "http",
        "asgi": {
            "version": "3.0",
            "spec_version": "2.3",
        },
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": unquote(parsed.path),
        "raw_path": parsed.path.encode("ascii"),
        "query_string": parsed.query.encode("ascii"),
        "root_path": "",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }

    request_sent = False
    messages = []

    async def receive():
        nonlocal request_sent

        if not request_sent:
            request_sent = True
            return {
                "type": "http.request",
                "body": b"",
                "more_body": False,
            }

        return {
            "type": "http.disconnect",
        }

    async def send(message):
        messages.append(message)

    await main_module.app(
        scope,
        receive,
        send,
    )

    start_messages = [
        message
        for message in messages
        if message["type"] == "http.response.start"
    ]

    if len(start_messages) != 1:
        raise AssertionError(
            "ASGI response did not contain exactly one response start"
        )

    body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )

    return _AsgiResponse(
        status_code=(
            start_messages[0]["status"]
        ),
        body=body,
    )


@pytest.mark.parametrize(
    ("method", "path"),
    (
        (
            "GET",
            "/api/research/study-revisions/%20%20%20/progress",
        ),
        (
            "GET",
            "/api/research/study-revisions/%20%20%20/trials",
        ),
        (
            "GET",
            "/api/research/study-revisions/%20%20%20/aggregation",
        ),
        (
            "GET",
            "/api/research/trials/%20%20%20",
        ),
        (
            "POST",
            "/api/research/study-revisions/%20%20%20/start",
        ),
        (
            "POST",
            "/api/research/study-revisions/%20%20%20/cancel",
        ),
    ),
)
def test_real_asgi_whitespace_identifier_returns_422(
    method,
    path,
):
    result = asyncio.run(
        _asgi_request(
            method,
            path,
        )
    )

    assert result.status_code == 422
    assert result.json() == {
        "code": "invalid_research_identifier",
        "message": "Research identifier was invalid",
    }
