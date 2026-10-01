from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import sqlite3

import pytest

from core.config.app_config import AppConfig
from core.market_data.historical_coverage import TimeRange
from core.research.models.registered_study import (
    EvidenceReusePolicy,
    ResearchJob,
    ResearchJobState,
    Study,
    TrialDisposition,
)
from core.research.models.research_catalog import (
    ComputationKind,
    ResearchArtifact,
    ResearchArtifactKind,
    RunAttemptState,
)
from core.research.models.universe import (
    UniverseDefinition,
    UniverseQuality,
    UniverseSnapshot,
)
from core.research.registered_study_registration import (
    RegisteredStudyRegistrationService,
)
from core.research.reproducibility import (
    canonical_fingerprint,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
)
from core.research.research_job_queue import (
    ResearchJobQueueService,
)
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)


UTC = timezone.utc

JAN = datetime(2020, 1, 1, tzinfo=UTC)
FEB = datetime(2020, 2, 1, tzinfo=UTC)
MAR = datetime(2020, 3, 1, tzinfo=UTC)
APR = datetime(2020, 4, 1, tzinfo=UTC)
MAY = datetime(2020, 5, 1, tzinfo=UTC)
JUN = datetime(2020, 6, 1, tzinfo=UTC)


def _fingerprint(
    label: str,
    *,
    schema: str,
) -> str:
    return canonical_fingerprint(
        {
            "label": label,
        },
        schema=schema,
    )


def _resolve_spec(
    catalog: SQLiteResearchCatalogStore,
    label: str,
):
    manifest_id = _fingerprint(
        f"manifest-{label}",
        schema="kanasu.test.m94d2-manifest.v1",
    )

    catalog.save_artifact(
        ResearchArtifact(
            artifact_id=manifest_id,
            artifact_kind=(
                ResearchArtifactKind.BACKTEST_RUN_MANIFEST
            ),
            schema_id="kanasu.test.m94d2-manifest.v1",
            relative_path=(
                "m94d2/"
                + manifest_id.split(":", 1)[1]
                + ".json"
            ),
            byte_count=2,
            created_at=APR,
        )
    )

    return catalog.resolve_experiment_spec(
        computation_kind=ComputationKind.BACKTEST,
        manifest_artifact_id=manifest_id,
        dataset_fingerprint=_fingerprint(
            f"dataset-{label}",
            schema="kanasu.test.m94d2-dataset.v1",
        ),
        configuration_fingerprint=_fingerprint(
            f"config-{label}",
            schema="kanasu.test.m94d2-config.v1",
        ),
        repository_revision="repo-m94d2",
        created_at=APR,
    )


def _environment(
    tmp_path,
    *,
    attempt_id_factory=None,
    claim_job: bool = True,
):
    catalog = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3",
        attempt_id_factory=attempt_id_factory,
    )

    artifact_store = (
        ContentAddressedResearchArtifactStore(
            tmp_path / "artifacts"
        )
    )

    catalog.save_study(
        Study(
            study_id="study-m94d2",
            created_at=JAN,
            display_title="M9.4d2 atomic binding",
        )
    )

    registration = (
        RegisteredStudyRegistrationService(
            catalog_store=catalog,
            artifact_store=artifact_store,
        )
    )

    definition = UniverseDefinition(
        name="m94d2-universe",
        selection_spec="fixture",
    )

    snapshot = UniverseSnapshot(
        definition=definition,
        members=("NSE:A",),
        quality=UniverseQuality.PIT_VERIFIED,
        as_of=JAN,
        provenance_refs=("m94d2-source",),
        effective_from=JAN,
        effective_to=FEB,
    )

    population = (
        registration.register_study_revision(
            study_id="study-m94d2",
            research_intent="M9.4d2 atomic linkage",
            strategy_procedure_id="fixture-v1",
            timeframe="1d",
            research_range=TimeRange(
                JAN,
                FEB,
            ),
            timezone="UTC",
            initial_capital=1_000_000.0,
            risk_economic_configuration={
                "risk_per_trade_pct": 1.0,
            },
            parameter_variants=(
                {
                    "variant": 1,
                },
            ),
            universe_definition=definition,
            universe_snapshots=(
                snapshot,
            ),
            require_point_in_time=True,
            data_treatment_basis={
                "adjustment": "raw",
            },
            repository_revision="repo-m94d2",
            evidence_reuse_policy=(
                EvidenceReusePolicy.FORCE_NEW_EXECUTION
            ),
            registered_at=MAR,
        )
    )

    queue = ResearchJobQueueService(
        catalog_store=catalog,
        app_config=AppConfig(
            research_max_workers=1
        ),
    )

    revision_id = (
        population.revision.study_revision_id
    )

    queue.start_revision(
        revision_id,
        started_at=APR,
    )

    trial = population.trials[0]

    queued_jobs = (
        catalog.list_research_jobs_for_trial(
            trial.trial_id
        )
    )

    assert len(queued_jobs) == 1

    job = queued_jobs[0]

    if claim_job:
        claimed = (
            catalog.claim_next_research_job(
                revision_id,
                "worker-m94d2",
                MAY,
                max_running_jobs=1,
            )
        )

        assert claimed is not None
        job = claimed

    spec = _resolve_spec(
        catalog,
        "primary",
    )

    return (
        catalog,
        trial,
        job,
        spec,
    )


