from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
import sqlite3

import pytest

import core.research.sqlite_research_catalog_store as catalog_module
from core.config.app_config import AppConfig
from core.market_data.historical_coverage import TimeRange
from core.research.models.registered_study import (
    EvidenceReusePolicy,
    INITIAL_RESEARCH_JOB_SCHEMA_ID,
    RESEARCH_MAX_WORKERS_SAFETY_CEILING,
    ResearchJob,
    ResearchJobState,
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


def _initial_job_id(trial_id: str) -> str:
    return canonical_fingerprint(
        {
            "trial_id": trial_id,
            "purpose": "INITIAL",
        },
        schema=INITIAL_RESEARCH_JOB_SCHEMA_ID,
    )


def _environment(
    tmp_path,
    *,
    max_workers: int = 4,
):
    catalog = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3"
    )

    artifacts = ContentAddressedResearchArtifactStore(
        tmp_path / "artifacts"
    )

    catalog.save_study(
        Study(
            study_id="study-m94c",
            created_at=JAN,
            display_title="M9.4c queue research",
        )
    )

    registration = RegisteredStudyRegistrationService(
        catalog_store=catalog,
        artifact_store=artifacts,
    )

    queue = ResearchJobQueueService(
        catalog_store=catalog,
        app_config=AppConfig(
            research_max_workers=max_workers
        ),
    )

    definition = UniverseDefinition(
        name="m94c-universe",
        selection_spec="fixture",
    )

    snapshot = UniverseSnapshot(
        definition=definition,
        members=(
            "NSE:A",
            "NSE:B",
            "NSE:C",
        ),
        quality=UniverseQuality.PIT_VERIFIED,
        as_of=JAN,
        provenance_refs=("m94c-source",),
        effective_from=JAN,
        effective_to=FEB,
    )

    return (
        catalog,
        registration,
        queue,
        definition,
        snapshot,
    )


def _register(
    registration,
    definition,
    snapshot,
    *,
    intent: str,
    registered_at: datetime,
    variants=(
        {"variant": 1},
        {"variant": 2},
    ),
):
    return registration.register_study_revision(
        study_id="study-m94c",
        research_intent=intent,
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
        parameter_variants=variants,
        universe_definition=definition,
        universe_snapshots=(snapshot,),
        require_point_in_time=True,
        data_treatment_basis={
            "adjustment": "raw",
        },
        repository_revision="repo-m94c",
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
        registered_at=registered_at,
    )


def _jobs_for_population(
    catalog,
    population,
):
    jobs = []

    for trial in population.trials:
        jobs.extend(
            catalog.list_research_jobs_for_trial(
                trial.trial_id
            )
        )

    return tuple(
        sorted(
            jobs,
            key=lambda job: (
                job.created_at,
                job.job_id,
            ),
        )
    )


def test_backend_worker_configuration_is_bounded():
    assert AppConfig().research_max_workers == 4

    assert (
        RESEARCH_MAX_WORKERS_SAFETY_CEILING
        == 16
    )


def test_queue_service_rejects_invalid_worker_bound(
    tmp_path,
):
    catalog = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3"
    )

    for value in (0, 17):
        with pytest.raises(
            ValueError,
            match="between 1 and 16",
        ):
            ResearchJobQueueService(
                catalog_store=catalog,
                app_config=AppConfig(
                    research_max_workers=value
                ),
            )


def test_start_atomically_creates_initial_queue_once(
    tmp_path,
):
    (
        catalog,
        registration,
        queue,
        definition,
        snapshot,
    ) = _environment(tmp_path)

    population = _register(
        registration,
        definition,
        snapshot,
        intent="atomic Start",
        registered_at=MAR,
    )

    assert len(population.trials) == 6

    started = queue.start_revision(
        population.revision.study_revision_id,
        started_at=APR,
    )

    assert started.initial_batch_started_at == APR
    assert started.total_registered_trials == 6
    assert started.pending_trials == 6
    assert started.queued_jobs == 6
    assert started.running_jobs == 0
    assert started.total_jobs == 6

    jobs = _jobs_for_population(
        catalog,
        population,
    )

    assert len(jobs) == 6

    assert {
        job.job_id
        for job in jobs
    } == {
        _initial_job_id(
            trial.trial_id
        )
        for trial in population.trials
    }

    assert all(
        job.state is ResearchJobState.QUEUED
        and job.created_at == APR
        and job.attempt_id is None
        for job in jobs
    )

    replay = queue.start_revision(
        population.revision.study_revision_id,
        started_at=MAY,
    )

    assert replay.initial_batch_started_at == APR
    assert replay.total_jobs == 6

    assert len(
        _jobs_for_population(
            catalog,
            population,
        )
    ) == 6


