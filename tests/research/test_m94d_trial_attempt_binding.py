from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import sqlite3

import pytest

from core.config.app_config import AppConfig
from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange
from core.research.models.dataset import (
    DatasetIdentityV2,
    DatasetProvenance,
    PriceAdjustmentBasis,
)
from core.research.models.dataset_reference import (
    DatasetReference,
)
from core.research.models.registered_study import (
    EvidenceReusePolicy,
    ResearchJob,
    ResearchJobCompletionKind,
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
from core.research.models.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceStatus,
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
    BACKTEST_RESULT_SCHEMA,
    BACKTEST_RUN_MANIFEST_SCHEMA,
    canonical_fingerprint,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
    research_artifact_reference,
)
from core.research.research_job_queue import (
    ResearchJobQueueService,
)
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)
from core.runtime.dataset_context import DatasetContext


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
        schema=BACKTEST_RUN_MANIFEST_SCHEMA,
    )

    catalog.save_artifact(
        ResearchArtifact(
            artifact_id=manifest_id,
            artifact_kind=(
                ResearchArtifactKind.BACKTEST_RUN_MANIFEST
            ),
            schema_id=BACKTEST_RUN_MANIFEST_SCHEMA,
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
    evidence_reuse_policy=EvidenceReusePolicy.FORCE_NEW_EXECUTION,
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
            evidence_reuse_policy=evidence_reuse_policy,
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



def test_m94e_cancel_request_blocks_fresh_attempt_binding(
    tmp_path,
):
    (
        catalog,
        trial,
        job,
        spec,
    ) = _environment(tmp_path)

    requested = (
        catalog
        .request_running_research_job_cancellation(
            job_id=job.job_id,
            requested_at=JUN,
        )
    )

    assert requested.cancel_requested_at == JUN

    with pytest.raises(
        ValueError,
        match="cancellation",
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
    assert (
        persisted_trial.disposition
        is TrialDisposition.PENDING
    )
    assert persisted_trial.experiment_spec_id is None
    assert (
        persisted_job.state
        is ResearchJobState.RUNNING
    )
    assert persisted_job.attempt_id is None
    assert persisted_job.cancel_requested_at == JUN
    assert _attempt_count(catalog) == 0


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


def test_succeeded_attempt_lookup_is_exact_and_deterministic(
    tmp_path,
):
    ids = iter(
        (
            "attempt-b",
            "attempt-a",
            "attempt-failed",
            "attempt-other",
        )
    )

    catalog = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3",
        attempt_id_factory=lambda: next(ids),
    )

    primary = _resolve_spec(
        catalog,
        "lookup-primary",
    )
    other = _resolve_spec(
        catalog,
        "lookup-other",
    )

    attempt_b = catalog.create_running_attempt(
        experiment_spec_id=primary.experiment_spec_id,
        created_at=APR,
    )
    attempt_a = catalog.create_running_attempt(
        experiment_spec_id=primary.experiment_spec_id,
        created_at=APR,
    )
    attempt_failed = catalog.create_running_attempt(
        experiment_spec_id=primary.experiment_spec_id,
        created_at=APR,
    )
    attempt_other = catalog.create_running_attempt(
        experiment_spec_id=other.experiment_spec_id,
        created_at=APR,
    )

    for attempt in (attempt_b, attempt_a):
        catalog.terminalize_attempt(
            attempt.attempt_id,
            state=RunAttemptState.SUCCEEDED,
            terminal_at=MAY,
        )

    catalog.terminalize_attempt(
        attempt_failed.attempt_id,
        state=RunAttemptState.FAILED,
        terminal_at=MAY,
        failure_classification="fixture_failure",
    )

    catalog.terminalize_attempt(
        attempt_other.attempt_id,
        state=RunAttemptState.SUCCEEDED,
        terminal_at=MAY,
    )

    found = (
        catalog.list_succeeded_attempts_for_experiment_spec(
            primary.experiment_spec_id
        )
    )

    assert tuple(
        attempt.attempt_id
        for attempt in found
    ) == (
        "attempt-a",
        "attempt-b",
    )


def _persist_reuse_dataset_reference(
    catalog,
    artifact_store,
    *,
    close=101.0,
    source="fixture:m94h2-reuse",
):
    candle = Candle(
        timestamp=JAN,
        open=100.0,
        high=max(102.0, close),
        low=99.0,
        close=close,
        volume=1000.0,
    )

    identity = DatasetIdentityV2(
        instrument_id="NSE:A",
        requested_range=TimeRange(
            JAN,
            FEB,
        ),
        timeframe="1d",
        timezone="UTC",
        price_adjustment_basis=(
            PriceAdjustmentBasis.RAW
        ),
        candles=(candle,),
    )

    reference = DatasetReference(
        identity=identity,
        provenance=DatasetProvenance(
            dataset_id=identity.dataset_id,
            instrument_id="NSE:A",
            requested_range=TimeRange(
                JAN,
                FEB,
            ),
            timeframe="1d",
            timezone="UTC",
            price_adjustment_basis=(
                PriceAdjustmentBasis.RAW
            ),
            source=source,
            coverage=(
                TimeRange(
                    JAN,
                    FEB,
                ),
            ),
            retrieved_at=APR,
        ),
    )

    artifact = (
        artifact_store
        .persist_dataset_reference(
            reference,
            created_at=APR,
        )
    )

    return (
        catalog
        .save_dataset_reference_artifact(
            artifact,
            reference,
        )
    )


def _dataset_reference_artifact_id(
    catalog,
    evidence,
):
    matches = []

    for reference in evidence.artifact_references:
        if not reference.startswith(
            "artifact:"
        ):
            continue

        artifact_id = reference.removeprefix(
            "artifact:"
        )
        artifact = catalog.load_artifact(
            artifact_id
        )

        if (
            artifact is not None
            and artifact.artifact_kind
            is ResearchArtifactKind.DATASET_REFERENCE
        ):
            matches.append(
                artifact_id
            )

    assert len(matches) == 1
    return matches[0]


def _create_reuse_source(
    tmp_path,
    catalog,
    spec,
):
    artifact_store = ContentAddressedResearchArtifactStore(
        tmp_path / "artifacts"
    )

    dataset_artifact = (
        _persist_reuse_dataset_reference(
            catalog,
            artifact_store,
        )
    )

    result_artifact = artifact_store.persist_bytes(
        b'{"m94d":"exact-reuse-source"}',
        artifact_kind=ResearchArtifactKind.BACKTEST_RESULT,
        schema_id=BACKTEST_RESULT_SCHEMA,
        created_at=APR,
    )

    attempt = catalog.create_running_attempt(
        experiment_spec_id=spec.experiment_spec_id,
        created_at=APR,
    )

    evidence = ResearchEvidence(
        evidence_id="evidence-m94d-reuse-source",
        created_at=MAY,
        status=ResearchEvidenceStatus.ACCEPTED,
        dataset_context=DatasetContext(
            symbol="NSE:A",
            timeframe="1d",
            timezone="UTC",
        ),
        requested_range=TimeRange(JAN, FEB),
        dataset_fingerprint=spec.dataset_fingerprint,
        configuration_fingerprint=(
            spec.configuration_fingerprint
        ),
        result_fingerprint=result_artifact.artifact_id,
        provenance=(("fixture", "m94d-exact-reuse"),),
        repository_revision=spec.repository_revision,
        summary="Exact accepted reuse fixture.",
        artifact_references=(
            research_artifact_reference(
                spec.manifest_artifact_id
            ),
            research_artifact_reference(
                result_artifact.artifact_id
            ),
            research_artifact_reference(
                dataset_artifact.artifact_id
            ),
        ),
    )

    terminal = catalog.terminalize_attempt_with_evidence(
        attempt.attempt_id,
        state=RunAttemptState.SUCCEEDED,
        terminal_at=MAY,
        runtime_session_id="runtime-m94d-reuse-source",
        result_artifact=result_artifact,
        evidence=evidence,
    )

    return terminal, evidence, result_artifact


def test_complete_running_job_with_exact_reuse_is_atomic(
    tmp_path,
):
    catalog, trial, job, spec = _environment(
        tmp_path,
        attempt_id_factory=lambda: "attempt-reuse-source",
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
    )

    source, evidence, artifact = _create_reuse_source(
        tmp_path,
        catalog,
        spec,
    )

    dataset_artifact_id = (
        _dataset_reference_artifact_id(
            catalog,
            evidence,
        )
    )

    before_attempts = _attempt_count(catalog)

    updated_trial, updated_job, event = (
        catalog._complete_running_job_with_exact_reuse(
            job_id=job.job_id,
            experiment_spec_id=spec.experiment_spec_id,
            reused_attempt_id=source.attempt_id,
            terminal_at=JUN,
            requested_dataset_reference_artifact_id=(
                dataset_artifact_id
            ),
            source_dataset_reference_artifact_id=(
                dataset_artifact_id
            ),
        )
    )

    assert _attempt_count(catalog) == before_attempts

    assert updated_trial.disposition is TrialDisposition.REUSED
    assert (
        updated_trial.experiment_spec_id
        == spec.experiment_spec_id
    )
    assert updated_trial.reused_attempt_id == source.attempt_id

    assert updated_job.state is ResearchJobState.SUCCEEDED
    assert (
        updated_job.completion_kind
        is ResearchJobCompletionKind.REUSED
    )
    assert updated_job.attempt_id is None
    assert updated_job.reused_attempt_id == source.attempt_id
    assert updated_job.reused_evidence_id == evidence.evidence_id
    assert (
        updated_job.reused_result_artifact_id
        == artifact.artifact_id
    )

    assert event.sequence_number == 2
    assert event.previous_disposition is TrialDisposition.PENDING
    assert event.new_disposition is TrialDisposition.REUSED
    assert event.causing_job_id == job.job_id

    events = catalog.load_trial_disposition_events(
        trial.trial_id
    )
    assert len(events) == 2




def test_m94h2_exact_reuse_rejects_missing_dataset_lineage(
    tmp_path,
):
    catalog, trial, job, spec = _environment(
        tmp_path,
        attempt_id_factory=(
            lambda: "attempt-h2-missing-lineage"
        ),
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
    )

    source, _, _ = _create_reuse_source(
        tmp_path,
        catalog,
        spec,
    )

    with pytest.raises(
        ValueError,
        match=(
            "requires requested and source "
            "DatasetReference lineage"
        ),
    ):
        catalog._complete_running_job_with_exact_reuse(
            job_id=job.job_id,
            experiment_spec_id=(
                spec.experiment_spec_id
            ),
            reused_attempt_id=(
                source.attempt_id
            ),
            terminal_at=JUN,
        )

    assert (
        catalog.load_trial(
            trial.trial_id
        ).disposition
        is TrialDisposition.PENDING
    )

    assert (
        catalog.load_research_job(
            job.job_id
        ).state
        is ResearchJobState.RUNNING
    )


def test_m94h2_exact_reuse_rejects_incompatible_dataset_lineage(
    tmp_path,
):
    catalog, trial, job, spec = _environment(
        tmp_path,
        attempt_id_factory=(
            lambda: "attempt-h2-incompatible-lineage"
        ),
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
    )

    source, evidence, _ = _create_reuse_source(
        tmp_path,
        catalog,
        spec,
    )

    source_dataset_artifact_id = (
        _dataset_reference_artifact_id(
            catalog,
            evidence,
        )
    )

    artifact_store = (
        ContentAddressedResearchArtifactStore(
            tmp_path / "artifacts"
        )
    )

    requested_artifact = (
        _persist_reuse_dataset_reference(
            catalog,
            artifact_store,
            close=103.0,
            source="fixture:m94h2-incompatible",
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "DatasetReference identities are incompatible"
        ),
    ):
        catalog._complete_running_job_with_exact_reuse(
            job_id=job.job_id,
            experiment_spec_id=(
                spec.experiment_spec_id
            ),
            reused_attempt_id=(
                source.attempt_id
            ),
            terminal_at=JUN,
            requested_dataset_reference_artifact_id=(
                requested_artifact.artifact_id
            ),
            source_dataset_reference_artifact_id=(
                source_dataset_artifact_id
            ),
        )

    assert (
        catalog.load_trial(
            trial.trial_id
        ).disposition
        is TrialDisposition.PENDING
    )

    assert (
        catalog.load_research_job(
            job.job_id
        ).state
        is ResearchJobState.RUNNING
    )


def test_m94e_cancel_request_blocks_exact_reuse_terminalization(
    tmp_path,
):
    catalog, trial, job, spec = _environment(
        tmp_path,
        attempt_id_factory=lambda: "attempt-m94e-reuse-source",
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
    )

    source, _, _ = _create_reuse_source(
        tmp_path,
        catalog,
        spec,
    )

    before_attempts = _attempt_count(catalog)

    requested = (
        catalog
        .request_running_research_job_cancellation(
            job_id=job.job_id,
            requested_at=JUN,
        )
    )

    assert requested.cancel_requested_at == JUN

    with pytest.raises(
        ValueError,
        match="cancellation",
    ):
        catalog._complete_running_job_with_exact_reuse(
            job_id=job.job_id,
            experiment_spec_id=(
                spec.experiment_spec_id
            ),
            reused_attempt_id=source.attempt_id,
            terminal_at=JUN,
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
        persisted_trial.disposition
        is TrialDisposition.PENDING
    )
    assert persisted_trial.experiment_spec_id is None
    assert (
        persisted_job.state
        is ResearchJobState.RUNNING
    )
    assert persisted_job.attempt_id is None
    assert persisted_job.cancel_requested_at == JUN
    assert _attempt_count(catalog) == before_attempts


def test_exact_reuse_rejects_evidence_missing_manifest_reference(
    tmp_path,
):
    catalog, trial, job, spec = _environment(
        tmp_path,
        attempt_id_factory=(
            lambda: "attempt-reuse-missing-manifest-reference"
        ),
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
    )

    source, evidence, artifact = _create_reuse_source(
        tmp_path,
        catalog,
        spec,
    )

    with sqlite3.connect(catalog.database_path) as connection:
        connection.execute(
            """
            UPDATE research_evidence
            SET artifact_references = ?
            WHERE evidence_id = ?
            """,
            (
                (
                    '["'
                    + research_artifact_reference(
                        artifact.artifact_id
                    )
                    + '"]'
                ),
                evidence.evidence_id,
            ),
        )
        connection.commit()

    with pytest.raises(
        ValueError,
        match="must reference the exact Backtest manifest artifact",
    ):
        catalog._complete_running_job_with_exact_reuse(
            job_id=job.job_id,
            experiment_spec_id=spec.experiment_spec_id,
            reused_attempt_id=source.attempt_id,
            terminal_at=JUN,
        )

    assert (
        catalog.load_trial(trial.trial_id).disposition
        is TrialDisposition.PENDING
    )
    assert (
        catalog.load_research_job(job.job_id).state
        is ResearchJobState.RUNNING
    )
    assert len(
        catalog.load_trial_disposition_events(
            trial.trial_id
        )
    ) == 1



def test_exact_reuse_respects_force_new_execution_policy(
    tmp_path,
):
    catalog, trial, job, spec = _environment(
        tmp_path,
        attempt_id_factory=lambda: "attempt-force-new-source",
    )

    source, _, _ = _create_reuse_source(
        tmp_path,
        catalog,
        spec,
    )

    before_attempts = _attempt_count(catalog)

    with pytest.raises(
        ValueError,
        match="forbids evidence reuse",
    ):
        catalog._complete_running_job_with_exact_reuse(
            job_id=job.job_id,
            experiment_spec_id=spec.experiment_spec_id,
            reused_attempt_id=source.attempt_id,
            terminal_at=JUN,
        )

    assert _attempt_count(catalog) == before_attempts
    assert (
        catalog.load_trial(trial.trial_id).disposition
        is TrialDisposition.PENDING
    )
    assert (
        catalog.load_research_job(job.job_id).state
        is ResearchJobState.RUNNING
    )
    assert len(
        catalog.load_trial_disposition_events(trial.trial_id)
    ) == 1


def test_exact_reuse_rejects_attempt_from_different_spec(
    tmp_path,
):
    catalog, trial, job, spec = _environment(
        tmp_path,
        attempt_id_factory=lambda: "attempt-wrong-spec-source",
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
    )

    other_spec = _resolve_spec(
        catalog,
        "reuse-other",
    )

    source, _, _ = _create_reuse_source(
        tmp_path,
        catalog,
        other_spec,
    )

    with pytest.raises(
        ValueError,
        match="successful exact ExperimentSpec",
    ):
        catalog._complete_running_job_with_exact_reuse(
            job_id=job.job_id,
            experiment_spec_id=spec.experiment_spec_id,
            reused_attempt_id=source.attempt_id,
            terminal_at=JUN,
        )

    assert (
        catalog.load_trial(trial.trial_id).disposition
        is TrialDisposition.PENDING
    )
    assert (
        catalog.load_research_job(job.job_id).state
        is ResearchJobState.RUNNING
    )
    assert len(
        catalog.load_trial_disposition_events(trial.trial_id)
    ) == 1


def _fresh_success_material(
    tmp_path,
    spec,
):
    artifact_store = ContentAddressedResearchArtifactStore(
        tmp_path / "artifacts"
    )

    result_artifact = artifact_store.persist_bytes(
        b'{"m94d":"fresh-execution-result"}',
        artifact_kind=ResearchArtifactKind.BACKTEST_RESULT,
        schema_id=BACKTEST_RESULT_SCHEMA,
        created_at=JUN,
    )

    evidence = ResearchEvidence(
        evidence_id="evidence-m94d-fresh-success",
        created_at=JUN,
        status=ResearchEvidenceStatus.ACCEPTED,
        dataset_context=DatasetContext(
            symbol="NSE:A",
            timeframe="1d",
            timezone="UTC",
        ),
        requested_range=TimeRange(JAN, FEB),
        dataset_fingerprint=spec.dataset_fingerprint,
        configuration_fingerprint=(
            spec.configuration_fingerprint
        ),
        result_fingerprint=result_artifact.artifact_id,
        provenance=(("fixture", "m94d-fresh-success"),),
        repository_revision=spec.repository_revision,
        summary="Fresh successful execution fixture.",
        artifact_references=(
            research_artifact_reference(
                result_artifact.artifact_id
            ),
        ),
    )

    return evidence, result_artifact


def test_fresh_success_terminalizes_attempt_job_trial_and_event_atomically(
    tmp_path,
):
    catalog, trial, job, spec = _environment(
        tmp_path,
        attempt_id_factory=lambda: "attempt-fresh-success",
    )

    _, linked_job, attempt = (
        catalog.bind_trial_spec_create_attempt_for_running_job(
            job_id=job.job_id,
            experiment_spec_id=spec.experiment_spec_id,
            attempt_created_at=MAY,
        )
    )

    assert linked_job.attempt_id == attempt.attempt_id

    evidence, result_artifact = _fresh_success_material(
        tmp_path,
        spec,
    )

    before_attempts = _attempt_count(catalog)

    terminal = (
        catalog.terminalize_running_job_attempt_with_evidence(
            attempt.attempt_id,
            job_id=job.job_id,
            state=RunAttemptState.SUCCEEDED,
            terminal_at=JUN,
            runtime_session_id="runtime-m94d-fresh-success",
            result_artifact=result_artifact,
            evidence=evidence,
        )
    )

    assert _attempt_count(catalog) == before_attempts
    assert terminal.state is RunAttemptState.SUCCEEDED
    assert terminal.attempt_id == attempt.attempt_id
    assert (
        terminal.result_artifact_id
        == result_artifact.artifact_id
    )
    assert terminal.evidence_id == evidence.evidence_id

    persisted_job = catalog.load_research_job(
        job.job_id
    )
    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_job is not None
    assert persisted_trial is not None

    assert persisted_job.state is ResearchJobState.SUCCEEDED
    assert (
        persisted_job.completion_kind
        is ResearchJobCompletionKind.EXECUTED
    )
    assert persisted_job.attempt_id == attempt.attempt_id
    assert persisted_job.reused_attempt_id is None

    assert (
        persisted_trial.disposition
        is TrialDisposition.EXECUTED
    )
    assert (
        persisted_trial.experiment_spec_id
        == spec.experiment_spec_id
    )

    events = catalog.load_trial_disposition_events(
        trial.trial_id
    )

    assert len(events) == 2
    assert (
        events[-1].previous_disposition
        is TrialDisposition.PENDING
    )
    assert (
        events[-1].new_disposition
        is TrialDisposition.EXECUTED
    )
    assert events[-1].causing_job_id == job.job_id


def test_fresh_failure_terminalizes_attempt_job_trial_and_event_atomically(
    tmp_path,
):
    catalog, trial, job, spec = _environment(
        tmp_path,
        attempt_id_factory=lambda: "attempt-fresh-failure",
    )

    _, _, attempt = (
        catalog.bind_trial_spec_create_attempt_for_running_job(
            job_id=job.job_id,
            experiment_spec_id=spec.experiment_spec_id,
            attempt_created_at=MAY,
        )
    )

    evidence = ResearchEvidence(
        evidence_id="evidence-m94d-fresh-failure",
        created_at=JUN,
        status=ResearchEvidenceStatus.FAILED,
        dataset_context=DatasetContext(
            symbol="NSE:A",
            timeframe="1d",
            timezone="UTC",
        ),
        requested_range=TimeRange(JAN, FEB),
        dataset_fingerprint=spec.dataset_fingerprint,
        configuration_fingerprint=(
            spec.configuration_fingerprint
        ),
        provenance=(("fixture", "m94d-fresh-failure"),),
        repository_revision=spec.repository_revision,
        summary="Fresh failed execution fixture.",
    )

    before_attempts = _attempt_count(catalog)

    terminal = (
        catalog.terminalize_running_job_attempt_with_evidence(
            attempt.attempt_id,
            job_id=job.job_id,
            state=RunAttemptState.FAILED,
            terminal_at=JUN,
            evidence=evidence,
            failure_classification="fixture_failure",
            failure_message="expected M9.4d failure",
        )
    )

    assert _attempt_count(catalog) == before_attempts
    assert terminal.state is RunAttemptState.FAILED
    assert terminal.evidence_id == evidence.evidence_id
    assert terminal.result_artifact_id is None

    persisted_job = catalog.load_research_job(
        job.job_id
    )
    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_job is not None
    assert persisted_trial is not None

    assert persisted_job.state is ResearchJobState.FAILED
    assert persisted_job.completion_kind is None
    assert persisted_job.attempt_id == attempt.attempt_id
    assert (
        persisted_job.failure_classification
        == "fixture_failure"
    )

    assert (
        persisted_trial.disposition
        is TrialDisposition.FAILED
    )
    assert (
        persisted_trial.failure_classification
        == "fixture_failure"
    )

    events = catalog.load_trial_disposition_events(
        trial.trial_id
    )

    assert len(events) == 2
    assert (
        events[-1].previous_disposition
        is TrialDisposition.PENDING
    )
    assert (
        events[-1].new_disposition
        is TrialDisposition.FAILED
    )
    assert events[-1].causing_job_id == job.job_id




def test_fresh_success_rejects_failure_metadata_without_mutation(
    tmp_path,
):
    catalog, trial, job, spec = _environment(
        tmp_path,
        attempt_id_factory=(
            lambda: "attempt-success-failure-metadata"
        ),
    )

    _, _, attempt = (
        catalog.bind_trial_spec_create_attempt_for_running_job(
            job_id=job.job_id,
            experiment_spec_id=spec.experiment_spec_id,
            attempt_created_at=MAY,
        )
    )

    evidence, result_artifact = _fresh_success_material(
        tmp_path,
        spec,
    )

    with pytest.raises(
        ValueError,
        match="cannot carry failure metadata",
    ):
        catalog.terminalize_running_job_attempt_with_evidence(
            attempt.attempt_id,
            job_id=job.job_id,
            state=RunAttemptState.SUCCEEDED,
            terminal_at=JUN,
            result_artifact=result_artifact,
            evidence=evidence,
            failure_classification="impossible_success_failure",
        )

    assert (
        catalog.load_run_attempt(attempt.attempt_id).state
        is RunAttemptState.RUNNING
    )
    assert (
        catalog.load_research_job(job.job_id).state
        is ResearchJobState.RUNNING
    )
    assert (
        catalog.load_trial(trial.trial_id).disposition
        is TrialDisposition.PENDING
    )


def test_fresh_failure_rejects_result_artifact_without_mutation(
    tmp_path,
):
    catalog, trial, job, spec = _environment(
        tmp_path,
        attempt_id_factory=(
            lambda: "attempt-failure-result-artifact"
        ),
    )

    _, _, attempt = (
        catalog.bind_trial_spec_create_attempt_for_running_job(
            job_id=job.job_id,
            experiment_spec_id=spec.experiment_spec_id,
            attempt_created_at=MAY,
        )
    )

    evidence, result_artifact = _fresh_success_material(
        tmp_path,
        spec,
    )

    failed_evidence = ResearchEvidence(
        evidence_id="evidence-m94d-impossible-failed-result",
        created_at=JUN,
        status=ResearchEvidenceStatus.FAILED,
        dataset_context=evidence.dataset_context,
        requested_range=evidence.requested_range,
        dataset_fingerprint=spec.dataset_fingerprint,
        configuration_fingerprint=(
            spec.configuration_fingerprint
        ),
        provenance=(("fixture", "failed-with-result"),),
        repository_revision=spec.repository_revision,
        summary="Impossible failed execution fixture.",
    )

    with pytest.raises(
        ValueError,
        match="cannot carry a result artifact",
    ):
        catalog.terminalize_running_job_attempt_with_evidence(
            attempt.attempt_id,
            job_id=job.job_id,
            state=RunAttemptState.FAILED,
            terminal_at=JUN,
            result_artifact=result_artifact,
            evidence=failed_evidence,
            failure_classification="fixture_failure",
            failure_message="should not persist",
        )

    assert (
        catalog.load_run_attempt(attempt.attempt_id).state
        is RunAttemptState.RUNNING
    )
    assert (
        catalog.load_research_job(job.job_id).state
        is ResearchJobState.RUNNING
    )
    assert (
        catalog.load_trial(trial.trial_id).disposition
        is TrialDisposition.PENDING
    )


def test_fresh_success_requires_result_artifact_evidence_reference(
    tmp_path,
):
    catalog, trial, job, spec = _environment(
        tmp_path,
        attempt_id_factory=(
            lambda: "attempt-success-missing-result-reference"
        ),
    )

    _, _, attempt = (
        catalog.bind_trial_spec_create_attempt_for_running_job(
            job_id=job.job_id,
            experiment_spec_id=spec.experiment_spec_id,
            attempt_created_at=MAY,
        )
    )

    evidence, result_artifact = _fresh_success_material(
        tmp_path,
        spec,
    )

    evidence_without_result_reference = ResearchEvidence(
        evidence_id="evidence-m94d-missing-result-reference",
        created_at=evidence.created_at,
        status=ResearchEvidenceStatus.ACCEPTED,
        dataset_context=evidence.dataset_context,
        requested_range=evidence.requested_range,
        dataset_fingerprint=evidence.dataset_fingerprint,
        configuration_fingerprint=(
            evidence.configuration_fingerprint
        ),
        result_fingerprint=evidence.result_fingerprint,
        provenance=evidence.provenance,
        repository_revision=evidence.repository_revision,
        summary="Accepted fixture missing result reference.",
        artifact_references=(),
    )

    with pytest.raises(
        ValueError,
        match="must reference the exact Backtest result artifact",
    ):
        catalog.terminalize_running_job_attempt_with_evidence(
            attempt.attempt_id,
            job_id=job.job_id,
            state=RunAttemptState.SUCCEEDED,
            terminal_at=JUN,
            result_artifact=result_artifact,
            evidence=evidence_without_result_reference,
        )

    assert (
        catalog.load_run_attempt(attempt.attempt_id).state
        is RunAttemptState.RUNNING
    )
    assert (
        catalog.load_research_job(job.job_id).state
        is ResearchJobState.RUNNING
    )
    assert (
        catalog.load_trial(trial.trial_id).disposition
        is TrialDisposition.PENDING
    )



def test_pre_attempt_failure_terminalizes_job_trial_and_event_atomically(
    tmp_path,
):
    catalog, trial, job, _ = _environment(
        tmp_path
    )

    before_attempts = _attempt_count(
        catalog
    )

    updated_trial, updated_job, event = (
        catalog.fail_running_job_without_attempt(
            job_id=job.job_id,
            terminal_at=JUN,
            failure_classification=(
                "exact_specification_preparation_failed"
            ),
            failure_message=(
                "fixture preparation failed"
            ),
        )
    )

    assert _attempt_count(catalog) == before_attempts

    assert (
        updated_job.state
        is ResearchJobState.FAILED
    )
    assert updated_job.attempt_id is None
    assert updated_job.completion_kind is None
    assert (
        updated_job.failure_classification
        == "exact_specification_preparation_failed"
    )
    assert (
        updated_job.failure_message
        == "fixture preparation failed"
    )

    assert (
        updated_trial.disposition
        is TrialDisposition.FAILED
    )
    assert (
        updated_trial.failure_classification
        == "exact_specification_preparation_failed"
    )
    assert (
        updated_trial.failure_message
        == "fixture preparation failed"
    )

    assert event.sequence_number == 2
    assert (
        event.previous_disposition
        is TrialDisposition.PENDING
    )
    assert (
        event.new_disposition
        is TrialDisposition.FAILED
    )
    assert event.causing_job_id == job.job_id
    assert (
        event.reason_classification
        == "exact_specification_preparation_failed"
    )
    assert (
        event.reason_message
        == "fixture preparation failed"
    )

    events = (
        catalog.load_trial_disposition_events(
            trial.trial_id
        )
    )
    assert len(events) == 2


def test_pre_attempt_failure_refuses_job_after_run_attempt_link(
    tmp_path,
):
    catalog, trial, job, spec = _environment(
        tmp_path,
        attempt_id_factory=(
            lambda: "attempt-pre-failure-guard"
        ),
    )

    _, linked_job, attempt = (
        catalog.bind_trial_spec_create_attempt_for_running_job(
            job_id=job.job_id,
            experiment_spec_id=(
                spec.experiment_spec_id
            ),
            attempt_created_at=MAY,
        )
    )

    assert linked_job.attempt_id == attempt.attempt_id

    before_attempts = _attempt_count(
        catalog
    )

    with pytest.raises(
        ValueError,
        match="no attempt or reuse lineage",
    ):
        catalog.fail_running_job_without_attempt(
            job_id=job.job_id,
            terminal_at=JUN,
            failure_classification=(
                "should_not_apply"
            ),
            failure_message=(
                "attempt already exists"
            ),
        )

    assert _attempt_count(catalog) == before_attempts

    persisted_job = catalog.load_research_job(
        job.job_id
    )
    persisted_trial = catalog.load_trial(
        trial.trial_id
    )
    persisted_attempt = catalog.load_run_attempt(
        attempt.attempt_id
    )

    assert persisted_job is not None
    assert persisted_trial is not None
    assert persisted_attempt is not None

    assert (
        persisted_job.state
        is ResearchJobState.RUNNING
    )
    assert (
        persisted_job.attempt_id
        == attempt.attempt_id
    )
    assert (
        persisted_trial.disposition
        is TrialDisposition.PENDING
    )
    assert (
        persisted_attempt.state
        is RunAttemptState.RUNNING
    )

    assert len(
        catalog.load_trial_disposition_events(
            trial.trial_id
        )
    ) == 1



def test_explicit_retry_preserves_trial_spec_and_prior_failure_history(
    tmp_path,
):
    catalog, trial, job, spec = _environment(
        tmp_path,
        attempt_id_factory=(
            lambda: "attempt-retry-source"
        ),
    )

    _, _, attempt = (
        catalog.bind_trial_spec_create_attempt_for_running_job(
            job_id=job.job_id,
            experiment_spec_id=(
                spec.experiment_spec_id
            ),
            attempt_created_at=MAY,
        )
    )

    evidence = ResearchEvidence(
        evidence_id="evidence-retry-source",
        created_at=JUN,
        status=ResearchEvidenceStatus.FAILED,
        dataset_context=DatasetContext(
            symbol="NSE:A",
            timeframe="1d",
            timezone="UTC",
        ),
        requested_range=TimeRange(
            JAN,
            FEB,
        ),
        dataset_fingerprint=(
            spec.dataset_fingerprint
        ),
        configuration_fingerprint=(
            spec.configuration_fingerprint
        ),
        provenance=(
            ("fixture", "retry-source"),
        ),
        repository_revision=(
            spec.repository_revision
        ),
        summary="Retry source failure fixture.",
    )

    catalog.terminalize_running_job_attempt_with_evidence(
        attempt.attempt_id,
        job_id=job.job_id,
        state=RunAttemptState.FAILED,
        terminal_at=JUN,
        evidence=evidence,
        failure_classification=(
            "fixture_retryable_failure"
        ),
        failure_message=(
            "retry source failed"
        ),
    )

    before_attempts = _attempt_count(
        catalog
    )

    before_jobs = (
        catalog.list_research_jobs_for_trial(
            trial.trial_id
        )
    )

    assert len(before_jobs) == 1

    updated_trial, retry_job, retry_event = (
        catalog.retry_trial(
            trial.trial_id,
            retry_requested_at=JUN,
        )
    )

    assert (
        updated_trial.trial_id
        == trial.trial_id
    )
    assert (
        updated_trial.disposition
        is TrialDisposition.PENDING
    )
    assert (
        updated_trial.experiment_spec_id
        == spec.experiment_spec_id
    )
    assert updated_trial.reused_attempt_id is None
    assert updated_trial.failure_classification is None
    assert updated_trial.failure_message is None

    assert (
        retry_job.state
        is ResearchJobState.QUEUED
    )
    assert retry_job.trial_id == trial.trial_id
    assert retry_job.attempt_id is None
    assert retry_job.completion_kind is None
    assert retry_job.claimed_at is None
    assert retry_job.terminal_at is None

    assert (
        retry_event.previous_disposition
        is TrialDisposition.FAILED
    )
    assert (
        retry_event.new_disposition
        is TrialDisposition.PENDING
    )
    assert (
        retry_event.causing_job_id
        == retry_job.job_id
    )
    assert (
        retry_event.reason_classification
        == "explicit_retry"
    )

    assert _attempt_count(catalog) == before_attempts

    persisted_source_job = (
        catalog.load_research_job(
            job.job_id
        )
    )
    persisted_source_attempt = (
        catalog.load_run_attempt(
            attempt.attempt_id
        )
    )

    assert persisted_source_job is not None
    assert persisted_source_attempt is not None

    assert (
        persisted_source_job.state
        is ResearchJobState.FAILED
    )
    assert (
        persisted_source_job.attempt_id
        == attempt.attempt_id
    )
    assert (
        persisted_source_job.failure_classification
        == "fixture_retryable_failure"
    )

    assert (
        persisted_source_attempt.state
        is RunAttemptState.FAILED
    )
    assert (
        persisted_source_attempt.evidence_id
        == evidence.evidence_id
    )

    jobs = (
        catalog.list_research_jobs_for_trial(
            trial.trial_id
        )
    )

    assert len(jobs) == 2
    assert {
        value.job_id
        for value in jobs
    } == {
        job.job_id,
        retry_job.job_id,
    }

    events = (
        catalog.load_trial_disposition_events(
            trial.trial_id
        )
    )

    assert len(events) == 3
    assert [
        (
            value.previous_disposition,
            value.new_disposition,
        )
        for value in events
    ] == [
        (
            None,
            TrialDisposition.PENDING,
        ),
        (
            TrialDisposition.PENDING,
            TrialDisposition.FAILED,
        ),
        (
            TrialDisposition.FAILED,
            TrialDisposition.PENDING,
        ),
    ]


def test_duplicate_retry_request_cannot_create_second_active_job(
    tmp_path,
):
    catalog, trial, job, _ = _environment(
        tmp_path
    )

    catalog.fail_running_job_without_attempt(
        job_id=job.job_id,
        terminal_at=JUN,
        failure_classification=(
            "fixture_retryable_pre_attempt_failure"
        ),
        failure_message=(
            "retryable preparation failure"
        ),
    )

    _, retry_job, _ = catalog.retry_trial(
        trial.trial_id,
        retry_requested_at=JUN,
    )

    jobs_before = (
        catalog.list_research_jobs_for_trial(
            trial.trial_id
        )
    )

    with pytest.raises(
        ValueError,
        match="not eligible for ordinary retry",
    ):
        catalog.retry_trial(
            trial.trial_id,
            retry_requested_at=JUN,
        )

    jobs_after = (
        catalog.list_research_jobs_for_trial(
            trial.trial_id
        )
    )

    assert jobs_after == jobs_before
    assert len(jobs_after) == 2

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.PENDING
    )

    persisted_retry_job = (
        catalog.load_research_job(
            retry_job.job_id
        )
    )

    assert persisted_retry_job is not None
    assert (
        persisted_retry_job.state
        is ResearchJobState.QUEUED
    )
    assert persisted_retry_job.attempt_id is None

    assert len(
        catalog.load_trial_disposition_events(
            trial.trial_id
        )
    ) == 3


def test_m94g2_public_retry_job_insert_cannot_bypass_retry(
    tmp_path,
):
    catalog, trial, job, _ = _environment(
        tmp_path
    )

    catalog.fail_running_job_without_attempt(
        job_id=job.job_id,
        terminal_at=JUN,
        failure_classification=(
            "fixture_retryable_pre_attempt_failure"
        ),
        failure_message=(
            "retryable preparation failure"
        ),
    )

    jobs_before = (
        catalog.list_research_jobs_for_trial(
            trial.trial_id
        )
    )

    bypass = ResearchJob(
        job_id="out-of-band-retry",
        trial_id=trial.trial_id,
        state=ResearchJobState.QUEUED,
        created_at=JUN,
    )

    with pytest.raises(
        ValueError,
        match="authoritative Start or Retry",
    ):
        catalog.save_queued_research_job(
            bypass
        )

    assert (
        catalog.list_research_jobs_for_trial(
            trial.trial_id
        )
        == jobs_before
    )

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.FAILED
    )

    updated_trial, retry_job, _ = (
        catalog.retry_trial(
            trial.trial_id,
            retry_requested_at=JUN,
        )
    )

    assert (
        updated_trial.disposition
        is TrialDisposition.PENDING
    )
    assert (
        retry_job.state
        is ResearchJobState.QUEUED
    )
    assert retry_job.job_id != bypass.job_id