def _attempt_count(
    catalog: SQLiteResearchCatalogStore,
) -> int:
    with closing(
        sqlite3.connect(
            catalog.database_path
        )
    ) as connection:
        return connection.execute(
            """
            SELECT COUNT(*)
            FROM run_attempts
            """
        ).fetchone()[0]


def _bind_trial_direct(
    catalog: SQLiteResearchCatalogStore,
    trial_id: str,
    experiment_spec_id: str,
) -> None:
    with closing(
        sqlite3.connect(
            catalog.database_path
        )
    ) as connection:
        cursor = connection.execute(
            """
            UPDATE trials
            SET experiment_spec_id = ?
            WHERE trial_id = ?
            """,
            (
                experiment_spec_id,
                trial_id,
            ),
        )

        assert cursor.rowcount == 1
        connection.commit()


def _link_job_direct(
    catalog: SQLiteResearchCatalogStore,
    job_id: str,
    attempt_id: str,
) -> None:
    with closing(
        sqlite3.connect(
            catalog.database_path
        )
    ) as connection:
        cursor = connection.execute(
            """
            UPDATE research_jobs
            SET attempt_id = ?
            WHERE job_id = ?
            """,
            (
                attempt_id,
                job_id,
            ),
        )

        assert cursor.rowcount == 1
        connection.commit()


def test_atomic_bind_creates_attempt_and_links_running_job(
    tmp_path,
):
    (
        catalog,
        trial,
        job,
        spec,
    ) = _environment(tmp_path)

    (
        updated_trial,
        updated_job,
        attempt,
    ) = (
        catalog
        .bind_trial_spec_create_attempt_for_running_job(
            job_id=job.job_id,
            experiment_spec_id=(
                spec.experiment_spec_id
            ),
            attempt_created_at=JUN,
        )
    )

    assert (
        updated_trial.experiment_spec_id
        == spec.experiment_spec_id
    )

    assert (
        updated_trial.disposition
        is TrialDisposition.PENDING
    )

    assert (
        updated_job.state
        is ResearchJobState.RUNNING
    )

    assert (
        updated_job.attempt_id
        == attempt.attempt_id
    )

    assert (
        attempt.experiment_spec_id
        == spec.experiment_spec_id
    )

    assert (
        attempt.state
        is RunAttemptState.RUNNING
    )

    assert attempt.created_at == JUN

    assert catalog.load_trial(
        trial.trial_id
    ) == updated_trial

    assert catalog.load_research_job(
        job.job_id
    ) == updated_job

    assert catalog.load_run_attempt(
        attempt.attempt_id
    ) == attempt

    assert _attempt_count(catalog) == 1


def test_existing_matching_trial_binding_allows_new_job_attempt(
    tmp_path,
):
    (
        catalog,
        trial,
        job,
        spec,
    ) = _environment(tmp_path)

    _bind_trial_direct(
        catalog,
        trial.trial_id,
        spec.experiment_spec_id,
    )

    (
        updated_trial,
        updated_job,
        attempt,
    ) = (
        catalog
        .bind_trial_spec_create_attempt_for_running_job(
            job_id=job.job_id,
            experiment_spec_id=(
                spec.experiment_spec_id
            ),
            attempt_created_at=JUN,
        )
    )

    assert (
        updated_trial.experiment_spec_id
        == spec.experiment_spec_id
    )

    assert (
        updated_job.attempt_id
        == attempt.attempt_id
    )

    assert _attempt_count(catalog) == 1


