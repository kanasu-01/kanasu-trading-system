"""M9.4 durable Start and bounded ResearchJob scheduling.

BEHAVIOR IMPACT: CHANGED
PRIMARY BEHAVIOR ID:
- RESEARCH-RULE-016

The durable SQLite queue remains the atomic claim authority, while the
backend scheduler now owns a real bounded local worker pool. A
ResearchJob may transition QUEUED -> RUNNING only from inside an
executing pool slot, and that slot remains occupied until the injected
job handler has durably terminalized the claimed ResearchJob.

The database-wide RUNNING count remains defence in depth across
independent scheduler instances.

This scheduler layer invokes an injected claimed-job handler but does
not itself define Backtest execution, ExperimentSpec or RunAttempt
creation, evidence reuse, retry, cancellation, stale-job recovery,
qualification, distributed scheduling, or broker execution.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Event, Lock

from core.config.app_config import AppConfig
from core.research.models.registered_study import (
    RESEARCH_MAX_WORKERS_SAFETY_CEILING,
    ResearchJob,
    ResearchJobState,
    ResearchQueueSnapshot,
)
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)


WorkerIdFactory = Callable[[int], str]
ClaimedAtFactory = Callable[[], datetime]
ExecuteClaimedJob = Callable[[ResearchJob], None]


_TERMINAL_RESEARCH_JOB_STATES = frozenset(
    {
        ResearchJobState.SUCCEEDED,
        ResearchJobState.FAILED,
        ResearchJobState.CANCELLED,
        ResearchJobState.INTERRUPTED,
    }
)


class ResearchJobQueueService:
    """Backend-owned durable Start and bounded worker authority."""

    def __init__(
        self,
        *,
        catalog_store: SQLiteResearchCatalogStore,
        app_config: AppConfig,
    ) -> None:
        if not isinstance(
            catalog_store,
            SQLiteResearchCatalogStore,
        ):
            raise TypeError(
                "catalog_store must be a "
                "SQLiteResearchCatalogStore"
            )

        if not isinstance(
            app_config,
            AppConfig,
        ):
            raise TypeError(
                "app_config must be an AppConfig"
            )

        max_workers = (
            app_config.research_max_workers
        )

        if (
            type(max_workers) is not int
            or max_workers <= 0
            or max_workers
            > RESEARCH_MAX_WORKERS_SAFETY_CEILING
        ):
            raise ValueError(
                "research_max_workers must be between 1 and "
                f"{RESEARCH_MAX_WORKERS_SAFETY_CEILING}"
            )

        self.catalog_store = catalog_store
        self.research_max_workers = (
            max_workers
        )

    def start_revision(
        self,
        study_revision_id: str,
        *,
        started_at: datetime,
    ) -> ResearchQueueSnapshot:
        self.catalog_store.start_study_revision_batch(
            study_revision_id,
            started_at,
        )

        return self.snapshot(
            study_revision_id
        )

    def _claim_next_in_worker_slot(
        self,
        study_revision_id: str,
        *,
        worker_id: str,
        claimed_at: datetime,
    ) -> ResearchJob | None:
        """
        Claim one durable job.

        This helper is deliberately private. The scheduler calls it only
        from an executing ThreadPoolExecutor worker.
        """

        return (
            self.catalog_store
            .claim_next_research_job(
                study_revision_id,
                worker_id,
                claimed_at,
                max_running_jobs=(
                    self.research_max_workers
                ),
            )
        )

    def _require_terminal_job(
        self,
        claimed_job: ResearchJob,
    ) -> ResearchJob:
        persisted = (
            self.catalog_store.load_research_job(
                claimed_job.job_id
            )
        )

        if persisted is None:
            raise RuntimeError(
                "claimed ResearchJob disappeared after handler"
            )

        if (
            persisted.state
            not in _TERMINAL_RESEARCH_JOB_STATES
        ):
            raise RuntimeError(
                "execute_claimed_job must durably terminalize "
                "ResearchJob before returning"
            )

        if (
            persisted.worker_id
            != claimed_job.worker_id
            or persisted.claimed_at
            != claimed_job.claimed_at
        ):
            raise RuntimeError(
                "terminal ResearchJob claim identity changed"
            )

        return persisted

    def run_worker_pool(
        self,
        study_revision_id: str,
        *,
        worker_id_factory: WorkerIdFactory,
        claimed_at_factory: ClaimedAtFactory,
        execute_claimed_job: ExecuteClaimedJob,
    ) -> ResearchQueueSnapshot:
        """
        Drain currently claimable work with bounded long-lived workers.

        Each pool task owns one actual worker slot. It claims one job,
        keeps the slot while the injected handler processes and durably
        terminalizes that job, verifies terminal state, and only then
        attempts another claim.

        A handler/scheduler persistence failure stops new claims. Any
        already-claimed stale RUNNING job is left for the explicit
        M9.4e recovery contract rather than being guessed terminal here.
        """

        if (
            not isinstance(study_revision_id, str)
            or not study_revision_id
        ):
            raise ValueError(
                "study_revision_id must be a non-empty string"
            )

        for value, name in (
            (
                worker_id_factory,
                "worker_id_factory",
            ),
            (
                claimed_at_factory,
                "claimed_at_factory",
            ),
            (
                execute_claimed_job,
                "execute_claimed_job",
            ),
        ):
            if not callable(value):
                raise TypeError(
                    f"{name} must be callable"
                )

        stop_event = Event()

        # Serialize the local stop-check plus claim initiation. SQLite
        # remains the durable cross-instance duplicate/cap authority.
        claim_gate = Lock()

        def synchronize_stop() -> None:
            stop_event.set()

            # Once this returns, any claim that had already entered the
            # local claim critical section has completed. Later workers
            # see stop_event before beginning another claim.
            with claim_gate:
                pass

        def worker_loop(
            slot_index: int,
        ) -> None:
            try:
                worker_id = worker_id_factory(
                    slot_index
                )
            except Exception:
                synchronize_stop()
                raise

            while True:
                with claim_gate:
                    if stop_event.is_set():
                        return

                    try:
                        claimed_at = (
                            claimed_at_factory()
                        )

                        job = (
                            self
                            ._claim_next_in_worker_slot(
                                study_revision_id,
                                worker_id=worker_id,
                                claimed_at=claimed_at,
                            )
                        )

                    except Exception:
                        stop_event.set()
                        raise

                if job is None:
                    return

                try:
                    execute_claimed_job(
                        job
                    )

                    self._require_terminal_job(
                        job
                    )

                except Exception:
                    synchronize_stop()
                    raise

        first_error: Exception | None = None

        with ThreadPoolExecutor(
            max_workers=self.research_max_workers,
            thread_name_prefix="kanasu-research",
        ) as executor:
            futures = tuple(
                executor.submit(
                    worker_loop,
                    slot_index,
                )
                for slot_index
                in range(
                    self.research_max_workers
                )
            )

            for future in futures:
                try:
                    future.result()
                except Exception as error:
                    if first_error is None:
                        first_error = error

        if first_error is not None:
            raise first_error

        return self.snapshot(
            study_revision_id
        )

    def snapshot(
        self,
        study_revision_id: str,
    ) -> ResearchQueueSnapshot:
        return (
            self.catalog_store
            .load_research_queue_snapshot(
                study_revision_id
            )
        )