def test_m94g2_trial_denominator_stays_fixed_across_failure_retry_and_reuse(
    tmp_path,
):
    catalog, trial, initial_job, spec = _environment(
        tmp_path,
        attempt_id_factory=(
            lambda: "attempt-denominator-source"
        ),
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
    )

    queue = ResearchJobQueueService(
        catalog_store=catalog,
        app_config=AppConfig(
            research_max_workers=1
        ),
    )

    def snapshot():
        return queue.snapshot(
            trial.study_revision_id
        )

    initial = snapshot()

    assert initial.total_registered_trials == 1
    assert initial.total_jobs == 1
    assert initial.running_jobs == 1

    catalog.fail_running_job_without_attempt(
        job_id=initial_job.job_id,
        terminal_at=JUN,
        failure_classification=(
            "fixture_denominator_failure"
        ),
        failure_message=(
            "denominator failure fixture"
        ),
    )

    failed = snapshot()

    assert failed.total_registered_trials == 1
    assert failed.total_jobs == 1
    assert failed.failed_trials == 1
    assert failed.failed_jobs == 1

    updated_trial, retry_job, _ = (
        catalog.retry_trial(
            trial.trial_id,
            retry_requested_at=JUN,
        )
    )

    assert (
        updated_trial.disposition
        is TrialDisposition.PENDING
    )

    retried = snapshot()

    assert retried.total_registered_trials == 1
    assert retried.total_jobs == 2
    assert retried.pending_trials == 1
    assert retried.queued_jobs == 1
    assert retried.failed_jobs == 1

    claimed_retry = (
        catalog.claim_next_research_job(
            trial.study_revision_id,
            "worker-denominator-reuse",
            JUN,
            max_running_jobs=1,
        )
    )

    assert claimed_retry is not None
    assert claimed_retry.job_id == retry_job.job_id

    source, reuse_evidence, _ = _create_reuse_source(
        tmp_path,
        catalog,
        spec,
    )

    dataset_artifact_id = (
        _dataset_reference_artifact_id(
            catalog,
            reuse_evidence,
        )
    )

    reused_trial, reused_job, _ = (
        catalog._complete_running_job_with_exact_reuse(
            job_id=claimed_retry.job_id,
            experiment_spec_id=(
                spec.experiment_spec_id
            ),
            reused_attempt_id=(
                source.attempt_id
            ),
            terminal_at=JUN,
            requested_dataset_reference_artifact_id=(
                dataset_artifact_id
            ),
            source_dataset_reference_artifact_id=(
                dataset_artifact_id
            ),
        )
    )

    assert (
        reused_trial.disposition
        is TrialDisposition.REUSED
    )
    assert (
        reused_job.completion_kind
        is ResearchJobCompletionKind.REUSED
    )

    final = snapshot()

    assert final.total_registered_trials == 1
    assert final.total_jobs == 2
    assert final.reused_trials == 1
    assert final.succeeded_jobs == 1
    assert final.failed_jobs == 1

    jobs = (
        catalog.list_research_jobs_for_trial(
            trial.trial_id
        )
    )

    assert len(jobs) == 2
    assert {
        job.job_id
        for job in jobs
    } == {
        initial_job.job_id,
        retry_job.job_id,
    }