def test_conflicting_trial_binding_rolls_back_without_attempt(
    tmp_path,
):
    (
        catalog,
        trial,
        job,
        primary_spec,
    ) = _environment(tmp_path)

    other_spec = _resolve_spec(
        catalog,
        "other",
    )

    _bind_trial_direct(
        catalog,
        trial.trial_id,
        other_spec.experiment_spec_id,
    )

    with pytest.raises(
        ValueError,
        match="different ExperimentSpec",
    ):
        (
            catalog
            .bind_trial_spec_create_attempt_for_running_job(
                job_id=job.job_id,
                experiment_spec_id=(
                    primary_spec.experiment_spec_id
                ),
                attempt_created_at=JUN,
            )
        )

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    persisted_job = catalog.load_research_job(
        job.job_id
    )

    assert persisted_trial is not None
    assert persisted_job is not None

    assert (
        persisted_trial.experiment_spec_id
        == other_spec.experiment_spec_id
    )

    assert persisted_job.attempt_id is None
    assert _attempt_count(catalog) == 0


def test_job_already_linked_to_attempt_fails_without_second_attempt(
    tmp_path,
):
    (
        catalog,
        trial,
        job,
        spec,
    ) = _environment(tmp_path)

    existing_attempt = (
        catalog.create_running_attempt(
            experiment_spec_id=(
                spec.experiment_spec_id
            ),
            created_at=JUN,
        )
    )

    _link_job_direct(
        catalog,
        job.job_id,
        existing_attempt.attempt_id,
    )

    with pytest.raises(
        ValueError,
        match="at most one new RunAttempt",
    ):
        (
            catalog
            .bind_trial_spec_create_attempt_for_running_job(
                job_id=job.job_id,
                experiment_spec_id=(
                    spec.experiment_spec_id
                ),
                attempt_created_at=JUN,
            )
        )

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_trial is not None
    assert persisted_trial.experiment_spec_id is None

    assert _attempt_count(catalog) == 1


def test_non_running_job_cannot_create_attempt(
    tmp_path,
):
    (
        catalog,
        trial,
        job,
        spec,
    ) = _environment(
        tmp_path,
        claim_job=False,
    )

    assert job.state is ResearchJobState.QUEUED

    with pytest.raises(
        ValueError,
        match="must be RUNNING",
    ):
        (
            catalog
            .bind_trial_spec_create_attempt_for_running_job(
                job_id=job.job_id,
                experiment_spec_id=(
                    spec.experiment_spec_id
                ),
                attempt_created_at=JUN,
            )
        )

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_trial is not None
    assert persisted_trial.experiment_spec_id is None
    assert _attempt_count(catalog) == 0


def test_non_pending_trial_cannot_create_attempt(
    tmp_path,
):
    (
        catalog,
        trial,
        job,
        spec,
    ) = _environment(tmp_path)

    with closing(
        sqlite3.connect(
            catalog.database_path
        )
    ) as connection:
        cursor = connection.execute(
            """
            UPDATE trials
            SET
                disposition = ?,
                disposition_at = ?
            WHERE trial_id = ?
            """,
            (
                TrialDisposition.FAILED.value,
                JUN.isoformat(
                    timespec="microseconds"
                ),
                trial.trial_id,
            ),
        )

        assert cursor.rowcount == 1
        connection.commit()

    with pytest.raises(
        ValueError,
        match="Trial must be PENDING",
    ):
        (
            catalog
            .bind_trial_spec_create_attempt_for_running_job(
                job_id=job.job_id,
                experiment_spec_id=(
                    spec.experiment_spec_id
                ),
                attempt_created_at=JUN,
            )
        )

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.FAILED
    )

    assert persisted_trial.experiment_spec_id is None
    assert _attempt_count(catalog) == 0


