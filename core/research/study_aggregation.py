from dataclasses import dataclass
from math import fsum, isfinite
from statistics import median

from core.backtest.performance_metrics import (
    PerformanceMetrics,
)
from core.research.models.registered_study import (
    ResearchJobCompletionKind,
    ResearchJobState,
    Trial,
    TrialDisposition,
)
from core.research.models.research_catalog import (
    ResearchArtifactKind,
    RunAttemptState,
)
from core.research.reproducibility import (
    BACKTEST_RESULT_SCHEMA,
    decode_canonical_bytes,
)


AGGREGATION_BASIS = (
    "INDEPENDENT_TRIAL_ACCOUNT_DISTRIBUTION"
)


class StudyAggregationError(RuntimeError):
    """Durable Study aggregation truth cannot be established."""


@dataclass(frozen=True)
class StudyMetricDistribution:
    """
    Cross-sectional distribution across independent Trial accounts.

    positive_count/positive_proportion mean strictly greater than zero
    for the named metric. They are descriptive breadth statistics, not
    portfolio-level statistics.
    """

    count: int
    mean: float | None
    median: float | None
    minimum: float | None
    maximum: float | None
    positive_count: int
    positive_proportion: float | None

    @classmethod
    def from_values(
        cls,
        values,
    ) -> "StudyMetricDistribution":
        values = tuple(
            float(value)
            for value in values
        )

        if any(
            not isfinite(value)
            for value in values
        ):
            raise StudyAggregationError(
                "aggregate metric values must be finite"
            )

        count = len(values)

        if count == 0:
            return cls(
                count=0,
                mean=None,
                median=None,
                minimum=None,
                maximum=None,
                positive_count=0,
                positive_proportion=None,
            )

        positive_count = sum(
            value > 0.0
            for value in values
        )

        return cls(
            count=count,
            mean=fsum(values) / count,
            median=float(median(values)),
            minimum=min(values),
            maximum=max(values),
            positive_count=positive_count,
            positive_proportion=(
                positive_count / count
            ),
        )


@dataclass(frozen=True)
class StudyAggregationResult:
    study_revision_id: str
    aggregation_basis: str

    total_registered_trials: int
    result_bearing_trials: int
    excluded_trials: int

    pending_trials: int
    executed_trials: int
    reused_trials: int
    invalid_trials: int
    insufficient_trials: int
    failed_trials: int
    cancelled_trials: int
    interrupted_trials: int

    account_return_pct: StudyMetricDistribution
    max_equity_drawdown_pct: StudyMetricDistribution

    result_artifact_ids: tuple[str, ...]