def test_m94i2_raw_exact_reuse_terminalizer_is_not_public_catalog_authority(
    tmp_path,
):
    catalog = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3"
    )

    assert not hasattr(
        catalog,
        "complete_running_job_with_exact_reuse",
    )
    assert callable(
        catalog._complete_running_job_with_exact_reuse
    )



@pytest.mark.parametrize(
    "terminal_state",
    (
        RunAttemptState.SUCCEEDED,
        RunAttemptState.FAILED,
        RunAttemptState.INTERRUPTED,
    ),
)
def test_m94j_standalone_terminalizer_rejects_job_owned_attempt(
    tmp_path,
    terminal_state,
):
    catalog, trial, job, spec = _environment(
        tmp_path
    )

    (
        _,
        _,
        attempt,
    ) = (
        catalog
        .bind_trial_spec_create_attempt_for_running_job(
            job_id=job.job_id,
            experiment_spec_id=spec.experiment_spec_id,
            attempt_created_at=JUN,
        )
    )

    with pytest.raises(
        ValueError,
        match="ResearchJob-owned RunAttempt",
    ):
        catalog.terminalize_attempt(
            attempt.attempt_id,
            state=terminal_state,
            terminal_at=JUN,
            failure_classification=(
                "m94j_forbidden_standalone"
                if terminal_state
                is not RunAttemptState.SUCCEEDED
                else None
            ),
        )

    persisted_attempt = catalog.load_run_attempt(
        attempt.attempt_id
    )
    persisted_job = catalog.load_research_job(
        job.job_id
    )
    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_attempt is not None
    assert persisted_job is not None
    assert persisted_trial is not None

    assert (
        persisted_attempt.state
        is RunAttemptState.RUNNING
    )
    assert (
        persisted_job.state
        is ResearchJobState.RUNNING
    )
    assert (
        persisted_trial.disposition
        is TrialDisposition.PENDING
    )


