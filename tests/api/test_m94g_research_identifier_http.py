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
def test_m94g4_real_asgi_research_workflow_persists_to_sqlite(
    tmp_path,
    monkeypatch,
):
    import asyncio
    import json
    from urllib.parse import unquote, urlsplit

    import api.research_application as research_application
    from core.config.app_config import AppConfig
    from core.research.models.registered_study import (
        EvidenceReusePolicy,
        ResearchJobState,
        TrialDisposition,
    )
    from core.research.models.universe import (
        UniverseQuality,
    )
    from core.research.sqlite_research_catalog_store import (
        SQLiteResearchCatalogStore,
    )

    config = AppConfig(
        research_database_path=str(
            tmp_path / "research.sqlite3"
        ),
        research_artifact_root=str(
            tmp_path / "research_artifacts"
        ),
        research_max_trials_per_revision=50,
        research_max_workers=2,
    )

    monkeypatch.setattr(
        research_application,
        "load_app_config",
        lambda: config,
    )

    async def request(
        method,
        path,
        payload=None,
    ):
        parsed = urlsplit(path)

        if payload is None:
            body = b""
            headers = []
        else:
            body = json.dumps(
                payload,
                separators=(",", ":"),
            ).encode("utf-8")
            headers = [
                (
                    b"content-type",
                    b"application/json",
                ),
                (
                    b"content-length",
                    str(len(body)).encode("ascii"),
                ),
            ]

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
            "query_string": parsed.query.encode(
                "ascii"
            ),
            "root_path": "",
            "headers": headers,
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
                    "body": body,
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

        starts = [
            message
            for message in messages
            if message["type"]
            == "http.response.start"
        ]

        assert len(starts) == 1

        response_body = b"".join(
            message.get("body", b"")
            for message in messages
            if message["type"]
            == "http.response.body"
        )

        return (
            starts[0]["status"],
            json.loads(
                response_body.decode("utf-8")
            ),
        )

    create_status, created = asyncio.run(
        request(
            "POST",
            "/api/research/studies",
            {
                "display_title": (
                    "M9.4g4 ASGI persistence"
                ),
            },
        )
    )

    assert create_status == 200
    study_id = created["study_id"]

    registration_payload = {
        "research_intent": (
            "prove real ASGI durable persistence"
        ),
        "strategy_procedure_id": (
            "fixture-asgi-persistence-v1"
        ),
        "timeframe": "1d",
        "research_range": {
            "start": "2020-01-01T00:00:00+00:00",
            "end": "2020-02-01T00:00:00+00:00",
        },
        "timezone": "UTC",
        "initial_capital": 1000000.0,
        "risk_economic_configuration": {
            "risk_per_trade_pct": 1.0,
        },
        "parameter_variants": [
            {
                "variant": 1,
            },
        ],
        "universe_definition": {
            "name": "m94g4-asgi-universe",
            "selection_spec": "fixture",
            "source_reference": (
                "m94g4-asgi-source"
            ),
        },
        "universe_snapshots": [
            {
                "members": [
                    "NSE:A",
                ],
                "quality": (
                    UniverseQuality.PIT_VERIFIED.value
                ),
                "as_of": (
                    "2020-01-01T00:00:00+00:00"
                ),
                "provenance_refs": [
                    "m94g4-asgi-source",
                ],
                "effective_from": (
                    "2020-01-01T00:00:00+00:00"
                ),
                "effective_to": (
                    "2020-02-01T00:00:00+00:00"
                ),
                "derivation_version": (
                    "fixture-v1"
                ),
            },
        ],
        "require_point_in_time": True,
        "data_treatment_basis": {
            "price_adjustment": "raw",
        },
        "repository_revision": (
            "repo-m94g4-asgi"
        ),
        "evidence_reuse_policy": (
            EvidenceReusePolicy
            .FORCE_NEW_EXECUTION
            .value
        ),
    }

    register_status, registered = asyncio.run(
        request(
            "POST",
            (
                "/api/research/studies/"
                + study_id
                + "/revisions"
            ),
            registration_payload,
        )
    )

    assert register_status == 200
    assert registered[
        "total_registered_trials"
    ] == 1

    revision_id = registered[
        "study_revision_id"
    ]

    start_status, started = asyncio.run(
        request(
            "POST",
            (
                "/api/research/study-revisions/"
                + revision_id
                + "/start"
            ),
        )
    )

    assert start_status == 200
    assert started[
        "total_registered_trials"
    ] == 1
    assert started["pending_trials"] == 1
    assert started["queued_jobs"] == 1
    assert started["total_jobs"] == 1

    reopened = SQLiteResearchCatalogStore(
        config.research_database_path
    )

    persisted_study = reopened.load_study(
        study_id
    )

    assert persisted_study is not None
    assert (
        persisted_study.display_title
        == "M9.4g4 ASGI persistence"
    )

    persisted_revision = (
        reopened.load_study_revision(
            revision_id
        )
    )

    assert persisted_revision is not None
    assert (
        persisted_revision.study_id
        == study_id
    )
    assert (
        persisted_revision
        .initial_batch_started_at
        is not None
    )

    trials = reopened.list_trials_for_revision(
        revision_id
    )

    assert len(trials) == 1
    assert (
        trials[0].disposition
        is TrialDisposition.PENDING
    )

    jobs = (
        reopened
        .list_research_jobs_for_trial(
            trials[0].trial_id
        )
    )

    assert len(jobs) == 1
    assert (
        jobs[0].state
        is ResearchJobState.QUEUED
    )
    assert jobs[0].attempt_id is None