def test_start_failure_rolls_back_entire_queue(
    tmp_path,
    monkeypatch,
):
    (
        catalog,
        registration,
        queue,
        definition,
        snapshot,
    ) = _environment(tmp_path)

    population = _register(
        registration,
        definition,
        snapshot,
        intent="Start rollback",
        registered_at=MAR,
        variants=(
            {"variant": 1},
        ),
    )

    monkeypatch.setattr(
        catalog_module,
        "_initial_research_job_id",
        lambda _trial_id: "job-collision",
    )

    with pytest.raises(
        ValueError,
        match="persisted atomically",
    ):
        queue.start_revision(
            population.revision.study_revision_id,
            started_at=APR,
        )

    revision = catalog.load_study_revision(
        population.revision.study_revision_id
    )

    assert revision is not None
    assert revision.initial_batch_started_at is None

    assert _jobs_for_population(
        catalog,
        population,
    ) == ()


def test_start_fails_closed_on_prestart_job(
    tmp_path,
):
    (
        catalog,
        registration,
        queue,
        definition,
        snapshot,
    ) = _environment(tmp_path)

    population = _register(
        registration,
        definition,
        snapshot,
        intent="prestart corruption",
        registered_at=MAR,
        variants=(
            {"variant": 1},
        ),
    )

    catalog.save_queued_research_job(
        ResearchJob(
            job_id="out-of-band",
            trial_id=population.trials[0].trial_id,
            state=ResearchJobState.QUEUED,
            created_at=APR,
        )
    )

    with pytest.raises(
        ValueError,
        match="unstarted StudyRevision already has",
    ):
        queue.start_revision(
            population.revision.study_revision_id,
            started_at=APR,
        )


def test_started_revision_missing_initial_job_fails_closed(
    tmp_path,
):
    (
        catalog,
        registration,
        queue,
        definition,
        snapshot,
    ) = _environment(tmp_path)

    population = _register(
        registration,
        definition,
        snapshot,
        intent="missing lineage",
        registered_at=MAR,
        variants=(
            {"variant": 1},
        ),
    )

    queue.start_revision(
        population.revision.study_revision_id,
        started_at=APR,
    )

    missing_job_id = _initial_job_id(
        population.trials[0].trial_id
    )

    with closing(
        sqlite3.connect(
            catalog.database_path
        )
    ) as connection:
        connection.execute(
            """
            DELETE FROM research_jobs
            WHERE job_id = ?
            """,
            (missing_job_id,),
        )
        connection.commit()

    with pytest.raises(
        ValueError,
        match="missing deterministic initial-job lineage",
    ):
        queue.start_revision(
            population.revision.study_revision_id,
            started_at=MAY,
        )


def test_claim_is_fifo_bounded_and_creates_no_attempt(
    tmp_path,
):
    (
        catalog,
        registration,
        queue,
        definition,
        snapshot,
    ) = _environment(
        tmp_path,
        max_workers=2,
    )

    population = _register(
        registration,
        definition,
        snapshot,
        intent="FIFO claim",
        registered_at=MAR,
    )

    queue.start_revision(
        population.revision.study_revision_id,
        started_at=APR,
    )

    expected = [
        job.job_id
        for job in _jobs_for_population(
            catalog,
            population,
        )
    ]

    first = queue.claim_next(
        population.revision.study_revision_id,
        worker_id="worker-1",
        claimed_at=MAY,
    )

    second = queue.claim_next(
        population.revision.study_revision_id,
        worker_id="worker-2",
        claimed_at=MAY,
    )

    third = queue.claim_next(
        population.revision.study_revision_id,
        worker_id="worker-3",
        claimed_at=MAY,
    )

    assert first is not None
    assert second is not None
    assert third is None

    assert [
        first.job_id,
        second.job_id,
    ] == expected[:2]

    assert first.state is ResearchJobState.RUNNING
    assert first.worker_id == "worker-1"
    assert first.attempt_id is None
    assert second.attempt_id is None

    with closing(
        catalog._connect()
    ) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM run_attempts"
        ).fetchone()[0] == 0


def test_start_replay_after_claim_does_not_duplicate_jobs(
    tmp_path,
):
    (
        catalog,
        registration,
        queue,
        definition,
        snapshot,
    ) = _environment(tmp_path)

    population = _register(
        registration,
        definition,
        snapshot,
        intent="replay after claim",
        registered_at=MAR,
    )

    queue.start_revision(
        population.revision.study_revision_id,
        started_at=APR,
    )

    claimed = queue.claim_next(
        population.revision.study_revision_id,
        worker_id="worker-1",
        claimed_at=MAY,
    )

    assert claimed is not None

    before = {
        job.job_id
        for job in _jobs_for_population(
            catalog,
            population,
        )
    }

    replay = queue.start_revision(
        population.revision.study_revision_id,
        started_at=JUN,
    )

    after = {
        job.job_id
        for job in _jobs_for_population(
            catalog,
            population,
        )
    }

    assert replay.initial_batch_started_at == APR
    assert before == after
    assert replay.running_jobs == 1
    assert replay.queued_jobs == 5