def test_m94j_atomic_evidence_terminalizer_rejects_job_owned_attempt(
    tmp_path,
):
    catalog, trial, job, spec = _environment(
        tmp_path
    )

    (
        _,
        _,
        attempt,
    ) = (
        catalog
        .bind_trial_spec_create_attempt_for_running_job(
            job_id=job.job_id,
            experiment_spec_id=spec.experiment_spec_id,
            attempt_created_at=JUN,
        )
    )

    result_artifact = ResearchArtifact(
        artifact_id=_fingerprint(
            "m94j-owned-result",
            schema=BACKTEST_RESULT_SCHEMA,
        ),
        artifact_kind=(
            ResearchArtifactKind.BACKTEST_RESULT
        ),
        schema_id=BACKTEST_RESULT_SCHEMA,
        relative_path=(
            "m94j/"
            + _fingerprint(
                "m94j-owned-result",
                schema=BACKTEST_RESULT_SCHEMA,
            ).split(":", 1)[1]
            + ".json"
        ),
        byte_count=2,
        created_at=JUN,
    )

    evidence = ResearchEvidence(
        evidence_id="evidence-m94j-owned-attempt",
        created_at=JUN,
        status=ResearchEvidenceStatus.ACCEPTED,
        dataset_context=DatasetContext(
            symbol="NSE:A",
            timeframe="1d",
            timezone="UTC",
        ),
        requested_range=TimeRange(JAN, FEB),
        dataset_fingerprint=spec.dataset_fingerprint,
        configuration_fingerprint=(
            spec.configuration_fingerprint
        ),
        result_fingerprint=(
            result_artifact.artifact_id
        ),
        provenance=(
            ("fixture", "m94j-owned-attempt"),
        ),
        repository_revision=(
            spec.repository_revision
        ),
        summary=(
            "M9.4j ownership exclusion fixture."
        ),
        artifact_references=(
            research_artifact_reference(
                spec.manifest_artifact_id
            ),
            research_artifact_reference(
                result_artifact.artifact_id
            ),
        ),
    )

    with pytest.raises(
        ValueError,
        match="ResearchJob-owned RunAttempt",
    ):
        catalog.terminalize_attempt_with_evidence(
            attempt.attempt_id,
            state=RunAttemptState.SUCCEEDED,
            terminal_at=JUN,
            runtime_session_id="runtime-m94j-owned",
            result_artifact=result_artifact,
            evidence=evidence,
        )

    persisted_attempt = catalog.load_run_attempt(
        attempt.attempt_id
    )
    persisted_job = catalog.load_research_job(
        job.job_id
    )
    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_attempt is not None
    assert persisted_job is not None
    assert persisted_trial is not None

    assert (
        persisted_attempt.state
        is RunAttemptState.RUNNING
    )
    assert (
        persisted_job.state
        is ResearchJobState.RUNNING
    )
    assert (
        persisted_trial.disposition
        is TrialDisposition.PENDING
    )

    assert (
        catalog.load_artifact(
            result_artifact.artifact_id
        )
        is None
    )



