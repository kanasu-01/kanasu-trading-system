from datetime import datetime, timedelta, timezone

import pytest

from core.research.reproducibility import decode_canonical_bytes
from core.config.app_config import AppConfig
from core.market_data.historical_coverage import TimeRange
from core.research.models.registered_study import (
    STUDY_REVISION_SCHEMA_ID,
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
    data_treatment=None,
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
                "brokerage_rate": 0.0003,
            }
        ),
        parameter_variants=parameters,
        universe_definition=definition,
        universe_snapshots=snapshots,
        require_point_in_time=True,
        data_treatment_basis=(
            data_treatment
            if data_treatment is not None
            else {
                "price_adjustment": "raw",
                "corporate_actions": "explicit",
            }
        ),
        repository_revision="repo-revision-1",
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
        registered_at=registered_at,
    )


def test_m94k_registration_requires_explicit_price_adjustment(
    tmp_path,
):
    _, _, service = _environment(
        tmp_path
    )

    definition = UniverseDefinition(
        name="m94k-explicit-data-treatment",
        selection_spec="fixture",
    )

    snapshot = _snapshot(
        definition,
        ("NSE:A",),
        JAN,
        FEB,
        provenance="m94k-explicit-source",
    )

    with pytest.raises(
        ValueError,
        match="explicitly declare price_adjustment",
    ):
        _register(
            service,
            definition,
            (snapshot,),
            data_treatment={},
        )


def test_m94k_registration_preserves_explicit_unknown_price_adjustment(
    tmp_path,
):
    _, artifacts, service = _environment(
        tmp_path
    )

    definition = UniverseDefinition(
        name="m94k-unknown-data-treatment",
        selection_spec="fixture",
    )

    snapshot = _snapshot(
        definition,
        ("NSE:A",),
        JAN,
        FEB,
        provenance="m94k-unknown-source",
    )

    population = _register(
        service,
        definition,
        (snapshot,),
        data_treatment={
            "price_adjustment": "unknown",
        },
    )

    raw = artifacts.load_bytes(
        population.revision.plan_artifact_id
    )

    plan = decode_canonical_bytes(
        raw,
        schema=STUDY_REVISION_SCHEMA_ID,
    )

    assert plan["data_treatment_basis"] == {
        "price_adjustment": "unknown",
    }


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



def test_registered_plan_can_be_strictly_decoded_without_identity_loss(
    tmp_path,
):
    _, artifacts, service = _environment(
        tmp_path
    )

    definition = UniverseDefinition(
        name="decoder-test",
        selection_spec="fixture",
        source_reference="decoder-fixture-v1",
    )

    first = _snapshot(
        definition,
        ("NSE:A",),
        JAN,
        FEB,
        provenance="decoder-source-1",
    )

    second = _snapshot(
        definition,
        ("NSE:A",),
        FEB,
        MAR,
        provenance="decoder-source-2",
    )

    snapshots = (first, second)

    population = _register(
        service,
        definition,
        snapshots,
        parameters=(
            {"fast": 5, "slow": 20},
            {"fast": 10, "slow": 40},
        ),
    )

    raw = artifacts.load_bytes(
        population.revision.plan_artifact_id
    )

    plan = decode_canonical_bytes(
        raw,
        schema=STUDY_REVISION_SCHEMA_ID,
    )

    assert plan["study_id"] == "study-m94b"
    assert (
        plan["strategy_procedure_id"]
        == "sma-crossover-v1"
    )
    assert plan["timeframe"] == "1d"
    assert plan["timezone"] == "UTC"
    assert plan["initial_capital"] == 1_000_000.0
    assert (
        plan["risk_economic_configuration"][
            "risk_per_trade_pct"
        ]
        == 1.0
    )
    assert len(plan["parameter_variants"]) == 2

    fingerprints = {
        item["fingerprint"]
        for item in plan["parameter_variants"]
    }

    assert fingerprints == {
        trial.parameter_configuration_fingerprint
        for trial in population.trials
    }