def test_cross_revision_claims_respect_global_worker_bound(
    tmp_path,
):
    (
        catalog,
        registration,
        queue,
        definition,
        snapshot,
    ) = _environment(
        tmp_path,
        max_workers=4,
    )

    first = _register(
        registration,
        definition,
        snapshot,
        intent="first active revision",
        registered_at=MAR,
    )

    second = _register(
        registration,
        definition,
        snapshot,
        intent="second active revision",
        registered_at=APR,
    )

    queue.start_revision(
        first.revision.study_revision_id,
        started_at=MAY,
    )

    queue.start_revision(
        second.revision.study_revision_id,
        started_at=MAY,
    )

    expected_fifo = {
        first.revision.study_revision_id: [
            job.job_id
            for job in _jobs_for_population(
                catalog,
                first,
            )
        ],
        second.revision.study_revision_id: [
            job.job_id
            for job in _jobs_for_population(
                catalog,
                second,
            )
        ],
    }

    requests = [
        first.revision.study_revision_id,
        second.revision.study_revision_id,
    ] * 8

    with ThreadPoolExecutor(
        max_workers=16
    ) as executor:
        futures = [
            executor.submit(
                queue.claim_next,
                revision_id,
                worker_id=f"worker-{index:02d}",
                claimed_at=JUN,
            )
            for index, revision_id
            in enumerate(requests)
        ]

        results = [
            future.result()
            for future in futures
        ]

    claimed = [
        job
        for job in results
        if job is not None
    ]

    assert len(claimed) == 4
    assert len(
        {
            job.job_id
            for job in claimed
        }
    ) == 4

    with closing(
        catalog._connect()
    ) as connection:
        global_running = connection.execute(
            """
            SELECT COUNT(*)
            FROM research_jobs
            WHERE state = 'RUNNING'
            """
        ).fetchone()[0]

    assert global_running == 4

    for population in (
        first,
        second,
    ):
        revision_id = (
            population.revision.study_revision_id
        )

        running = [
            job.job_id
            for job in _jobs_for_population(
                catalog,
                population,
            )
            if job.state
            is ResearchJobState.RUNNING
        ]

        assert (
            running
            == expected_fifo[
                revision_id
            ][:len(running)]
        )


def test_queue_snapshot_separates_trial_and_job_counts(
    tmp_path,
):
    (
        _,
        registration,
        queue,
        definition,
        snapshot,
    ) = _environment(
        tmp_path,
        max_workers=2,
    )

    population = _register(
        registration,
        definition,
        snapshot,
        intent="truthful snapshot",
        registered_at=MAR,
    )

    before = queue.snapshot(
        population.revision.study_revision_id
    )

    assert before.total_registered_trials == 6
    assert before.pending_trials == 6
    assert before.total_jobs == 0

    queue.start_revision(
        population.revision.study_revision_id,
        started_at=APR,
    )

    queue.claim_next(
        population.revision.study_revision_id,
        worker_id="worker-1",
        claimed_at=MAY,
    )

    queue.claim_next(
        population.revision.study_revision_id,
        worker_id="worker-2",
        claimed_at=MAY,
    )

    after = queue.snapshot(
        population.revision.study_revision_id
    )

    assert after.total_registered_trials == 6
    assert after.pending_trials == 6
    assert after.queued_jobs == 4
    assert after.running_jobs == 2
    assert after.total_jobs == 6


def test_existing_schema_v2_restores_queue_indexes_without_version_bump(
    tmp_path,
):
    path = tmp_path / "research.sqlite3"

    SQLiteResearchCatalogStore(path)

    names = (
        "ix_research_jobs_state_created_job",
        "ix_research_jobs_trial_created_job",
    )

    with closing(
        sqlite3.connect(path)
    ) as connection:
        assert (
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
            == 2
        )

        for name in names:
            connection.execute(
                f"DROP INDEX {name}"
            )

        connection.commit()

    SQLiteResearchCatalogStore(path)

    with closing(
        sqlite3.connect(path)
    ) as connection:
        assert (
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
            == 2
        )

        state_columns = tuple(
            row[2]
            for row in connection.execute(
                """
                PRAGMA index_info(
                    ix_research_jobs_state_created_job
                )
                """
            ).fetchall()
        )

        trial_columns = tuple(
            row[2]
            for row in connection.execute(
                """
                PRAGMA index_info(
                    ix_research_jobs_trial_created_job
                )
                """
            ).fetchall()
        )

    assert state_columns == (
        "state",
        "created_at",
        "job_id",
    )

    assert trial_columns == (
        "trial_id",
        "created_at",
        "job_id",
    )
