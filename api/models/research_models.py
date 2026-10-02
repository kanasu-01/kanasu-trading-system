from datetime import datetime
from typing import Any

from pydantic import Field

from api.models.common_models import StrictApiModel


class ResearchProgressResponse(StrictApiModel):
    """
    Truthful StudyRevision progress.

    Trial disposition counts retain the fixed registered-Trial
    denominator. ResearchJob counts are reported separately because
    retries may create more jobs than Trials.
    """

    study_revision_id: str = Field(min_length=1)
    initial_batch_started_at: datetime | None

    total_registered_trials: int = Field(ge=0)

    pending_trials: int = Field(ge=0)
    executed_trials: int = Field(ge=0)
    reused_trials: int = Field(ge=0)
    invalid_trials: int = Field(ge=0)
    insufficient_trials: int = Field(ge=0)
    failed_trials: int = Field(ge=0)
    cancelled_trials: int = Field(ge=0)
    interrupted_trials: int = Field(ge=0)

    queued_jobs: int = Field(ge=0)
    running_jobs: int = Field(ge=0)
    succeeded_jobs: int = Field(ge=0)
    failed_jobs: int = Field(ge=0)
    cancelled_jobs: int = Field(ge=0)
    interrupted_jobs: int = Field(ge=0)

    total_jobs: int = Field(ge=0)


class ResearchStudyCreateRequest(StrictApiModel):
    display_title: str = Field(min_length=1)


class ResearchStudyResponse(StrictApiModel):
    study_id: str = Field(min_length=1)
    created_at: datetime
    display_title: str = Field(min_length=1)
    archived: bool


class ResearchTimeRangeRequest(StrictApiModel):
    start: datetime
    end: datetime


class ResearchUniverseDefinitionRequest(
    StrictApiModel
):
    name: str = Field(min_length=1)
    selection_spec: str = Field(min_length=1)
    source_reference: str | None = None


class ResearchUniverseSnapshotRequest(
    StrictApiModel
):
    members: list[str]
    quality: str = Field(min_length=1)
    as_of: datetime
    provenance_refs: list[str]

    effective_from: datetime | None = None
    effective_to: datetime | None = None
    derivation_version: str | None = None


class ResearchRevisionRegistrationRequest(
    StrictApiModel
):
    research_intent: str = Field(min_length=1)
    strategy_procedure_id: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)

    research_range: ResearchTimeRangeRequest
    timezone: str = Field(min_length=1)

    initial_capital: float = Field(gt=0)

    risk_economic_configuration: dict[
        str,
        Any,
    ]

    parameter_variants: list[
        dict[str, Any]
    ]

    universe_definition: (
        ResearchUniverseDefinitionRequest
    )

    universe_snapshots: list[
        ResearchUniverseSnapshotRequest
    ]

    require_point_in_time: bool

    data_treatment_basis: dict[
        str,
        Any,
    ]

    repository_revision: str = Field(min_length=1)

    evidence_reuse_policy: str = Field(
        min_length=1
    )


class ResearchRevisionRegistrationResponse(
    StrictApiModel
):
    study_revision_id: str = Field(min_length=1)
    study_id: str = Field(min_length=1)
    revision_number: int = Field(gt=0)
    plan_artifact_id: str = Field(min_length=1)
    repository_revision: str = Field(min_length=1)
    evidence_reuse_policy: str = Field(min_length=1)
    registered_at: datetime
    initial_batch_started_at: datetime | None
    total_registered_trials: int = Field(ge=0)


class ResearchTrialResponse(StrictApiModel):
    trial_id: str = Field(min_length=1)
    study_revision_id: str = Field(min_length=1)
    instrument_id: str = Field(min_length=1)

    membership_episode_start: datetime
    membership_episode_end: datetime

    disposition: str = Field(min_length=1)
    disposition_at: datetime

    experiment_spec_id: str | None
    reused_attempt_id: str | None

    failure_classification: str | None
    failure_message: str | None


class ResearchTrialListResponse(StrictApiModel):
    study_revision_id: str = Field(min_length=1)
    total_registered_trials: int = Field(ge=0)
    trials: list[ResearchTrialResponse]


class ResearchMetricDistributionResponse(
    StrictApiModel
):
    count: int = Field(ge=0)
    mean: float | None
    median: float | None
    minimum: float | None
    maximum: float | None
    positive_count: int = Field(ge=0)
    positive_proportion: float | None


class ResearchAggregationResponse(StrictApiModel):
    """
    Descriptive cross-sectional statistics across independent
    Trial accounts.

    This contract deliberately contains no portfolio-return,
    portfolio-P&L, shared-capital or cross-instrument-netting field.
    """

    study_revision_id: str = Field(min_length=1)
    aggregation_basis: str = Field(min_length=1)

    total_registered_trials: int = Field(ge=0)
    result_bearing_trials: int = Field(ge=0)
    excluded_trials: int = Field(ge=0)

    pending_trials: int = Field(ge=0)
    executed_trials: int = Field(ge=0)
    reused_trials: int = Field(ge=0)
    invalid_trials: int = Field(ge=0)
    insufficient_trials: int = Field(ge=0)
    failed_trials: int = Field(ge=0)
    cancelled_trials: int = Field(ge=0)
    interrupted_trials: int = Field(ge=0)

    account_return_pct: (
        ResearchMetricDistributionResponse
    )
    max_equity_drawdown_pct: (
        ResearchMetricDistributionResponse
    )

    result_artifact_ids: list[str]



class ResearchTrialDispositionEventResponse(
    StrictApiModel
):
    event_id: str = Field(min_length=1)
    trial_id: str = Field(min_length=1)
    sequence_number: int = Field(ge=0)

    previous_disposition: str | None
    new_disposition: str = Field(min_length=1)

    occurred_at: datetime
    causing_job_id: str | None

    reason_classification: str | None
    reason_message: str | None


class ResearchRunAttemptResponse(StrictApiModel):
    attempt_id: str = Field(min_length=1)
    experiment_spec_id: str = Field(min_length=1)
    state: str = Field(min_length=1)

    created_at: datetime
    terminal_at: datetime | None

    runtime_session_id: str | None
    result_artifact_id: str | None
    evidence_id: str | None

    failure_classification: str | None
    failure_message: str | None


class ResearchJobLineageResponse(StrictApiModel):
    job_id: str = Field(min_length=1)
    trial_id: str = Field(min_length=1)
    state: str = Field(min_length=1)

    created_at: datetime
    claimed_at: datetime | None
    terminal_at: datetime | None

    worker_id: str | None
    cancel_requested_at: datetime | None

    attempt_id: str | None
    completion_kind: str | None

    reused_attempt_id: str | None
    reused_evidence_id: str | None
    reused_result_artifact_id: str | None

    failure_classification: str | None
    failure_message: str | None

    attempt: ResearchRunAttemptResponse | None
    reused_attempt: ResearchRunAttemptResponse | None


class ResearchTrialDetailResponse(StrictApiModel):
    trial: ResearchTrialResponse

    disposition_events: list[
        ResearchTrialDispositionEventResponse
    ]

    jobs: list[
        ResearchJobLineageResponse
    ]
