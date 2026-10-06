from __future__ import annotations

from collections.abc import (
    Callable,
    Iterable,
    Mapping,
)
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from api.models.research_models import (
    ResearchAggregationResponse,
    ResearchMetricDistributionResponse,
    ResearchProgressResponse,
    ResearchRevisionRegistrationResponse,
    ResearchRunAttemptResponse,
    ResearchStudyResponse,
    ResearchTrialDetailResponse,
    ResearchTrialDispositionEventResponse,
    ResearchJobLineageResponse,
    ResearchTrialListResponse,
    ResearchTrialResponse,
)
from core.config.app_config import AppConfig
from core.config.loaders import load_app_config
from core.market_data.historical_coverage import (
    TimeRange,
)
from core.research.models.registered_study import (
    EvidenceReusePolicy,
    ResearchQueueSnapshot,
    Study,
)
from core.research.models.universe import (
    UniverseDefinition,
    UniverseSnapshot,
)
from core.research.registered_study_registration import (
    RegisteredStudyRegistrationService,
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
from core.research.study_aggregation import (
    StudyAggregationService,
)


StudyIdFactory = Callable[[], str]
Clock = Callable[[], datetime]


class ResearchStudyNotFound(LookupError):
    """Requested Study does not exist."""


class ResearchRevisionNotFound(LookupError):
    """Requested StudyRevision does not exist."""


class ResearchTrialNotFound(LookupError):
    """Requested Trial does not exist."""


class ResearchIdentifierValidationError(ValueError):
    """Semantic research identifier is empty or whitespace."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _default_study_id() -> str:
    return "study-" + uuid4().hex


def _resolved_config(
    app_config: AppConfig | None,
) -> AppConfig:
    return (
        app_config
        if app_config is not None
        else load_app_config()
    )


def _catalog_store(
    app_config: AppConfig,
) -> SQLiteResearchCatalogStore:
    return SQLiteResearchCatalogStore(
        app_config.research_database_path
    )


def _require_nonempty(
    value: str,
    field_name: str,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise ResearchIdentifierValidationError(
            f"{field_name} must be a non-empty string"
        )

    return value


def _require_revision(
    store: SQLiteResearchCatalogStore,
    study_revision_id: str,
):
    revision = store.load_study_revision(
        study_revision_id
    )

    if revision is None:
        raise ResearchRevisionNotFound(
            study_revision_id
        )

    return revision


def _study_response(
    study: Study,
) -> ResearchStudyResponse:
    return ResearchStudyResponse(
        study_id=study.study_id,
        created_at=study.created_at,
        display_title=study.display_title,
        archived=study.archived,
    )


def _progress_response(
    snapshot: ResearchQueueSnapshot,
) -> ResearchProgressResponse:
    return ResearchProgressResponse(
        study_revision_id=(
            snapshot.study_revision_id
        ),
        initial_batch_started_at=(
            snapshot.initial_batch_started_at
        ),
        total_registered_trials=(
            snapshot.total_registered_trials
        ),
        pending_trials=snapshot.pending_trials,
        executed_trials=snapshot.executed_trials,
        reused_trials=snapshot.reused_trials,
        invalid_trials=snapshot.invalid_trials,
        insufficient_trials=(
            snapshot.insufficient_trials
        ),
        failed_trials=snapshot.failed_trials,
        cancelled_trials=snapshot.cancelled_trials,
        interrupted_trials=(
            snapshot.interrupted_trials
        ),
        queued_jobs=snapshot.queued_jobs,
        running_jobs=snapshot.running_jobs,
        succeeded_jobs=snapshot.succeeded_jobs,
        failed_jobs=snapshot.failed_jobs,
        cancelled_jobs=snapshot.cancelled_jobs,
        interrupted_jobs=snapshot.interrupted_jobs,
        total_jobs=snapshot.total_jobs,
    )


def _enum_value(
    value,
) -> str | None:
    if value is None:
        return None

    if hasattr(value, "value"):
        return str(value.value)

    return str(value)


def _trial_response(
    trial,
) -> ResearchTrialResponse:
    return ResearchTrialResponse(
        trial_id=trial.trial_id,
        study_revision_id=(
            trial.study_revision_id
        ),
        instrument_id=(
            trial.instrument_id
        ),
        membership_episode_start=(
            trial.membership_episode_start
        ),
        membership_episode_end=(
            trial.membership_episode_end
        ),
        disposition=(
            _enum_value(
                trial.disposition
            )
        ),
        disposition_at=(
            trial.disposition_at
        ),
        experiment_spec_id=(
            trial.experiment_spec_id
        ),
        reused_attempt_id=(
            trial.reused_attempt_id
        ),
        failure_classification=(
            trial.failure_classification
        ),
        failure_message=(
            trial.failure_message
        ),
    )


def _run_attempt_response(
    attempt,
) -> ResearchRunAttemptResponse:
    return ResearchRunAttemptResponse(
        attempt_id=attempt.attempt_id,
        experiment_spec_id=(
            attempt.experiment_spec_id
        ),
        state=_enum_value(
            attempt.state
        ),
        created_at=attempt.created_at,
        terminal_at=attempt.terminal_at,
        runtime_session_id=(
            attempt.runtime_session_id
        ),
        result_artifact_id=(
            attempt.result_artifact_id
        ),
        evidence_id=attempt.evidence_id,
        failure_classification=(
            attempt.failure_classification
        ),
        failure_message=(
            attempt.failure_message
        ),
    )


def _metric_distribution_response(
    distribution,
) -> ResearchMetricDistributionResponse:
    return ResearchMetricDistributionResponse(
        count=distribution.count,
        mean=distribution.mean,
        median=distribution.median,
        minimum=distribution.minimum,
        maximum=distribution.maximum,
        positive_count=(
            distribution.positive_count
        ),
        positive_proportion=(
            distribution.positive_proportion
        ),
    )


def create_research_study(
    display_title: str,
    *,
    app_config: AppConfig | None = None,
    study_id_factory: StudyIdFactory = (
        _default_study_id
    ),
    clock: Clock = _utc_now,
) -> ResearchStudyResponse:
    _require_nonempty(
        display_title,
        "display_title",
    )

    if not callable(study_id_factory):
        raise TypeError(
            "study_id_factory must be callable"
        )

    if not callable(clock):
        raise TypeError(
            "clock must be callable"
        )

    study_id = study_id_factory()

    _require_nonempty(
        study_id,
        "study_id",
    )

    config = _resolved_config(
        app_config
    )
    store = _catalog_store(
        config
    )

    study = Study(
        study_id=study_id,
        created_at=clock(),
        display_title=display_title,
        archived=False,
    )

    persisted = store.save_study(
        study
    )

    return _study_response(
        persisted
    )


def reopen_research_study(
    study_id: str,
    *,
    app_config: AppConfig | None = None,
) -> ResearchStudyResponse:
    _require_nonempty(
        study_id,
        "study_id",
    )

    config = _resolved_config(
        app_config
    )
    store = _catalog_store(
        config
    )

    current = store.load_study(
        study_id
    )

    if current is None:
        raise ResearchStudyNotFound(
            study_id
        )

    reopened = store.update_study_metadata(
        study_id,
        display_title=current.display_title,
        archived=False,
    )

    return _study_response(
        reopened
    )


def register_research_revision(
    *,
    study_id: str,
    research_intent: str,
    strategy_procedure_id: str,
    timeframe: str,
    research_range: TimeRange,
    timezone: str,
    initial_capital: float,
    risk_economic_configuration: (
        Mapping[str, Any]
    ),
    parameter_variants: (
        Iterable[Mapping[str, Any]]
    ),
    universe_definition: UniverseDefinition,
    universe_snapshots: (
        Iterable[UniverseSnapshot]
    ),
    require_point_in_time: bool,
    data_treatment_basis: (
        Mapping[str, Any]
    ),
    repository_revision: str,
    evidence_reuse_policy: (
        EvidenceReusePolicy
    ),
    registered_at: datetime,
    app_config: AppConfig | None = None,
) -> ResearchRevisionRegistrationResponse:
    _require_nonempty(
        study_id,
        "study_id",
    )

    config = _resolved_config(
        app_config
    )
    store = _catalog_store(
        config
    )

    if store.load_study(study_id) is None:
        raise ResearchStudyNotFound(
            study_id
        )

    artifact_store = (
        ContentAddressedResearchArtifactStore(
            config.research_artifact_root
        )
    )

    registration = (
        RegisteredStudyRegistrationService(
            catalog_store=store,
            artifact_store=artifact_store,
            max_trials_per_revision=(
                config
                .research_max_trials_per_revision
            ),
        )
    )

    snapshots = tuple(
        universe_snapshots
    )

    population = (
        registration.register_study_revision(
            study_id=study_id,
            research_intent=research_intent,
            strategy_procedure_id=(
                strategy_procedure_id
            ),
            timeframe=timeframe,
            research_range=research_range,
            timezone=timezone,
            initial_capital=initial_capital,
            risk_economic_configuration=(
                risk_economic_configuration
            ),
            parameter_variants=(
                parameter_variants
            ),
            universe_definition=(
                universe_definition
            ),
            universe_snapshots=snapshots,
            require_point_in_time=(
                require_point_in_time
            ),
            data_treatment_basis=(
                data_treatment_basis
            ),
            repository_revision=(
                repository_revision
            ),
            evidence_reuse_policy=(
                evidence_reuse_policy
            ),
            registered_at=registered_at,
        )
    )

    revision = population.revision

    return ResearchRevisionRegistrationResponse(
        study_revision_id=(
            revision.study_revision_id
        ),
        study_id=revision.study_id,
        revision_number=(
            revision.revision_number
        ),
        plan_artifact_id=(
            revision.plan_artifact_id
        ),
        repository_revision=(
            revision.repository_revision
        ),
        evidence_reuse_policy=(
            revision.evidence_reuse_policy.value
            if isinstance(
                revision.evidence_reuse_policy,
                EvidenceReusePolicy,
            )
            else str(
                revision.evidence_reuse_policy
            )
        ),
        registered_at=(
            revision.registered_at
        ),
        initial_batch_started_at=(
            revision.initial_batch_started_at
        ),
        total_registered_trials=len(
            population.trials
        ),
    )


def list_research_trials(
    study_revision_id: str,
    *,
    app_config: AppConfig | None = None,
) -> ResearchTrialListResponse:
    _require_nonempty(
        study_revision_id,
        "study_revision_id",
    )

    config = _resolved_config(
        app_config
    )
    store = _catalog_store(
        config
    )

    _require_revision(
        store,
        study_revision_id,
    )

    trials = tuple(
        store.list_trials_for_revision(
            study_revision_id
        )
    )

    return ResearchTrialListResponse(
        study_revision_id=(
            study_revision_id
        ),
        total_registered_trials=len(
            trials
        ),
        trials=[
            _trial_response(
                trial
            )
            for trial in trials
        ],
    )


def get_research_trial_detail(
    trial_id: str,
    *,
    app_config: AppConfig | None = None,
) -> ResearchTrialDetailResponse:
    _require_nonempty(
        trial_id,
        "trial_id",
    )

    config = _resolved_config(
        app_config
    )
    store = _catalog_store(
        config
    )

    snapshot = (
        store.load_research_trial_detail_snapshot(
            trial_id
        )
    )

    if snapshot is None:
        raise ResearchTrialNotFound(
            trial_id
        )

    trial = snapshot.trial
    events = snapshot.disposition_events
    jobs = snapshot.jobs

    owned_attempts = dict(
        snapshot.owned_attempts
    )
    reused_attempts = dict(
        snapshot.reused_attempts
    )

    event_responses = [
        ResearchTrialDispositionEventResponse(
            event_id=event.event_id,
            trial_id=event.trial_id,
            sequence_number=(
                event.sequence_number
            ),
            previous_disposition=(
                _enum_value(
                    event.previous_disposition
                )
            ),
            new_disposition=(
                _enum_value(
                    event.new_disposition
                )
            ),
            occurred_at=event.occurred_at,
            causing_job_id=(
                event.causing_job_id
            ),
            reason_classification=(
                event.reason_classification
            ),
            reason_message=(
                event.reason_message
            ),
        )
        for event in events
    ]

    job_responses = []

    for job in jobs:
        attempt = None
        reused_attempt = None

        if job.attempt_id is not None:
            attempt = owned_attempts.get(
                job.attempt_id
            )

            if attempt is None:
                raise RuntimeError(
                    "ResearchJob attempt lineage "
                    "references a missing RunAttempt"
                )

        if job.reused_attempt_id is not None:
            reused_attempt = (
                reused_attempts.get(
                    job.reused_attempt_id
                )
            )

            if reused_attempt is None:
                raise RuntimeError(
                    "ResearchJob reused lineage "
                    "references a missing RunAttempt"
                )

        job_responses.append(
            ResearchJobLineageResponse(
                job_id=job.job_id,
                trial_id=job.trial_id,
                state=_enum_value(
                    job.state
                ),
                created_at=job.created_at,
                claimed_at=job.claimed_at,
                terminal_at=job.terminal_at,
                worker_id=job.worker_id,
                cancel_requested_at=(
                    job.cancel_requested_at
                ),
                attempt_id=job.attempt_id,
                completion_kind=(
                    _enum_value(
                        job.completion_kind
                    )
                ),
                reused_attempt_id=(
                    job.reused_attempt_id
                ),
                reused_evidence_id=(
                    job.reused_evidence_id
                ),
                reused_result_artifact_id=(
                    job.reused_result_artifact_id
                ),
                failure_classification=(
                    job.failure_classification
                ),
                failure_message=(
                    job.failure_message
                ),
                attempt=(
                    _run_attempt_response(
                        attempt
                    )
                    if attempt is not None
                    else None
                ),
                reused_attempt=(
                    _run_attempt_response(
                        reused_attempt
                    )
                    if reused_attempt is not None
                    else None
                ),
            )
        )

    return ResearchTrialDetailResponse(
        trial=_trial_response(
            trial
        ),
        disposition_events=(
            event_responses
        ),
        jobs=job_responses,
    )


def run_research_revision(
    study_revision_id: str,
    *,
    execute_claimed_job,
    worker_id_factory,
    claimed_at_factory,
    app_config: AppConfig | None = None,
) -> ResearchProgressResponse:
    _require_nonempty(
        study_revision_id,
        "study_revision_id",
    )

    for value, field_name in (
        (
            execute_claimed_job,
            "execute_claimed_job",
        ),
        (
            worker_id_factory,
            "worker_id_factory",
        ),
        (
            claimed_at_factory,
            "claimed_at_factory",
        ),
    ):
        if not callable(value):
            raise TypeError(
                f"{field_name} must be callable"
            )

    config = _resolved_config(
        app_config
    )
    store = _catalog_store(
        config
    )

    _require_revision(
        store,
        study_revision_id,
    )

    queue = ResearchJobQueueService(
        catalog_store=store,
        app_config=config,
    )

    snapshot = queue.run_worker_pool(
        study_revision_id,
        worker_id_factory=(
            worker_id_factory
        ),
        claimed_at_factory=(
            claimed_at_factory
        ),
        execute_claimed_job=(
            execute_claimed_job
        ),
    )

    return _progress_response(
        snapshot
    )


def start_research_revision(
    study_revision_id: str,
    *,
    started_at: datetime,
    app_config: AppConfig | None = None,
) -> ResearchProgressResponse:
    _require_nonempty(
        study_revision_id,
        "study_revision_id",
    )

    config = _resolved_config(
        app_config
    )
    store = _catalog_store(
        config
    )

    _require_revision(
        store,
        study_revision_id,
    )

    queue = ResearchJobQueueService(
        catalog_store=store,
        app_config=config,
    )

    snapshot = queue.start_revision(
        study_revision_id,
        started_at=started_at,
    )

    return _progress_response(
        snapshot
    )


def cancel_research_revision(
    study_revision_id: str,
    *,
    requested_at: datetime,
    app_config: AppConfig | None = None,
) -> ResearchProgressResponse:
    _require_nonempty(
        study_revision_id,
        "study_revision_id",
    )

    config = _resolved_config(
        app_config
    )
    store = _catalog_store(
        config
    )

    _require_revision(
        store,
        study_revision_id,
    )

    store.cancel_study_revision_batch(
        study_revision_id=(
            study_revision_id
        ),
        requested_at=requested_at,
    )

    snapshot = (
        store.load_research_queue_snapshot(
            study_revision_id
        )
    )

    return _progress_response(
        snapshot
    )


def get_research_aggregation(
    study_revision_id: str,
    *,
    app_config: AppConfig | None = None,
) -> ResearchAggregationResponse:
    _require_nonempty(
        study_revision_id,
        "study_revision_id",
    )

    config = _resolved_config(
        app_config
    )
    store = _catalog_store(
        config
    )

    _require_revision(
        store,
        study_revision_id,
    )

    artifact_store = (
        ContentAddressedResearchArtifactStore(
            config.research_artifact_root
        )
    )

    aggregation = StudyAggregationService(
        catalog_store=store,
        artifact_store=artifact_store,
    ).aggregate_revision(
        study_revision_id
    )

    return ResearchAggregationResponse(
        study_revision_id=(
            aggregation.study_revision_id
        ),
        aggregation_basis=(
            aggregation.aggregation_basis
        ),
        total_registered_trials=(
            aggregation.total_registered_trials
        ),
        result_bearing_trials=(
            aggregation.result_bearing_trials
        ),
        excluded_trials=(
            aggregation.excluded_trials
        ),
        pending_trials=(
            aggregation.pending_trials
        ),
        executed_trials=(
            aggregation.executed_trials
        ),
        reused_trials=(
            aggregation.reused_trials
        ),
        invalid_trials=(
            aggregation.invalid_trials
        ),
        insufficient_trials=(
            aggregation.insufficient_trials
        ),
        failed_trials=(
            aggregation.failed_trials
        ),
        cancelled_trials=(
            aggregation.cancelled_trials
        ),
        interrupted_trials=(
            aggregation.interrupted_trials
        ),
        account_return_pct=(
            _metric_distribution_response(
                aggregation.account_return_pct
            )
        ),
        max_equity_drawdown_pct=(
            _metric_distribution_response(
                aggregation
                .max_equity_drawdown_pct
            )
        ),
        result_artifact_ids=list(
            aggregation.result_artifact_ids
        ),
    )


def get_research_progress(
    study_revision_id: str,
    *,
    app_config: AppConfig | None = None,
) -> ResearchProgressResponse:
    """
    Load truthful registered-Trial and ResearchJob progress.

    The durable ResearchQueueSnapshot remains the authoritative domain
    read model. This application function only maps that snapshot into
    the stable external API contract.
    """

    _require_nonempty(
        study_revision_id,
        "study_revision_id",
    )

    config = _resolved_config(
        app_config
    )
    store = _catalog_store(
        config
    )

    _require_revision(
        store,
        study_revision_id,
    )

    snapshot = (
        store.load_research_queue_snapshot(
            study_revision_id
        )
    )

    return _progress_response(
        snapshot
    )
