"""M9.4c durable Start and bounded ResearchJob claiming.

BEHAVIOR IMPACT: ADDED
BEHAVIOR IDS:
- RESEARCH-RULE-014
- RESEARCH-RULE-015
- RESEARCH-RULE-016

Start now creates the deterministic durable initial ResearchJob queue
exactly once. Workers claim queued jobs through an atomic SQLite
QUEUED -> RUNNING transition under a backend-owned global capacity
bound.

This slice does not execute Backtests, create ExperimentSpecs or
RunAttempts, reuse evidence, retry work, cancel work, recover stale
work, qualify research, schedule distributed workers, or place broker
orders.
"""

from __future__ import annotations

from datetime import datetime

from core.config.app_config import AppConfig
from core.research.models.registered_study import (
    RESEARCH_MAX_WORKERS_SAFETY_CEILING,
    ResearchJob,
    ResearchQueueSnapshot,
)
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)


class ResearchJobQueueService:
    """Backend-owned durable Start and bounded claim authority."""

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

    def claim_next(
        self,
        study_revision_id: str,
        *,
        worker_id: str,
        claimed_at: datetime,
    ) -> ResearchJob | None:
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
