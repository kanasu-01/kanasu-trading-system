import asyncio
import json
from datetime import datetime, timezone

import api.main as main_module
import api.routes.research_routes as routes
from api.research_application import (
    ResearchStudyNotFound,
)
from core.market_data.historical_coverage import (
    TimeRange,
)
from core.research.models.registered_study import (
    EvidenceReusePolicy,
)
from core.research.models.universe import (
    UniverseDefinition,
    UniverseQuality,
    UniverseSnapshot,
)


STUDY_ID = "study-registration-http"

START = datetime(
    2026,
    1,
    1,
    tzinfo=timezone.utc,
)

END = datetime(
    2026,
    2,
    1,
    tzinfo=timezone.utc,
)


def _request():
    request_type = getattr(
        routes,
        "ResearchRevisionRegistrationRequest",
    )

    return request_type(
        research_intent=(
            "Evaluate one registered population"
        ),
        strategy_procedure_id=(
            "sma-crossover-v1"
        ),
        timeframe="1d",
        research_range={
            "start": START,
            "end": END,
        },
        timezone="UTC",
        initial_capital=1_000_000.0,
        risk_economic_configuration={
            "risk_per_trade_pct": 1.0,
            "position_sizing": {
                "mode": "fixed-risk",
            },
        },
        parameter_variants=[
            {
                "fast_period": 10,
                "slow_period": 30,
            },
            {
                "fast_period": 20,
                "slow_period": 50,
            },
        ],
        universe_definition={
            "name": "pit-http-universe",
            "selection_spec": (
                "explicit registered fixture"
            ),
            "source_reference": (
                "membership-source-v1"
            ),
        },
        universe_snapshots=[
            {
                "members": [
                    "NSE:A",
                    "NSE:B",
                ],
                "quality": "PIT_RECONSTRUCTED",
                "as_of": START,
                "provenance_refs": [
                    "membership-evidence-001",
                ],
                "effective_from": START,
                "effective_to": END,
                "derivation_version": (
                    "universe-reconstruction-v2"
                ),
            },
        ],
        require_point_in_time=True,
        data_treatment_basis={
            "price_adjustment": "raw",
            "missing_data": "fail_closed",
        },
        repository_revision="repo-revision-001",
        evidence_reuse_policy=(
            "ALLOW_EXACT_ACCEPTED"
        ),
    )


def test_registration_route_converts_complete_request_to_domain(
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
        "register_research_revision",
    )

    actual = asyncio.run(
        route(
            STUDY_ID,
            _request(),
        )
    )

    assert actual is expected

    assert (
        captured["function"]
        is getattr(
            routes,
            "register_research_revision_application",
        )
    )

    assert captured["args"] == ()

    kwargs = captured["kwargs"]

    assert kwargs["study_id"] == STUDY_ID
    assert (
        kwargs["research_intent"]
        == "Evaluate one registered population"
    )
    assert (
        kwargs["strategy_procedure_id"]
        == "sma-crossover-v1"
    )
    assert kwargs["timeframe"] == "1d"
    assert kwargs["timezone"] == "UTC"
    assert kwargs["initial_capital"] == 1_000_000.0

    assert isinstance(
        kwargs["research_range"],
        TimeRange,
    )
    assert kwargs["research_range"].start == START
    assert kwargs["research_range"].end == END

    assert kwargs[
        "risk_economic_configuration"
    ] == {
        "risk_per_trade_pct": 1.0,
        "position_sizing": {
            "mode": "fixed-risk",
        },
    }

    assert tuple(
        kwargs["parameter_variants"]
    ) == (
        {
            "fast_period": 10,
            "slow_period": 30,
        },
        {
            "fast_period": 20,
            "slow_period": 50,
        },
    )

    definition = kwargs[
        "universe_definition"
    ]

    assert isinstance(
        definition,
        UniverseDefinition,
    )
    assert definition.name == "pit-http-universe"
    assert (
        definition.selection_spec
        == "explicit registered fixture"
    )
    assert (
        definition.source_reference
        == "membership-source-v1"
    )

    snapshots = tuple(
        kwargs["universe_snapshots"]
    )

    assert len(snapshots) == 1

    snapshot = snapshots[0]

    assert isinstance(
        snapshot,
        UniverseSnapshot,
    )
    assert snapshot.definition is definition
    assert snapshot.members == (
        "NSE:A",
        "NSE:B",
    )
    assert (
        snapshot.quality
        is UniverseQuality.PIT_RECONSTRUCTED
    )
    assert snapshot.as_of == START
    assert snapshot.provenance_refs == (
        "membership-evidence-001",
    )
    assert snapshot.effective_from == START
    assert snapshot.effective_to == END
    assert (
        snapshot.derivation_version
        == "universe-reconstruction-v2"
    )

    assert kwargs[
        "require_point_in_time"
    ] is True

    assert kwargs[
        "data_treatment_basis"
    ] == {
        "price_adjustment": "raw",
        "missing_data": "fail_closed",
    }

    assert (
        kwargs["repository_revision"]
        == "repo-revision-001"
    )

    assert (
        kwargs["evidence_reuse_policy"]
        is EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
    )

    registered_at = kwargs[
        "registered_at"
    ]

    assert isinstance(
        registered_at,
        datetime,
    )
    assert registered_at.utcoffset() is not None


