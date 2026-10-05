from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
import sqlite3
from threading import Event, Lock, get_ident

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


def _claim_direct(
    catalog,
    queue,
    study_revision_id,
    *,
    worker_id,
    claimed_at,
):
    """Exercise the durable store primitive without scheduler policy."""

    return catalog.claim_next_research_job(
        study_revision_id,
        worker_id,
        claimed_at,
        max_running_jobs=(
            queue.research_max_workers
        ),
    )


def _terminalize_running_job(
    catalog,
    job,
    *,
    terminal_at=JUN,
):
    """
    Test-only terminalization fixture.

    M9.4d supplies the production coordinated terminalizer. These queue
    tests only need a durable terminal state to prove worker-slot
    lifetime and scheduler behavior.
    """

    with closing(
        sqlite3.connect(
            catalog.database_path
        )
    ) as connection:
        cursor = connection.execute(
            """
            UPDATE research_jobs
            SET
                state = ?,
                terminal_at = ?,
                failure_classification = ?,
                failure_message = ?
            WHERE
                job_id = ?
                AND state = ?
            """,
            (
                ResearchJobState.FAILED.value,
                terminal_at.isoformat(
                    timespec="microseconds"
                ),
                "worker_pool_test_terminal",
                "test-only durable terminalization",
                job.job_id,
                ResearchJobState.RUNNING.value,
            ),
        )

        assert cursor.rowcount == 1
        connection.commit()

    persisted = catalog.load_research_job(
        job.job_id
    )

    assert persisted is not None
    assert (
        persisted.state
        is ResearchJobState.FAILED
    )

    return persisted


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

    # Test-only corruption injection through the explicitly private
    # storage seam. Supported public insertion is tested separately.
    catalog._save_queued_research_job(
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

    first = _claim_direct(catalog, queue,
        population.revision.study_revision_id,
        worker_id="worker-1",
        claimed_at=MAY,
    )

    second = _claim_direct(catalog, queue,
        population.revision.study_revision_id,
        worker_id="worker-2",
        claimed_at=MAY,
    )

    third = _claim_direct(catalog, queue,
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


def _m94h3_drain_initial_queue(
    catalog,
    queue,
    population,
):
    revision_id = (
        population.revision.study_revision_id
    )

    drained = []

    while True:
        job = _claim_direct(
            catalog,
            queue,
            revision_id,
            worker_id=(
                f"m94h3-drain-{len(drained)}"
            ),
            claimed_at=MAY,
        )

        if job is None:
            break

        drained.append(
            job
        )

        _terminalize_running_job(
            catalog,
            job,
        )

    return tuple(
        drained
    )


def test_m94h3_fifo_uses_exact_chronology_across_offsets_and_microseconds(
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
        max_workers=1,
    )

    population = _register(
        registration,
        definition,
        snapshot,
        intent="exact semantic FIFO chronology",
        registered_at=MAR,
        variants=(
            {"variant": 1},
        ),
    )

    revision_id = (
        population.revision.study_revision_id
    )

    queue.start_revision(
        revision_id,
        started_at=APR,
    )

    drained = _m94h3_drain_initial_queue(
        catalog,
        queue,
        population,
    )

    assert len(drained) == 3

    trial_id = (
        population.trials[0].trial_id
    )

    plus_zero = timezone.utc
    minus_five = timezone(
        -timedelta(hours=5)
    )

    # Absolute chronology differs by exactly one microsecond:
    #
    # earlier == 2020-04-02 00:00:00.000001 UTC
    # later   == 2020-04-02 00:00:00.000002 UTC
    #
    # But lexical ISO text puts `later` first because its local
    # calendar date is 2020-04-01. SQLite julianday()/unixepoch()
    # on the supported build also collapse this one-microsecond
    # distinction. job_id deliberately favors the later job too.
    earlier = datetime(
        2020,
        4,
        2,
        0,
        0,
        0,
        1,
        tzinfo=plus_zero,
    )

    later = datetime(
        2020,
        4,
        1,
        19,
        0,
        0,
        2,
        tzinfo=minus_five,
    )

    assert earlier < later

    lexical_earlier = earlier.isoformat(
        timespec="microseconds"
    )

    lexical_later = later.isoformat(
        timespec="microseconds"
    )

    assert lexical_later < lexical_earlier

    later_job = ResearchJob(
        job_id="job-a-m94h3-later",
        trial_id=trial_id,
        state=ResearchJobState.QUEUED,
        created_at=later,
    )

    earlier_job = ResearchJob(
        job_id="job-z-m94h3-earlier",
        trial_id=trial_id,
        state=ResearchJobState.QUEUED,
        created_at=earlier,
    )

    catalog._save_queued_research_job(
        later_job
    )

    catalog._save_queued_research_job(
        earlier_job
    )

    first = _claim_direct(
        catalog,
        queue,
        revision_id,
        worker_id="worker-m94h3-first",
        claimed_at=JUN,
    )

    assert first is not None
    assert first.job_id == earlier_job.job_id

    _terminalize_running_job(
        catalog,
        first,
    )

    second = _claim_direct(
        catalog,
        queue,
        revision_id,
        worker_id="worker-m94h3-second",
        claimed_at=JUN,
    )

    assert second is not None
    assert second.job_id == later_job.job_id


def test_m94h3_fifo_equivalent_instants_use_stable_job_id_tiebreaker(
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
        max_workers=1,
    )

    population = _register(
        registration,
        definition,
        snapshot,
        intent="equivalent instant FIFO tie",
        registered_at=MAR,
        variants=(
            {"variant": 1},
        ),
    )

    revision_id = (
        population.revision.study_revision_id
    )

    queue.start_revision(
        revision_id,
        started_at=APR,
    )

    _m94h3_drain_initial_queue(
        catalog,
        queue,
        population,
    )

    trial_id = (
        population.trials[0].trial_id
    )

    plus_fourteen = timezone(
        timedelta(hours=14)
    )

    minus_ten = timezone(
        -timedelta(hours=10)
    )

    first_representation = datetime(
        2020,
        4,
        2,
        14,
        0,
        tzinfo=plus_fourteen,
    )

    second_representation = datetime(
        2020,
        4,
        1,
        14,
        0,
        tzinfo=minus_ten,
    )

    assert (
        first_representation
        == second_representation
    )

    job_b = ResearchJob(
        job_id="job-b-m94h3-tie",
        trial_id=trial_id,
        state=ResearchJobState.QUEUED,
        created_at=first_representation,
    )

    job_a = ResearchJob(
        job_id="job-a-m94h3-tie",
        trial_id=trial_id,
        state=ResearchJobState.QUEUED,
        created_at=second_representation,
    )

    # Persist in reverse deterministic order.
    catalog._save_queued_research_job(
        job_b
    )

    catalog._save_queued_research_job(
        job_a
    )

    claimed = _claim_direct(
        catalog,
        queue,
        revision_id,
        worker_id="worker-m94h3-tie",
        claimed_at=JUN,
    )

    assert claimed is not None
    assert claimed.job_id == job_a.job_id


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

    claimed = _claim_direct(catalog, queue,
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
                _claim_direct,
                catalog,
                queue,
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

    _claim_direct(catalog, queue,
        population.revision.study_revision_id,
        worker_id="worker-1",
        claimed_at=MAY,
    )

    _claim_direct(catalog, queue,
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


def test_existing_current_schema_restores_queue_indexes_without_version_bump(
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
            == 5
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
            == 5
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


def test_service_direct_claim_api_is_demoted(
    tmp_path,
):
    (
        _catalog,
        _registration,
        queue,
        _definition,
        _snapshot,
    ) = _environment(tmp_path)

    assert not hasattr(
        queue,
        "claim_next",
    )


def test_worker_pool_claim_occurs_inside_executor_thread(
    tmp_path,
    monkeypatch,
):
    (
        catalog,
        registration,
        queue,
        definition,
        snapshot,
    ) = _environment(
        tmp_path,
        max_workers=1,
    )

    population = _register(
        registration,
        definition,
        snapshot,
        intent="worker thread authority",
        registered_at=MAR,
        variants=(
            {"variant": 1},
        ),
    )

    queue.start_revision(
        population.revision.study_revision_id,
        started_at=APR,
    )

    caller_thread = get_ident()
    claim_threads = []
    handler_threads = []

    original_claim = (
        queue._claim_next_in_worker_slot
    )

    def observed_claim(
        *args,
        **kwargs,
    ):
        claim_threads.append(
            get_ident()
        )

        return original_claim(
            *args,
            **kwargs,
        )

    monkeypatch.setattr(
        queue,
        "_claim_next_in_worker_slot",
        observed_claim,
    )

    def handle(job):
        handler_threads.append(
            get_ident()
        )

        _terminalize_running_job(
            catalog,
            job,
        )

    result = queue.run_worker_pool(
        population.revision.study_revision_id,
        worker_id_factory=(
            lambda slot: f"worker-{slot}"
        ),
        claimed_at_factory=lambda: MAY,
        execute_claimed_job=handle,
    )

    assert claim_threads
    assert handler_threads

    assert all(
        thread_id != caller_thread
        for thread_id in claim_threads
    )

    assert set(
        handler_threads
    ).issubset(
        set(
            claim_threads
        )
    )

    assert result.queued_jobs == 0
    assert result.running_jobs == 0
    assert result.failed_jobs == 3


def test_worker_slot_is_held_until_handler_returns(
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
        max_workers=1,
    )

    population = _register(
        registration,
        definition,
        snapshot,
        intent="slot lifetime",
        registered_at=MAR,
        variants=(
            {"variant": 1},
        ),
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

    entered = Event()
    release = Event()

    def handle(job):
        if job.job_id == expected[0]:
            entered.set()

            assert release.wait(
                timeout=5
            )

        _terminalize_running_job(
            catalog,
            job,
        )

    with ThreadPoolExecutor(
        max_workers=1
    ) as caller:
        future = caller.submit(
            queue.run_worker_pool,
            population.revision.study_revision_id,
            worker_id_factory=(
                lambda slot: f"worker-{slot}"
            ),
            claimed_at_factory=lambda: MAY,
            execute_claimed_job=handle,
        )

        assert entered.wait(
            timeout=5
        )

        during = queue.snapshot(
            population.revision.study_revision_id
        )

        assert during.running_jobs == 1
        assert during.queued_jobs == 2
        assert not future.done()

        release.set()

        after = future.result(
            timeout=5
        )

    assert after.running_jobs == 0
    assert after.queued_jobs == 0
    assert after.failed_jobs == 3


def test_worker_pool_never_exceeds_configured_worker_count(
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
        intent="bounded handler concurrency",
        registered_at=MAR,
    )

    queue.start_revision(
        population.revision.study_revision_id,
        started_at=APR,
    )

    active_lock = Lock()
    release = Event()
    two_active = Event()

    active = 0
    maximum_active = 0

    def handle(job):
        nonlocal active
        nonlocal maximum_active

        with active_lock:
            active += 1
            maximum_active = max(
                maximum_active,
                active,
            )

            if active == 2:
                two_active.set()

        try:
            assert release.wait(
                timeout=5
            )

            _terminalize_running_job(
                catalog,
                job,
            )

        finally:
            with active_lock:
                active -= 1

    with ThreadPoolExecutor(
        max_workers=1
    ) as caller:
        future = caller.submit(
            queue.run_worker_pool,
            population.revision.study_revision_id,
            worker_id_factory=(
                lambda slot: f"worker-{slot}"
            ),
            claimed_at_factory=lambda: MAY,
            execute_claimed_job=handle,
        )

        assert two_active.wait(
            timeout=5
        )

        during = queue.snapshot(
            population.revision.study_revision_id
        )

        assert during.running_jobs == 2
        assert maximum_active == 2

        release.set()

        after = future.result(
            timeout=5
        )

    assert maximum_active <= 2
    assert after.running_jobs == 0
    assert after.queued_jobs == 0
    assert after.failed_jobs == 6


def test_worker_pool_stops_new_claims_when_handler_fails(
    tmp_path,
):
    (
        _catalog,
        registration,
        queue,
        definition,
        snapshot,
    ) = _environment(
        tmp_path,
        max_workers=1,
    )

    population = _register(
        registration,
        definition,
        snapshot,
        intent="handler failure stop",
        registered_at=MAR,
        variants=(
            {"variant": 1},
        ),
    )

    queue.start_revision(
        population.revision.study_revision_id,
        started_at=APR,
    )

    seen = []

    def fail(job):
        seen.append(
            job.job_id
        )

        raise RuntimeError(
            "worker handler failed"
        )

    with pytest.raises(
        RuntimeError,
        match="worker handler failed",
    ):
        queue.run_worker_pool(
            population.revision.study_revision_id,
            worker_id_factory=(
                lambda slot: f"worker-{slot}"
            ),
            claimed_at_factory=lambda: MAY,
            execute_claimed_job=fail,
        )

    after = queue.snapshot(
        population.revision.study_revision_id
    )

    assert len(seen) == 1
    assert after.running_jobs == 1
    assert after.queued_jobs == 2


def test_worker_pool_rejects_handler_return_with_running_job(
    tmp_path,
):
    (
        _catalog,
        registration,
        queue,
        definition,
        snapshot,
    ) = _environment(
        tmp_path,
        max_workers=1,
    )

    population = _register(
        registration,
        definition,
        snapshot,
        intent="terminal verification",
        registered_at=MAR,
        variants=(
            {"variant": 1},
        ),
    )

    queue.start_revision(
        population.revision.study_revision_id,
        started_at=APR,
    )

    with pytest.raises(
        RuntimeError,
        match="must durably terminalize",
    ):
        queue.run_worker_pool(
            population.revision.study_revision_id,
            worker_id_factory=(
                lambda slot: f"worker-{slot}"
            ),
            claimed_at_factory=lambda: MAY,
            execute_claimed_job=(
                lambda _job: None
            ),
        )

    after = queue.snapshot(
        population.revision.study_revision_id
    )

    assert after.running_jobs == 1
    assert after.queued_jobs == 2


def test_worker_pool_empty_queue_returns_clean_snapshot(
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
        max_workers=1,
    )

    population = _register(
        registration,
        definition,
        snapshot,
        intent="empty queue",
        registered_at=MAR,
        variants=(
            {"variant": 1},
        ),
    )

    revision_id = (
        population.revision.study_revision_id
    )

    queue.start_revision(
        revision_id,
        started_at=APR,
    )

    seeded = 0

    while True:
        job = _claim_direct(
            catalog,
            queue,
            revision_id,
            worker_id=f"seed-{seeded}",
            claimed_at=MAY,
        )

        if job is None:
            break

        _terminalize_running_job(
            catalog,
            job,
        )

        seeded += 1

    assert seeded == 3

    result = queue.run_worker_pool(
        revision_id,
        worker_id_factory=(
            lambda slot: f"worker-{slot}"
        ),
        claimed_at_factory=lambda: JUN,
        execute_claimed_job=(
            lambda _job: pytest.fail(
                "empty queue must not invoke handler"
            )
        ),
    )

    assert result.queued_jobs == 0
    assert result.running_jobs == 0
    assert result.failed_jobs == 3


def test_worker_pool_claiming_creates_no_runattempt(
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
        max_workers=1,
    )

    population = _register(
        registration,
        definition,
        snapshot,
        intent="claim creates no attempt",
        registered_at=MAR,
        variants=(
            {"variant": 1},
        ),
    )

    queue.start_revision(
        population.revision.study_revision_id,
        started_at=APR,
    )

    observed_attempt_counts = []

    def handle(job):
        with closing(
            sqlite3.connect(
                catalog.database_path
            )
        ) as connection:
            observed_attempt_counts.append(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM run_attempts
                    """
                ).fetchone()[0]
            )

        _terminalize_running_job(
            catalog,
            job,
        )

    queue.run_worker_pool(
        population.revision.study_revision_id,
        worker_id_factory=(
            lambda slot: f"worker-{slot}"
        ),
        claimed_at_factory=lambda: MAY,
        execute_claimed_job=handle,
    )

    assert observed_attempt_counts == [
        0,
        0,
        0,
    ]


def test_worker_pool_preserves_fifo_atomic_claiming(
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
        max_workers=1,
    )

    population = _register(
        registration,
        definition,
        snapshot,
        intent="pool FIFO",
        registered_at=MAR,
        variants=(
            {"variant": 1},
        ),
    )

    revision_id = (
        population.revision.study_revision_id
    )

    queue.start_revision(
        revision_id,
        started_at=APR,
    )

    expected = [
        job.job_id
        for job in _jobs_for_population(
            catalog,
            population,
        )
    ]

    seen = []

    def handle(job):
        seen.append(
            job.job_id
        )

        _terminalize_running_job(
            catalog,
            job,
        )

    result = queue.run_worker_pool(
        revision_id,
        worker_id_factory=(
            lambda slot: f"worker-{slot}"
        ),
        claimed_at_factory=lambda: MAY,
        execute_claimed_job=handle,
    )

    assert seen == expected
    assert result.queued_jobs == 0
    assert result.running_jobs == 0
    assert result.failed_jobs == 3


def test_m94g2_public_initial_job_insert_cannot_bypass_start(
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
        max_workers=1,
    )

    population = _register(
        registration,
        definition,
        snapshot,
        intent="public initial-job bypass rejection",
        registered_at=MAR,
        variants=(
            {"variant": 1},
        ),
    )

    trial = population.trials[0]

    bypass = ResearchJob(
        job_id="out-of-band-initial",
        trial_id=trial.trial_id,
        state=ResearchJobState.QUEUED,
        created_at=APR,
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
        == ()
    )

    started = queue.start_revision(
        population.revision.study_revision_id,
        started_at=APR,
    )

    expected_trials = len(
        population.trials
    )

    assert started.total_registered_trials == expected_trials
    assert started.total_jobs == expected_trials
    assert started.queued_jobs == expected_trials
