from datetime import datetime, timezone

import pytest

from core.config.app_config import AppConfig
from core.market_data.historical_coverage import TimeRange
from core.research.models.registered_study import (
    EvidenceReusePolicy,
    Study,
)
from core.research.models.universe import (
    UniverseDefinition,
    UniverseQuality,
    UniverseSnapshot,
)
from core.research.registered_study_registration import (
    DEFAULT_RESEARCH_MAX_TRIALS_PER_REVISION,
    RegisteredStudyRegistrationService,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
)
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)


UTC = timezone.utc

JAN = datetime(2020, 1, 1, tzinfo=UTC)
FEB = datetime(2020, 2, 1, tzinfo=UTC)
MAR = datetime(2020, 3, 1, tzinfo=UTC)
APR = datetime(2020, 4, 1, tzinfo=UTC)


def _snapshot(
    definition,
    members,
    start,
    end,
    *,
    provenance,
):
    return UniverseSnapshot(
        definition=definition,
        members=members,
        quality=UniverseQuality.PIT_VERIFIED,
        as_of=start,
        provenance_refs=(provenance,),
        effective_from=start,
        effective_to=end,
    )


def _environment(
    tmp_path,
    *,
    max_trials=5000,
):
    catalog = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3"
    )

    artifacts = ContentAddressedResearchArtifactStore(
        tmp_path / "artifacts"
    )

    catalog.save_study(
        Study(
            study_id="study-m94b",
            created_at=JAN,
            display_title="M9.4b research",
        )
    )

    service = RegisteredStudyRegistrationService(
        catalog_store=catalog,
        artifact_store=artifacts,
        max_trials_per_revision=max_trials,
    )

    return catalog, artifacts, service


def _register(
    service,
    definition,
    snapshots,
    *,
    parameters=(
        {"fast": 5, "slow": 20},
    ),
    registered_at=APR,
    research_intent="test deterministic membership",
    risk=None,
):
    return service.register_study_revision(
        study_id="study-m94b",
        research_intent=research_intent,
        strategy_procedure_id="sma-crossover-v1",
        timeframe="1d",
        research_range=TimeRange(
            JAN,
            max(
                snapshot.effective_to
                for snapshot in snapshots
                if snapshot.effective_to is not None
            ),
        ),
        timezone="UTC",
        initial_capital=1_000_000.0,
        risk_economic_configuration=(
            risk
            or {
                "risk_per_trade_pct": 1.0,
                "slippage_pct": 0.05,
                "brokerage_pct": 0.01,
            }
        ),
        parameter_variants=parameters,
        universe_definition=definition,
        universe_snapshots=snapshots,
        require_point_in_time=True,
        data_treatment_basis={
            "price_adjustment": "raw",
            "corporate_actions": "explicit",
        },
        repository_revision="repo-revision-1",
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
        registered_at=registered_at,
    )


def test_continuous_member_coalesces_without_snapshot_reset(
    tmp_path,
):
    catalog, artifacts, service = _environment(
        tmp_path
    )

    definition = UniverseDefinition(
        name="pit-test",
        selection_spec="fixture",
        source_reference="fixture-v1",
    )

    first = _snapshot(
        definition,
        ("NSE:A", "NSE:B"),
        JAN,
        FEB,
        provenance="source-1",
    )

    second = _snapshot(
        definition,
        ("NSE:A", "NSE:C"),
        FEB,
        MAR,
        provenance="source-2",
    )

    population = _register(
        service,
        definition,
        (first, second),
        parameters=(
            {"fast": 10, "slow": 30},
            {"fast": 5, "slow": 20},
        ),
    )

    assert population.revision.study_revision_id == (
        population.revision.plan_artifact_id
    )

    assert population.revision.revision_number == 1
    assert len(population.trials) == 6

    a_trials = tuple(
        trial
        for trial in population.trials
        if trial.instrument_id == "NSE:A"
    )

    assert len(a_trials) == 2

    assert {
        (
            trial.membership_episode_start,
            trial.membership_episode_end,
        )
        for trial in a_trials
    } == {
        (JAN, MAR),
    }

    evidence = artifacts.load_bytes(
        a_trials[0].membership_evidence_artifact_id
    )

    assert first.snapshot_id.encode() in evidence
    assert second.snapshot_id.encode() in evidence
    assert b"PIT_VERIFIED" in evidence
    assert b"source-1" in evidence
    assert b"source-2" in evidence

    plan = artifacts.load_bytes(
        population.revision.plan_artifact_id
    )

    assert first.snapshot_id.encode() in plan
    assert second.snapshot_id.encode() in plan
    assert b"NSE:A" in plan
    assert b"NSE:B" in plan
    assert b"NSE:C" in plan

    assert all(
        trial.membership_evidence_artifact_id
        == trial.membership_evidence_fingerprint
        for trial in population.trials
    )

    assert catalog.list_research_jobs_for_trial(
        population.trials[0].trial_id
    ) == ()