def test_registration_route_returns_stable_404_for_missing_study(
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
        "register_research_revision",
    )

    result = asyncio.run(
        route(
            STUDY_ID,
            _request(),
        )
    )

    assert result.status_code == 404
    assert json.loads(result.body) == {
        "code": "research_study_not_found",
        "message": "Research study was not found",
    }


def test_registration_route_maps_domain_rejection_to_422(
    monkeypatch,
):
    async def fail(
        function,
        *args,
        **kwargs,
    ):
        raise ValueError(
            "private universe validation detail"
        )

    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        fail,
    )

    route = getattr(
        routes,
        "register_research_revision",
    )

    result = asyncio.run(
        route(
            STUDY_ID,
            _request(),
        )
    )

    assert result.status_code == 422
    assert json.loads(result.body) == {
        "code": "invalid_research_registration",
        "message": (
            "Research revision registration "
            "was invalid"
        ),
    }


def test_registration_route_sanitizes_unexpected_failure(
    monkeypatch,
):
    async def fail(
        function,
        *args,
        **kwargs,
    ):
        raise RuntimeError(
            "private persistence detail"
        )

    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        fail,
    )

    route = getattr(
        routes,
        "register_research_revision",
    )

    result = asyncio.run(
        route(
            STUDY_ID,
            _request(),
        )
    )

    assert result.status_code == 500
    assert json.loads(result.body) == {
        "code": "research_registration_failed",
        "message": (
            "Research revision could not be registered"
        ),
    }


def test_registration_http_contract_is_typed_and_complete():
    schema = main_module.app.openapi()

    path = (
        "/api/research/studies/"
        "{study_id}/revisions"
    )

    operation = schema[
        "paths"
    ][path]["post"]

    assert (
        operation["requestBody"][
            "content"
        ]["application/json"]["schema"]
        == {
            "$ref": (
                "#/components/schemas/"
                "ResearchRevisionRegistrationRequest"
            )
        }
    )

    responses = operation["responses"]

    assert (
        responses["200"]["content"][
            "application/json"
        ]["schema"]
        == {
            "$ref": (
                "#/components/schemas/"
                "ResearchRevisionRegistrationResponse"
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

    components = schema[
        "components"
    ]["schemas"]

    request_schema = components[
        "ResearchRevisionRegistrationRequest"
    ]

    required = set(
        request_schema["required"]
    )

    assert {
        "research_intent",
        "strategy_procedure_id",
        "timeframe",
        "research_range",
        "timezone",
        "initial_capital",
        "risk_economic_configuration",
        "parameter_variants",
        "universe_definition",
        "universe_snapshots",
        "require_point_in_time",
        "data_treatment_basis",
        "repository_revision",
        "evidence_reuse_policy",
    }.issubset(required)

    snapshot_schema = components[
        "ResearchUniverseSnapshotRequest"
    ]

    assert {
        "members",
        "quality",
        "as_of",
        "provenance_refs",
    }.issubset(
        set(
            snapshot_schema["required"]
        )
    )

    assert "derivation_version" in snapshot_schema[
        "properties"
    ]
    assert "effective_from" in snapshot_schema[
        "properties"
    ]
    assert "effective_to" in snapshot_schema[
        "properties"
    ]