def test_missing_experiment_spec_rolls_back(
    tmp_path,
):
    (
        catalog,
        trial,
        job,
        _spec,
    ) = _environment(tmp_path)

    missing_spec_id = _fingerprint(
        "missing-spec",
        schema="kanasu.test.m94d2-missing-spec.v1",
    )

    with pytest.raises(
        ValueError,
        match="ExperimentSpec does not exist",
    ):
        (
            catalog
            .bind_trial_spec_create_attempt_for_running_job(
                job_id=job.job_id,
                experiment_spec_id=(
                    missing_spec_id
                ),
                attempt_created_at=JUN,
            )
        )

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    persisted_job = catalog.load_research_job(
        job.job_id
    )

    assert persisted_trial is not None
    assert persisted_job is not None

    assert persisted_trial.experiment_spec_id is None
    assert persisted_job.attempt_id is None
    assert _attempt_count(catalog) == 0


def test_attempt_created_at_cannot_precede_job_claim_and_rolls_back(
    tmp_path,
):
    (
        catalog,
        trial,
        job,
        spec,
    ) = _environment(tmp_path)

    assert job.claimed_at == MAY

    with pytest.raises(
        ValueError,
        match=(
            "attempt_created_at cannot precede "
            "ResearchJob claimed_at"
        ),
    ):
        (
            catalog
            .bind_trial_spec_create_attempt_for_running_job(
                job_id=job.job_id,
                experiment_spec_id=(
                    spec.experiment_spec_id
                ),
                attempt_created_at=APR,
            )
        )

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    persisted_job = catalog.load_research_job(
        job.job_id
    )

    assert persisted_trial is not None
    assert persisted_job is not None

    assert persisted_trial.experiment_spec_id is None
    assert persisted_job.attempt_id is None
    assert persisted_job.state is ResearchJobState.RUNNING

    assert _attempt_count(catalog) == 0


def test_attempt_id_collision_rolls_back_trial_binding_and_job_link(
    tmp_path,
):
    (
        catalog,
        trial,
        job,
        spec,
    ) = _environment(
        tmp_path,
        attempt_id_factory=(
            lambda: "attempt-collision"
        ),
    )

    existing_attempt = (
        catalog.create_running_attempt(
            experiment_spec_id=(
                spec.experiment_spec_id
            ),
            created_at=MAY,
        )
    )

    assert (
        existing_attempt.attempt_id
        == "attempt-collision"
    )

    with pytest.raises(
        ValueError,
        match="atomic Trial/ResearchJob/RunAttempt link",
    ):
        (
            catalog
            .bind_trial_spec_create_attempt_for_running_job(
                job_id=job.job_id,
                experiment_spec_id=(
                    spec.experiment_spec_id
                ),
                attempt_created_at=JUN,
            )
        )

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    persisted_job = catalog.load_research_job(
        job.job_id
    )

    assert persisted_trial is not None
    assert persisted_job is not None

    assert persisted_trial.experiment_spec_id is None
    assert persisted_job.attempt_id is None

    assert _attempt_count(catalog) == 1


def test_transaction_failure_leaves_no_partial_identity_links(
    tmp_path,
):
    (
        catalog,
        trial,
        job,
        spec,
    ) = _environment(tmp_path)

    with closing(
        sqlite3.connect(
            catalog.database_path
        )
    ) as connection:
        connection.execute(
            """
            CREATE TRIGGER m94d2_fail_job_attempt_link
            BEFORE UPDATE OF attempt_id
            ON research_jobs
            WHEN NEW.attempt_id IS NOT NULL
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'm94d2 injected job-link failure'
                );
            END
            """
        )

        connection.commit()

    with pytest.raises(
        ValueError,
        match="atomic Trial/ResearchJob/RunAttempt link",
    ):
        (
            catalog
            .bind_trial_spec_create_attempt_for_running_job(
                job_id=job.job_id,
                experiment_spec_id=(
                    spec.experiment_spec_id
                ),
                attempt_created_at=JUN,
            )
        )

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    persisted_job = catalog.load_research_job(
        job.job_id
    )

    assert persisted_trial is not None
    assert persisted_job is not None

    assert persisted_trial.experiment_spec_id is None
    assert persisted_job.attempt_id is None
    assert _attempt_count(catalog) == 0
