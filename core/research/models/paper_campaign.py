"""Persistent qualified-paper campaign records for M9.7."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re


_FINGERPRINT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
PAPER_CAMPAIGN_CONFIG_SCHEMA_ID = "kanasu.paper-campaign-config.v1"


class PaperCampaignSessionState(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"


def _require_nonempty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_fingerprint(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _FINGERPRINT_PATTERN.fullmatch(value):
        raise ValueError(
            f"{field_name} must use sha256:<64 lowercase hexadecimal>"
        )


def _require_aware(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime")
    if value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


@dataclass(frozen=True)
class PaperCampaign:
    """Immutable research lineage for one qualified forward-observation campaign."""

    campaign_id: str
    created_at: datetime
    candidate_revision_id: str
    wfa_decision_id: str
    study_revision_id: str
    trial_id: str
    experiment_spec_id: str
    parameter_configuration_fingerprint: str
    configuration_fingerprint: str
    created_repository_revision: str

    def __post_init__(self) -> None:
        _require_nonempty(self.campaign_id, "campaign_id")
        _require_aware(self.created_at, "created_at")
        _require_fingerprint(
            self.candidate_revision_id,
            "candidate_revision_id",
        )
        _require_nonempty(self.wfa_decision_id, "wfa_decision_id")
        for name in (
            "study_revision_id",
            "trial_id",
            "experiment_spec_id",
            "parameter_configuration_fingerprint",
            "configuration_fingerprint",
        ):
            _require_fingerprint(getattr(self, name), name)
        _require_nonempty(
            self.created_repository_revision,
            "created_repository_revision",
        )


@dataclass(frozen=True)
class PaperCampaignSession:
    """Durable lifecycle evidence for one runtime Paper session episode."""

    session_id: str
    campaign_id: str
    created_at: datetime
    evaluator_repository_revision: str
    live_binding_id: str
    live_provider: str
    live_provider_instrument_id: str
    live_provider_symbol: str
    state: PaperCampaignSessionState
    started_at: datetime | None = None
    terminal_at: datetime | None = None
    terminal_snapshot_json: str | None = None
    failure_type: str | None = None
    failure_message: str | None = None

    def __post_init__(self) -> None:
        _require_nonempty(self.session_id, "session_id")
        _require_nonempty(self.campaign_id, "campaign_id")
        _require_aware(self.created_at, "created_at")
        _require_nonempty(
            self.evaluator_repository_revision,
            "evaluator_repository_revision",
        )
        for name in (
            "live_binding_id",
            "live_provider",
            "live_provider_instrument_id",
            "live_provider_symbol",
        ):
            _require_nonempty(getattr(self, name), name)
        if not isinstance(self.state, PaperCampaignSessionState):
            raise TypeError("state must be a PaperCampaignSessionState")
        if self.started_at is not None:
            _require_aware(self.started_at, "started_at")
        if self.terminal_at is not None:
            _require_aware(self.terminal_at, "terminal_at")
        if self.terminal_snapshot_json is not None:
            _require_nonempty(
                self.terminal_snapshot_json,
                "terminal_snapshot_json",
            )
        if self.failure_type is not None:
            _require_nonempty(self.failure_type, "failure_type")
        if self.failure_message is not None and not isinstance(
            self.failure_message, str
        ):
            raise TypeError("failure_message must be a string or None")

        if self.started_at is not None and self.started_at < self.created_at:
            raise ValueError("started_at cannot precede created_at")
        if self.terminal_at is not None:
            if self.terminal_at < self.created_at:
                raise ValueError("terminal_at cannot precede created_at")
            if (
                self.started_at is not None
                and self.terminal_at < self.started_at
            ):
                raise ValueError("terminal_at cannot precede started_at")

        if self.state is PaperCampaignSessionState.CREATED:
            if any(
                value is not None
                for value in (
                    self.started_at,
                    self.terminal_at,
                    self.terminal_snapshot_json,
                    self.failure_type,
                    self.failure_message,
                )
            ):
                raise ValueError(
                    "CREATED campaign session cannot contain runtime or terminal state"
                )
            return

        if self.state is PaperCampaignSessionState.RUNNING:
            if self.started_at is None:
                raise ValueError("RUNNING campaign session requires started_at")
            if any(
                value is not None
                for value in (
                    self.terminal_at,
                    self.terminal_snapshot_json,
                    self.failure_type,
                    self.failure_message,
                )
            ):
                raise ValueError(
                    "RUNNING campaign session cannot contain terminal state"
                )
            return

        if self.terminal_at is None:
            raise ValueError("terminal campaign session requires terminal_at")

        if self.state is PaperCampaignSessionState.STOPPED:
            if self.terminal_snapshot_json is None:
                raise ValueError(
                    "STOPPED campaign session requires terminal snapshot"
                )
            if self.failure_type is not None or self.failure_message is not None:
                raise ValueError("STOPPED campaign session cannot contain failure")
            return

        if self.state is PaperCampaignSessionState.FAILED:
            if self.failure_type is None or self.failure_message is None:
                raise ValueError("FAILED campaign session requires failure detail")
            return

        if self.state is PaperCampaignSessionState.INTERRUPTED:
            if self.terminal_snapshot_json is not None:
                raise ValueError(
                    "INTERRUPTED campaign session cannot fabricate terminal snapshot"
                )
            if self.failure_type is None or self.failure_message is None:
                raise ValueError(
                    "INTERRUPTED campaign session requires interruption detail"
                )


@dataclass(frozen=True)
class PaperCampaignHistory:
    campaign: PaperCampaign
    sessions: tuple[PaperCampaignSession, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.campaign, PaperCampaign):
            raise TypeError("campaign must be a PaperCampaign")
        if not isinstance(self.sessions, tuple):
            raise TypeError("sessions must be a tuple")
        if any(
            not isinstance(session, PaperCampaignSession)
            for session in self.sessions
        ):
            raise TypeError("sessions must contain PaperCampaignSession values")
        if any(
            session.campaign_id != self.campaign.campaign_id
            for session in self.sessions
        ):
            raise ValueError("campaign history contains a foreign session")
