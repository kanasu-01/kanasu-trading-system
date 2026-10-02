from datetime import datetime, timezone
import sqlite3

import pytest

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
    RegisteredStudyRegistrationService,
)
from core.research.registered_trial_execution_plan import (
    RegisteredTrialExecutionPlanResolver,
)
from core.research.reproducibility import (
    canonical_fingerprint,
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


def _environment(tmp_path):
    catalog = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3"
    )
    artifacts = ContentAddressedResearchArtifactStore(
        tmp_path / "artifacts"
    )

    catalog.save_study(
        Study(
            study_id="study-m94d-plan",
            created_at=JAN,
            display_title="M9.4d plan resolution",
        )
    )

    registration = RegisteredStudyRegistrationService(
        catalog_store=catalog,
        artifact_store=artifacts,
    )

    definition = UniverseDefinition(
        name="m94d-plan-universe",
        selection_spec="fixture",
        source_reference="fixture-v1",
    )

    snapshots = (
        UniverseSnapshot(
            definition=definition,
            members=("NSE:A",),
            quality=UniverseQuality.PIT_VERIFIED,
            as_of=JAN,
            provenance_refs=("source-1",),
            effective_from=JAN,
            effective_to=FEB,
        ),
    )

    population = registration.register_study_revision(
        study_id="study-m94d-plan",
        research_intent="resolve exact Trial plan",
        strategy_procedure_id="sma-crossover-v1",
        timeframe="1d",
        research_range=TimeRange(JAN, FEB),
        timezone="UTC",
        initial_capital=1_000_000.0,
        risk_economic_configuration={
            "risk_per_trade_pct": 1.0,
            "slippage_pct": 0.05,
        },
        parameter_variants=(
            {"fast": 5, "slow": 20},
            {"fast": 10, "slow": 40},
        ),
        universe_definition=definition,
        universe_snapshots=snapshots,
        require_point_in_time=True,
        data_treatment_basis={
            "price_adjustment": "raw",
            "corporate_actions": "explicit",
        },
        repository_revision="repo-m94d-plan",
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
        registered_at=APR,
    )

    resolver = RegisteredTrialExecutionPlanResolver(
        catalog_store=catalog,
        artifact_store=artifacts,
    )

    return catalog, population, resolver


def test_resolves_exact_parameter_variant_for_each_trial(
    tmp_path,
):
    _, population, resolver = _environment(
        tmp_path
    )

    resolved = {
        trial.parameter_configuration_fingerprint: (
            resolver.resolve(trial.trial_id)
        )
        for trial in population.trials
    }

    assert len(resolved) == 2

    configurations = {
        tuple(
            sorted(
                plan.parameter_configuration.items()
            )
        )
        for plan in resolved.values()
    }

    assert configurations == {
        (("fast", 5), ("slow", 20)),
        (("fast", 10), ("slow", 40)),
    }

    for trial in population.trials:
        plan = resolved[
            trial.parameter_configuration_fingerprint
        ]

        assert plan.trial_id == trial.trial_id
        assert plan.instrument_id == "NSE:A"
        assert (
            plan.strategy_procedure_id
            == "sma-crossover-v1"
        )
        assert plan.timeframe == "1d"
        assert plan.research_range == TimeRange(
            JAN,
            FEB,
        )
        assert plan.trial_range == TimeRange(
            JAN,
            FEB,
        )
        assert plan.timezone == "UTC"
        assert plan.initial_capital == 1_000_000.0
        assert (
            plan.risk_economic_configuration[
                "risk_per_trade_pct"
            ]
            == 1.0
        )
        assert (
            plan.data_treatment_basis[
                "price_adjustment"
            ]
            == "raw"
        )
        assert (
            plan.repository_revision
            == "repo-m94d-plan"
        )
        assert (
            plan.evidence_reuse_policy
            is EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        )


def test_fails_closed_when_trial_parameter_fingerprint_is_not_in_plan(
    tmp_path,
):
    catalog, population, resolver = _environment(
        tmp_path
    )

    trial = population.trials[0]

    impossible = canonical_fingerprint(
        {"fast": 999, "slow": 1000},
        schema="kanasu.study-parameter-variant.v1",
    )

    with sqlite3.connect(
        catalog.database_path
    ) as connection:
        connection.execute(
            """
            UPDATE trials
            SET parameter_configuration_fingerprint = ?
            WHERE trial_id = ?
            """,
            (
                impossible,
                trial.trial_id,
            ),
        )
        connection.commit()

    with pytest.raises(
        ValueError,
        match=(
            "parameter configuration fingerprint "
            "is not present"
        ),
    ):
        resolver.resolve(
            trial.trial_id
        )



def test_fails_closed_when_membership_episode_exceeds_registered_range(
    tmp_path,
):
    catalog, population, resolver = _environment(
        tmp_path
    )

    trial = population.trials[0]

    with sqlite3.connect(
        catalog.database_path
    ) as connection:
        connection.execute(
            """
            UPDATE trials
            SET membership_episode_end = ?
            WHERE trial_id = ?
            """,
            (
                MAR.isoformat(
                    timespec="microseconds"
                ),
                trial.trial_id,
            ),
        )
        connection.commit()

    with pytest.raises(
        ValueError,
        match=(
            "membership episode is outside "
            "the registered StudyRevision research range"
        ),
    ):
        resolver.resolve(
            trial.trial_id
        )