def test_m94j_trial_detail_snapshot_uses_one_read_transaction(
    tmp_path,
):
    catalog, trial, job, spec = _environment(
        tmp_path
    )

    (
        _,
        _,
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

    original_connect = catalog._connect
    connection_count = []
    traced_sql = []

    def traced_connect():
        connection_count.append(1)
        connection = original_connect()
        connection.set_trace_callback(
            traced_sql.append
        )
        return connection

    catalog._connect = traced_connect

    snapshot = (
        catalog.load_research_trial_detail_snapshot(
            trial.trial_id
        )
    )

    assert snapshot is not None
    assert connection_count == [1]

    normalized_sql = [
        statement.strip().upper()
        for statement in traced_sql
    ]

    assert "BEGIN" in normalized_sql
    assert "COMMIT" in normalized_sql

    assert (
        snapshot.trial.trial_id
        == trial.trial_id
    )
    assert snapshot.jobs
    assert (
        snapshot.jobs[0].job_id
        == job.job_id
    )
    assert (
        snapshot.jobs[0].attempt_id
        == attempt.attempt_id
    )

    assert snapshot.owned_attempts == (
        (
            attempt.attempt_id,
            attempt,
        ),
    )

    assert snapshot.reused_attempts == ()

    assert (
        snapshot.disposition_events[-1]
        .new_disposition
        is TrialDisposition.PENDING
    )