class StudyAggregationService:
    """
    Aggregate descriptive statistics across independent Trial accounts.

    This service deliberately does not sum capital, P&L, equity, or
    positions across Trials. Each result-bearing Trial remains an
    independent simulated account.
    """

    def __init__(
        self,
        *,
        catalog_store,
        artifact_store,
    ):
        self.catalog_store = catalog_store
        self.artifact_store = artifact_store

    @staticmethod
    def _result_bearing_disposition(
        disposition: TrialDisposition,
    ) -> bool:
        return disposition in {
            TrialDisposition.EXECUTED,
            TrialDisposition.REUSED,
        }

    def _resolve_result_artifact_id(
        self,
        trial: Trial,
    ) -> str:
        expected_completion = (
            ResearchJobCompletionKind.EXECUTED
            if trial.disposition
            is TrialDisposition.EXECUTED
            else ResearchJobCompletionKind.REUSED
        )

        events = tuple(
            self.catalog_store
            .load_trial_disposition_events(
                trial.trial_id
            )
        )

        if not events:
            raise StudyAggregationError(
                "result-bearing Trial requires "
                "terminal disposition-event lineage"
            )

        event = events[-1]

        if (
            event.trial_id != trial.trial_id
            or event.new_disposition
            is not trial.disposition
            or event.causing_job_id is None
        ):
            raise StudyAggregationError(
                "result-bearing Trial current disposition "
                "does not have truthful causing-job lineage"
            )

        job = (
            self.catalog_store
            .load_research_job(
                event.causing_job_id
            )
        )

        if (
            job is None
            or job.trial_id != trial.trial_id
            or job.state
            is not ResearchJobState.SUCCEEDED
            or job.completion_kind
            is not expected_completion
        ):
            raise StudyAggregationError(
                "result-bearing Trial causing job "
                "does not match current terminal disposition"
            )

        if (
            expected_completion
            is ResearchJobCompletionKind.EXECUTED
        ):
            if job.attempt_id is None:
                raise StudyAggregationError(
                    "EXECUTED result-bearing Trial "
                    "requires RunAttempt lineage"
                )

            attempt = (
                self.catalog_store
                .load_run_attempt(
                    job.attempt_id
                )
            )

            if (
                attempt is None
                or attempt.state
                is not RunAttemptState.SUCCEEDED
                or attempt.result_artifact_id is None
            ):
                raise StudyAggregationError(
                    "EXECUTED result-bearing Trial "
                    "requires successful result-bearing RunAttempt"
                )

            return attempt.result_artifact_id

        if (
            trial.reused_attempt_id is None
            or job.reused_attempt_id
            != trial.reused_attempt_id
            or job.reused_result_artifact_id is None
        ):
            raise StudyAggregationError(
                "REUSED result-bearing Trial "
                "requires exact reused result lineage"
            )

        source_attempt = (
            self.catalog_store
            .load_run_attempt(
                job.reused_attempt_id
            )
        )

        if (
            source_attempt is None
            or source_attempt.state
            is not RunAttemptState.SUCCEEDED
            or source_attempt.result_artifact_id
            != job.reused_result_artifact_id
        ):
            raise StudyAggregationError(
                "REUSED result-bearing Trial "
                "source attempt does not match reused result"
            )

        return job.reused_result_artifact_id

    def _load_result_payload(
        self,
        artifact_id: str,
    ) -> dict:
        artifact = (
            self.catalog_store
            .load_artifact(
                artifact_id
            )
        )

        if (
            artifact is None
            or artifact.artifact_kind
            is not ResearchArtifactKind.BACKTEST_RESULT
            or artifact.schema_id
            != BACKTEST_RESULT_SCHEMA
        ):
            raise StudyAggregationError(
                "result-bearing Trial requires "
                "canonical Backtest result artifact"
            )

        try:
            raw = self.artifact_store.load_bytes(
                artifact_id
            )

            payload = decode_canonical_bytes(
                raw,
                schema=BACKTEST_RESULT_SCHEMA,
            )
        except Exception as error:
            raise StudyAggregationError(
                "canonical Backtest result artifact "
                "could not be verified and decoded"
            ) from error

        if (
            not isinstance(payload, dict)
            or set(payload)
            != {
                "trades",
                "bar_records",
                "equity_curve",
            }
            or not isinstance(
                payload["trades"],
                list,
            )
            or not isinstance(
                payload["bar_records"],
                list,
            )
            or not isinstance(
                payload["equity_curve"],
                list,
            )
        ):
            raise StudyAggregationError(
                "canonical Backtest result payload "
                "has an invalid shape"
            )

        return payload

    @staticmethod
    def _financial_metrics(
        payload: dict,
    ) -> tuple[float, float]:
        bar_records = payload["bar_records"]
        equity_curve = payload["equity_curve"]
        trades = payload["trades"]

        if not bar_records:
            if trades:
                raise StudyAggregationError(
                    "Backtest trades require "
                    "authoritative equity records"
                )

            if equity_curve:
                raise StudyAggregationError(
                    "Backtest equity curve must be derived "
                    "from authoritative bar records"
                )

            return 0.0, 0.0

        equity_values = []

        for index, record in enumerate(
            bar_records
        ):
            if (
                not isinstance(record, dict)
                or "equity" not in record
            ):
                raise StudyAggregationError(
                    "Backtest bar record at index "
                    f"{index} lacks authoritative equity"
                )

            try:
                equity = float(
                    record["equity"]
                )
            except (
                TypeError,
                ValueError,
            ) as error:
                raise StudyAggregationError(
                    "Backtest equity at index "
                    f"{index} must be finite"
                ) from error

            if not isfinite(equity):
                raise StudyAggregationError(
                    "Backtest equity at index "
                    f"{index} must be finite"
                )

            equity_values.append(equity)

        if equity_values[0] <= 0.0:
            raise StudyAggregationError(
                "Backtest starting equity must be "
                "strictly positive"
            )

        if len(equity_curve) != len(
            equity_values
        ):
            raise StudyAggregationError(
                "Backtest equity curve does not match "
                "authoritative bar records"
            )

        for index, (
            point,
            expected_equity,
        ) in enumerate(
            zip(
                equity_curve,
                equity_values,
            )
        ):
            if (
                not isinstance(point, tuple)
                or len(point) != 2
            ):
                raise StudyAggregationError(
                    "Backtest equity curve point "
                    f"{index} is invalid"
                )

            try:
                curve_equity = float(
                    point[1]
                )
            except (
                TypeError,
                ValueError,
            ) as error:
                raise StudyAggregationError(
                    "Backtest equity curve point "
                    f"{index} is invalid"
                ) from error

            if (
                not isfinite(curve_equity)
                or curve_equity
                != expected_equity
            ):
                raise StudyAggregationError(
                    "Backtest equity curve does not match "
                    "authoritative bar records"
                )

        starting_equity = equity_values[0]
        ending_equity = equity_values[-1]

        account_return_pct = (
            (
                ending_equity
                - starting_equity
            )
            / starting_equity
            * 100.0
        )

        max_drawdown_pct = (
            PerformanceMetrics
            ._max_equity_drawdown(
                equity_values
            )
        )

        return (
            account_return_pct,
            max_drawdown_pct,
        )

    def aggregate_revision(
        self,
        study_revision_id: str,
    ) -> StudyAggregationResult:
        if (
            not isinstance(
                study_revision_id,
                str,
            )
            or not study_revision_id
        ):
            raise ValueError(
                "study_revision_id must be "
                "a non-empty string"
            )

        revision = (
            self.catalog_store
            .load_study_revision(
                study_revision_id
            )
        )

        if revision is None:
            raise StudyAggregationError(
                "StudyRevision does not exist"
            )

        trials = tuple(
            self.catalog_store
            .list_trials_for_revision(
                study_revision_id
            )
        )

        counts = {
            disposition: 0
            for disposition in TrialDisposition
        }

        returns = []
        drawdowns = []
        artifact_ids = []

        for trial in trials:
            counts[
                trial.disposition
            ] += 1

            if not self._result_bearing_disposition(
                trial.disposition
            ):
                continue

            artifact_id = (
                self._resolve_result_artifact_id(
                    trial
                )
            )

            payload = self._load_result_payload(
                artifact_id
            )

            (
                account_return_pct,
                max_drawdown_pct,
            ) = self._financial_metrics(
                payload
            )

            artifact_ids.append(
                artifact_id
            )
            returns.append(
                account_return_pct
            )
            drawdowns.append(
                max_drawdown_pct
            )

        total_registered = len(trials)
        result_bearing = (
            counts[
                TrialDisposition.EXECUTED
            ]
            + counts[
                TrialDisposition.REUSED
            ]
        )

        if len(artifact_ids) != result_bearing:
            raise StudyAggregationError(
                "result-bearing Trial denominator "
                "does not match resolved results"
            )

        return StudyAggregationResult(
            study_revision_id=(
                study_revision_id
            ),
            aggregation_basis=(
                AGGREGATION_BASIS
            ),
            total_registered_trials=(
                total_registered
            ),
            result_bearing_trials=(
                result_bearing
            ),
            excluded_trials=(
                total_registered
                - result_bearing
            ),
            pending_trials=counts[
                TrialDisposition.PENDING
            ],
            executed_trials=counts[
                TrialDisposition.EXECUTED
            ],
            reused_trials=counts[
                TrialDisposition.REUSED
            ],
            invalid_trials=counts[
                TrialDisposition.INVALID
            ],
            insufficient_trials=counts[
                TrialDisposition.INSUFFICIENT
            ],
            failed_trials=counts[
                TrialDisposition.FAILED
            ],
            cancelled_trials=counts[
                TrialDisposition.CANCELLED
            ],
            interrupted_trials=counts[
                TrialDisposition.INTERRUPTED
            ],
            account_return_pct=(
                StudyMetricDistribution
                .from_values(
                    returns
                )
            ),
            max_equity_drawdown_pct=(
                StudyMetricDistribution
                .from_values(
                    drawdowns
                )
            ),
            result_artifact_ids=tuple(
                artifact_ids
            ),
        )
