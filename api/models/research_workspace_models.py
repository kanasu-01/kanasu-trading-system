"""Typed HTTP contracts for the M9.8 research workspace."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from api.application_catalog import (
    SUPPORTED_STRATEGIES,
    SUPPORTED_TIMEFRAMES,
    SUPPORTED_TIMEZONES,
)
from api.models.backtest_models import (
    BacktestRunResponse,
    SMACrossoverParams,
)
from api.models.common_models import (
    MarketOption,
    StrategyOption,
    StrictApiModel,
    SymbolOption,
    TimeframeOption,
)
from api.models.paper_trading_models import PaperTradingStatusResponse


class WorkspaceStudyCreateRequest(StrictApiModel):
    display_title: str = Field(min_length=1)


class WorkspaceStudyResponse(StrictApiModel):
    study_id: str = Field(min_length=1)
    display_title: str = Field(min_length=1)
    created_at: datetime
    archived: bool


class WorkspaceQualificationPolicyResponse(StrictApiModel):
    policy_id: str = Field(min_length=1)
    version: int = Field(gt=0)
    threshold_pct: str = Field(min_length=1)


class ResearchWorkspaceConfigResponse(StrictApiModel):
    markets: list[MarketOption]
    symbols: list[SymbolOption]
    timeframes: list[TimeframeOption]
    strategies: list[StrategyOption]
    timezones: list[str]
    studies: list[WorkspaceStudyResponse]
    active_qualification_policy: WorkspaceQualificationPolicyResponse | None


class WorkspaceBacktestRunRequest(StrictApiModel):
    """Registered Backtest request; symbol authority comes from M9.3 registry."""

    study_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    start: datetime
    end: datetime
    timezone: str = Field(min_length=1)
    initial_capital: float = Field(gt=0)
    strategy_params: SMACrossoverParams = Field(
        default_factory=SMACrossoverParams
    )

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("symbol must not be empty")
        return normalized

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, value: str) -> str:
        normalized = value.strip()
        if normalized not in SUPPORTED_TIMEFRAMES:
            raise ValueError(f"unsupported timeframe: {normalized}")
        return normalized

    @field_validator("strategy_id")
    @classmethod
    def validate_strategy_id(cls, value: str) -> str:
        normalized = value.strip()
        if normalized not in SUPPORTED_STRATEGIES:
            raise ValueError(f"unsupported strategy_id: {normalized}")
        return normalized

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        normalized = value.strip()
        if normalized not in SUPPORTED_TIMEZONES:
            raise ValueError(f"unsupported timezone: {normalized}")
        return normalized

    @model_validator(mode="after")
    def validate_time_window(self):
        start_aware = self.start.utcoffset() is not None
        end_aware = self.end.utcoffset() is not None
        if start_aware != end_aware:
            raise ValueError(
                "start and end must use compatible timezone awareness"
            )
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class WorkspaceBacktestRunResponse(BacktestRunResponse):
    study_id: str = Field(min_length=1)
    study_revision_id: str = Field(min_length=1)
    trial_id: str = Field(min_length=1)


class WorkspaceStrategyState(StrictApiModel):
    study_id: str = Field(min_length=1)
    study_revision_id: str = Field(min_length=1)
    revision_number: int = Field(gt=0)
    trial_id: str = Field(min_length=1)
    instrument_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)
    strategy_procedure_id: str = Field(min_length=1)
    strategy_label: str = Field(min_length=1)
    strategy_parameters: dict[str, Any]
    trial_disposition: str = Field(min_length=1)
    trial_disposition_event_id: str = Field(min_length=1)
    qualification_outcome: str | None = None
    qualification_decision_id: str | None = None
    candidate_revision_id: str | None = None
    wfa_outcome: str | None = None
    wfa_verdict: str | None = None
    wfa_decision_id: str | None = None
    paper_campaign_id: str | None = None
    retryable: bool


class WorkspaceStrategyListResponse(StrictApiModel):
    study_id: str = Field(min_length=1)
    strategies: list[WorkspaceStrategyState]


class WorkspaceRetryRequest(StrictApiModel):
    expected_disposition_event_id: str = Field(min_length=1)


class WorkspaceQualificationRequest(StrictApiModel):
    threshold_pct: Decimal = Field(ge=0, le=100)
    observed_policy_id: str | None = Field(default=None, min_length=1)


class WorkspaceQualificationItemResponse(StrictApiModel):
    trial_id: str = Field(min_length=1)
    strategy_label: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    evidence_validity: str = Field(min_length=1)
    decision_id: str | None = None
    candidate_revision_id: str | None = None
    decision_policy_id: str | None = None
    decision_policy_version: int | None = None
    decision_threshold_pct: str | None = None
    reason: str = Field(min_length=1)


class WorkspaceQualificationResponse(StrictApiModel):
    study_id: str = Field(min_length=1)
    policy: WorkspaceQualificationPolicyResponse
    policy_changed: bool
    policy_current: bool
    results: list[WorkspaceQualificationItemResponse]


class WorkspaceWfaMetricsResponse(StrictApiModel):
    consistency_ratio: float
    avg_account_return_pct: float
    worst_equity_drawdown_pct: float
    stitched_total_return_pct: float
    stitched_max_drawdown_pct: float
    account_return_stability_score: float


class WorkspaceWfaItemResponse(StrictApiModel):
    trial_id: str = Field(min_length=1)
    candidate_revision_id: str | None = None
    strategy_label: str = Field(min_length=1)
    evidence_validity: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    verdict: Literal["PASS", "FAIL"] | None
    decision_id: str | None = None
    reason: str = Field(min_length=1)
    metrics: WorkspaceWfaMetricsResponse | None = None


class WorkspaceWfaResponse(StrictApiModel):
    study_id: str = Field(min_length=1)
    active_policy_id: str | None
    strategies: list[WorkspaceWfaItemResponse]


class WorkspaceWfaRunRequest(StrictApiModel):
    expected_policy_id: str | None


class WorkspacePaperSendRequest(StrictApiModel):
    expected_wfa_decision_ids: list[str]

    @field_validator("expected_wfa_decision_ids")
    @classmethod
    def validate_expected_wfa_decision_ids(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value]
        if any(not item for item in normalized):
            raise ValueError("expected WFA decision IDs must not be empty")
        if len(normalized) != len(set(normalized)):
            raise ValueError("expected WFA decision IDs must be unique")
        return normalized


class WorkspacePaperSendItemResponse(StrictApiModel):
    candidate_revision_id: str | None = None
    strategy_label: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    campaign_id: str | None = None
    reused: bool | None = None
    reason: str = Field(min_length=1)


class WorkspacePaperSendResponse(StrictApiModel):
    study_id: str = Field(min_length=1)
    campaigns: list[WorkspacePaperSendItemResponse]


class WorkspacePaperCampaignResponse(StrictApiModel):
    campaign_id: str = Field(min_length=1)
    study_id: str = Field(min_length=1)
    study_revision_id: str = Field(min_length=1)
    trial_id: str = Field(min_length=1)
    candidate_revision_id: str = Field(min_length=1)
    strategy_label: str = Field(min_length=1)
    wfa_decision_id: str = Field(min_length=1)
    created_at: datetime
    current_authority: bool


class WorkspacePaperCampaignListResponse(StrictApiModel):
    study_id: str = Field(min_length=1)
    campaigns: list[WorkspacePaperCampaignResponse]


class WorkspacePaperSessionResponse(StrictApiModel):
    session_id: str = Field(min_length=1)
    state: str = Field(min_length=1)
    created_at: datetime
    started_at: datetime | None
    terminal_at: datetime | None
    failure_type: str | None
    failure_message: str | None


class WorkspacePaperStartRequest(StrictApiModel):
    expected_latest_session_id: str | None

    @field_validator("expected_latest_session_id")
    @classmethod
    def validate_expected_latest_session_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("expected_latest_session_id must not be empty")
        return normalized


class WorkspacePaperStopRequest(StrictApiModel):
    expected_session_id: str = Field(min_length=1)


class WorkspacePaperHistoryResponse(StrictApiModel):
    campaign: WorkspacePaperCampaignResponse
    sessions: list[WorkspacePaperSessionResponse]
    runtime: PaperTradingStatusResponse | None = None
    campaign_owns_runtime: bool