def test_true_membership_gap_creates_separate_episodes(
    tmp_path,
):
    _, _, service = _environment(
        tmp_path
    )

    definition = UniverseDefinition(
        name="gap-test",
        selection_spec="fixture",
    )

    snapshots = (
        _snapshot(
            definition,
            ("NSE:A",),
            JAN,
            FEB,
            provenance="source-1",
        ),
        _snapshot(
            definition,
            ("NSE:B",),
            FEB,
            MAR,
            provenance="source-2",
        ),
        _snapshot(
            definition,
            ("NSE:A",),
            MAR,
            APR,
            provenance="source-3",
        ),
    )

    population = _register(
        service,
        definition,
        snapshots,
    )

    a_trials = [
        trial
        for trial in population.trials
        if trial.instrument_id == "NSE:A"
    ]

    assert [
        (
            trial.membership_episode_start,
            trial.membership_episode_end,
        )
        for trial in a_trials
    ] == [
        (JAN, FEB),
        (MAR, APR),
    ]


def test_identical_registration_is_order_independent_and_idempotent(
    tmp_path,
):
    catalog, _, service = _environment(
        tmp_path
    )

    definition = UniverseDefinition(
        name="idempotent-test",
        selection_spec="fixture",
    )

    first = _snapshot(
        definition,
        ("NSE:A",),
        JAN,
        FEB,
        provenance="source-1",
    )

    second = _snapshot(
        definition,
        ("NSE:A",),
        FEB,
        MAR,
        provenance="source-2",
    )

    params_a = (
        {"fast": 5, "slow": 20},
        {"fast": 10, "slow": 30},
    )

    params_b = tuple(
        reversed(params_a)
    )

    one = _register(
        service,
        definition,
        (first, second),
        parameters=params_a,
        registered_at=APR,
    )

    later = datetime(
        2020,
        5,
        1,
        tzinfo=UTC,
    )

    two = _register(
        service,
        definition,
        (second, first),
        parameters=params_b,
        registered_at=later,
    )

    assert (
        one.revision.study_revision_id
        == two.revision.study_revision_id
    )

    assert two.revision.registered_at == APR
    assert two.revision.revision_number == 1

    assert {
        trial.trial_id
        for trial in one.trials
    } == {
        trial.trial_id
        for trial in two.trials
    }

    assert len(
        catalog.list_study_revisions(
            "study-m94b"
        )
    ) == 1


def test_material_plan_change_creates_new_revision(
    tmp_path,
):
    _, _, service = _environment(
        tmp_path
    )

    definition = UniverseDefinition(
        name="revision-test",
        selection_spec="fixture",
    )

    snapshots = (
        _snapshot(
            definition,
            ("NSE:A",),
            JAN,
            FEB,
            provenance="source-1",
        ),
    )

    one = _register(
        service,
        definition,
        snapshots,
        risk={
            "risk_per_trade_pct": 1.0,
        },
    )

    two = _register(
        service,
        definition,
        snapshots,
        registered_at=datetime(
            2020,
            5,
            1,
            tzinfo=UTC,
        ),
        risk={
            "risk_per_trade_pct": 0.5,
        },
    )

    assert (
        one.revision.study_revision_id
        != two.revision.study_revision_id
    )

    assert one.revision.revision_number == 1
    assert two.revision.revision_number == 2


def test_trial_population_limit_rejects_before_artifact_publication(
    tmp_path,
):
    catalog, _, service = _environment(
        tmp_path,
        max_trials=1,
    )

    definition = UniverseDefinition(
        name="limit-test",
        selection_spec="fixture",
    )

    snapshots = (
        _snapshot(
            definition,
            ("NSE:A", "NSE:B"),
            JAN,
            FEB,
            provenance="source-1",
        ),
    )

    with pytest.raises(
        ValueError,
        match="exceeds backend limit",
    ):
        _register(
            service,
            definition,
            snapshots,
        )

    assert catalog.list_study_revisions(
        "study-m94b"
    ) == ()

    assert list(
        (tmp_path / "artifacts").rglob(
            "*.json"
        )
    ) == []


def test_universe_resolution_failure_registers_zero_trials(
    tmp_path,
):
    catalog, _, service = _environment(
        tmp_path
    )

    definition = UniverseDefinition(
        name="coverage-test",
        selection_spec="fixture",
    )

    first = _snapshot(
        definition,
        ("NSE:A",),
        JAN,
        FEB,
        provenance="source-1",
    )

    third = _snapshot(
        definition,
        ("NSE:A",),
        MAR,
        APR,
        provenance="source-3",
    )

    with pytest.raises(
        ValueError,
        match="gap",
    ):
        _register(
            service,
            definition,
            (first, third),
        )

    assert catalog.list_study_revisions(
        "study-m94b"
    ) == ()

    assert list(
        (tmp_path / "artifacts").rglob(
            "*.json"
        )
    ) == []


def test_backend_trial_limit_default_is_reviewed_value():
    assert (
        DEFAULT_RESEARCH_MAX_TRIALS_PER_REVISION
        == 5_000
    )

    assert (
        AppConfig().research_max_trials_per_revision
        == 5_000
    )


def test_service_rejects_nonpositive_trial_limit(
    tmp_path,
):
    catalog = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3"
    )

    artifacts = ContentAddressedResearchArtifactStore(
        tmp_path / "artifacts"
    )

    with pytest.raises(
        ValueError,
        match="positive integer",
    ):
        RegisteredStudyRegistrationService(
            catalog_store=catalog,
            artifact_store=artifacts,
            max_trials_per_revision=0,
        )