def test_canonical_decoder_rejects_wrong_schema_and_noncanonical_bytes(
    tmp_path,
):
    _, artifacts, service = _environment(
        tmp_path
    )

    definition = UniverseDefinition(
        name="decoder-test",
        selection_spec="fixture",
        source_reference="decoder-fixture-v1",
    )

    first = _snapshot(
        definition,
        ("NSE:A",),
        JAN,
        FEB,
        provenance="decoder-source-1",
    )

    second = _snapshot(
        definition,
        ("NSE:A",),
        FEB,
        MAR,
        provenance="decoder-source-2",
    )

    snapshots = (first, second)

    population = _register(
        service,
        definition,
        snapshots,
    )

    raw = artifacts.load_bytes(
        population.revision.plan_artifact_id
    )

    with pytest.raises(
        ValueError,
        match="schema does not match",
    ):
        decode_canonical_bytes(
            raw,
            schema="kanasu.wrong-schema.v1",
        )

    with pytest.raises(ValueError):
        decode_canonical_bytes(
            raw + b" ",
            schema=STUDY_REVISION_SCHEMA_ID,
        )


def test_m94g2_mixed_offset_registration_replay_is_idempotent(
    tmp_path,
):
    catalog, _, service = _environment(
        tmp_path
    )

    definition = UniverseDefinition(
        name="mixed-offset-idempotence",
        selection_spec="fixture",
    )

    plus_fourteen = timezone(
        timedelta(hours=14)
    )
    minus_ten = timezone(
        timedelta(hours=-10)
    )

    # These starts intentionally sort differently as ISO text versus
    # absolute chronology:
    #   first_start  == 2020-01-01 00:00 UTC
    #   second_start == 2020-01-01 01:30 UTC
    # but second_start's stored ISO text begins with 2019-12-31.
    first_start = datetime(
        2020,
        1,
        1,
        14,
        0,
        tzinfo=plus_fourteen,
    )
    first_end = datetime(
        2020,
        1,
        1,
        15,
        30,
        tzinfo=plus_fourteen,
    )
    second_start = datetime(
        2019,
        12,
        31,
        15,
        30,
        tzinfo=minus_ten,
    )
    second_end = datetime(
        2020,
        1,
        1,
        18,
        0,
        tzinfo=minus_ten,
    )

    assert first_end == second_start
    assert first_start < second_start

    first = _snapshot(
        definition,
        ("NSE:A",),
        first_start,
        first_end,
        provenance="mixed-offset-source-1",
    )
    second = _snapshot(
        definition,
        ("NSE:B",),
        second_start,
        second_end,
        provenance="mixed-offset-source-2",
    )

    def register(snapshots):
        return service.register_study_revision(
            study_id="study-m94b",
            research_intent=(
                "mixed-offset registration idempotence"
            ),
            strategy_procedure_id=(
                "sma-crossover-v1"
            ),
            timeframe="1d",
            research_range=TimeRange(
                first_start,
                second_end,
            ),
            timezone="UTC",
            initial_capital=1_000_000.0,
            risk_economic_configuration={
                "risk_per_trade_pct": 1.0,
                "slippage_pct": 0.05,
                "brokerage_rate": 0.0003,
            },
            parameter_variants=(
                {"fast": 5, "slow": 20},
            ),
            universe_definition=definition,
            universe_snapshots=snapshots,
            require_point_in_time=True,
            data_treatment_basis={
                "price_adjustment": "raw",
                "corporate_actions": "explicit",
            },
            repository_revision=(
                "repo-revision-1"
            ),
            evidence_reuse_policy=(
                EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
            ),
            registered_at=APR,
        )

    one = register(
        (first, second)
    )
    two = register(
        (second, first)
    )

    assert (
        one.revision.study_revision_id
        == two.revision.study_revision_id
    )
    assert (
        one.revision.registered_at
        == two.revision.registered_at
        == APR
    )
    assert one.trials == two.trials

    assert [
        (
            trial.instrument_id,
            trial.membership_episode_start,
        )
        for trial in two.trials
    ] == [
        ("NSE:A", first_start),
        ("NSE:B", second_start),
    ]

    assert len(
        catalog.list_study_revisions(
            "study-m94b"
        )
    ) == 1
