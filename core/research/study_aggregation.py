from dataclasses import dataclass
from fractions import Fraction
from math import fsum, isfinite
from statistics import median

from core.backtest.performance_metrics import (
    PerformanceMetrics,
)
from core.research.models.registered_study import (
    ResearchJobCompletionKind,
    ResearchJobState,
    StudyRevision,
    Trial,
    TrialDisposition,
)
from core.research.models.research_catalog import (
    ResearchArtifactKind,
    RunAttemptState,
)
from core.research.models.research_evidence import (
    ResearchEvidenceStatus,
)
from core.research.research_artifact_store import (
    research_artifact_reference,
)
from core.research.reproducibility import (
    BACKTEST_RESULT_SCHEMA,
    decode_stable_backtest_result_bytes,
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

        # Keep the accurate fast path for ordinary inputs.
        # On intermediate overflow, preserve the exact
        # binary-float sum before dividing and rounding once.
        # Scaling individual inputs can lose subnormal
        # remainders or overflow a representable average.
        try:
            try:
                mean_value = fsum(values) / count
            except OverflowError:
                exact_total = sum(
                    (
                        Fraction.from_float(value)
                        for value in values
                    ),
                    start=Fraction(0),
                )
                mean_value = float(exact_total / count)

            median_value = float(median(values))
            if not isfinite(median_value) and count % 2 == 0:
                ordered = sorted(values)
                lower = ordered[count // 2 - 1]
                upper = ordered[count // 2]
                median_value = fsum(
                    (lower / 2.0, upper / 2.0)
                )
        except (OverflowError, ValueError) as exc:
            raise StudyAggregationError(
                "aggregate metric statistics cannot "
                "be represented as finite values"
            ) from exc

        if (
            not isfinite(mean_value)
            or not isfinite(median_value)
        ):
            raise StudyAggregationError(
                "aggregate metric statistics must be finite"
            )

        return cls(
            count=count,
            mean=mean_value,
            median=median_value,
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
        evidence_store=None,
    ):
        self.catalog_store = catalog_store
        self.artifact_store = artifact_store
        self.evidence_store = evidence_store

    def _authoritative_evidence_store(self):
        database_path = getattr(
            self.catalog_store,
            "database_path",
            None,
        )

        if database_path is not None:
            try:
                from core.research.sqlite_research_evidence_store import (
                    SQLiteResearchEvidenceStore,
                )

                # A canonical persisted Trial derives evidence authority
                # exclusively from the catalog's own research database.
                # An injected foreign store must never override it.
                return SQLiteResearchEvidenceStore(
                    database_path
                )
            except Exception as error:
                raise StudyAggregationError(
                    "authoritative ResearchEvidence store "
                    "could not be opened from catalog database"
                ) from error

        # Lightweight/noncanonical projection callers have no durable
        # catalog database. Preserve their explicit evidence dependency.
        if self.evidence_store is not None:
            return self.evidence_store

        raise StudyAggregationError(
            "canonical result-bearing Trial requires "
            "authoritative ResearchEvidence store"
        )

    def _validate_selected_result_evidence(
        self,
        *,
        attempt,
        result_artifact_id: str,
    ) -> None:
        evidence_id = getattr(
            attempt,
            "evidence_id",
            None,
        )

        experiment_spec_id = getattr(
            attempt,
            "experiment_spec_id",
            None,
        )

        if (
            evidence_id is None
            or experiment_spec_id is None
        ):
            raise StudyAggregationError(
                "result-bearing RunAttempt requires "
                "authoritative ResearchEvidence lineage"
            )

        spec = (
            self.catalog_store
            .load_experiment_spec(
                experiment_spec_id
            )
        )

        if spec is None:
            raise StudyAggregationError(
                "result-bearing RunAttempt "
                "ExperimentSpec does not exist"
            )

        result_artifact = (
            self.catalog_store
            .load_artifact(
                result_artifact_id
            )
        )

        manifest_artifact = (
            self.catalog_store
            .load_artifact(
                spec.manifest_artifact_id
            )
        )

        from core.research.reproducibility import (
            BACKTEST_RUN_MANIFEST_SCHEMA,
        )

        if (
            result_artifact is None
            or result_artifact.artifact_kind
            is not ResearchArtifactKind.BACKTEST_RESULT
            or result_artifact.schema_id
            != BACKTEST_RESULT_SCHEMA
        ):
            raise StudyAggregationError(
                "ResearchEvidence result authority "
                "requires canonical Backtest result artifact"
            )

        if (
            manifest_artifact is None
            or manifest_artifact.artifact_kind
            is not ResearchArtifactKind.BACKTEST_RUN_MANIFEST
            or manifest_artifact.schema_id
            != BACKTEST_RUN_MANIFEST_SCHEMA
        ):
            raise StudyAggregationError(
                "ResearchEvidence result authority "
                "requires canonical Backtest run manifest"
            )

        try:
            evidence = (
                self._authoritative_evidence_store()
                .load(
                    evidence_id
                )
            )
        except StudyAggregationError:
            raise
        except Exception as error:
            raise StudyAggregationError(
                "authoritative ResearchEvidence "
                "could not be loaded"
            ) from error

        if (
            evidence is None
            or evidence.evidence_id
            != evidence_id
            or evidence.status
            is not ResearchEvidenceStatus.ACCEPTED
        ):
            raise StudyAggregationError(
                "selected result requires actual "
                "ACCEPTED ResearchEvidence"
            )

        if (
            evidence.dataset_fingerprint
            != spec.dataset_fingerprint
            or evidence.configuration_fingerprint
            != spec.configuration_fingerprint
            or evidence.repository_revision
            != spec.repository_revision
        ):
            raise StudyAggregationError(
                "selected result ResearchEvidence "
                "does not match ExperimentSpec identity"
            )

        if (
            evidence.result_fingerprint
            != result_artifact.artifact_id
        ):
            raise StudyAggregationError(
                "selected result artifact does not match "
                "accepted ResearchEvidence result fingerprint"
            )

        manifest_reference = (
            research_artifact_reference(
                manifest_artifact.artifact_id
            )
        )

        result_reference = (
            research_artifact_reference(
                result_artifact.artifact_id
            )
        )

        if (
            manifest_reference
            not in evidence.artifact_references
            or result_reference
            not in evidence.artifact_references
        ):
            raise StudyAggregationError(
                "selected result requires accepted "
                "ResearchEvidence manifest/result references"
            )

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

            if (
                isinstance(trial, Trial)
                and attempt.experiment_spec_id
                != trial.experiment_spec_id
            ):
                raise StudyAggregationError(
                    "EXECUTED result-bearing Trial "
                    "RunAttempt ExperimentSpec lineage "
                    "does not match Trial binding"
                )

            if isinstance(trial, Trial):
                self._validate_selected_result_evidence(
                    attempt=attempt,
                    result_artifact_id=(
                        attempt.result_artifact_id
                    ),
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
            or source_attempt.evidence_id is None
            or job.reused_evidence_id
            != source_attempt.evidence_id
            or source_attempt.result_artifact_id
            != job.reused_result_artifact_id
        ):
            raise StudyAggregationError(
                "REUSED result-bearing Trial "
                "source attempt evidence/result lineage "
                "does not match reused sources"
            )

        if (
            isinstance(trial, Trial)
            and source_attempt.experiment_spec_id
            != trial.experiment_spec_id
        ):
            raise StudyAggregationError(
                "REUSED result-bearing Trial "
                "source RunAttempt ExperimentSpec lineage "
                "does not match Trial binding"
            )

        if isinstance(trial, Trial):
            self._validate_selected_result_evidence(
                attempt=source_attempt,
                result_artifact_id=(
                    job.reused_result_artifact_id
                ),
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

            return decode_stable_backtest_result_bytes(
                raw
            )
        except Exception as error:
            raise StudyAggregationError(
                "canonical Backtest result artifact "
                "could not be verified and decoded"
            ) from error

    def _validate_result_manifest_capital(
        self,
        trial: Trial,
        payload: dict,
    ) -> None:
        from core.research.reproducibility import (
            BACKTEST_RUN_MANIFEST_SCHEMA,
            decode_canonical_bytes,
            validate_backtest_result_manifest_capital_binding,
        )

        # Durable catalog values are canonical Trial objects and
        # carry immutable ExperimentSpec lineage. Lightweight
        # aggregation projections without that durable model
        # cannot prove or contradict cross-artifact capital
        # authority, so retain their historical aggregation
        # semantics. Canonical Trials remain fail-closed below.
        if not isinstance(trial, Trial):
            return

        if trial.experiment_spec_id is None:
            raise StudyAggregationError(
                "result-bearing Trial requires "
                "authoritative ExperimentSpec lineage"
            )

        spec = self.catalog_store.load_experiment_spec(
            trial.experiment_spec_id
        )

        if spec is None:
            raise StudyAggregationError(
                "result-bearing Trial ExperimentSpec "
                "does not exist"
            )

        manifest_artifact = (
            self.catalog_store.load_artifact(
                spec.manifest_artifact_id
            )
        )

        if (
            manifest_artifact is None
            or manifest_artifact.artifact_kind
            is not ResearchArtifactKind.BACKTEST_RUN_MANIFEST
            or manifest_artifact.schema_id
            != BACKTEST_RUN_MANIFEST_SCHEMA
        ):
            raise StudyAggregationError(
                "result-bearing Trial requires canonical "
                "Backtest run manifest artifact"
            )

        try:
            raw_manifest = (
                self.artifact_store.load_bytes(
                    manifest_artifact.artifact_id
                )
            )

            if (
                len(raw_manifest)
                != manifest_artifact.byte_count
            ):
                raise ValueError(
                    "manifest byte count mismatch"
                )

            manifest = decode_canonical_bytes(
                raw_manifest,
                schema=BACKTEST_RUN_MANIFEST_SCHEMA,
            )

            validate_backtest_result_manifest_capital_binding(
                payload,
                manifest,
            )
        except Exception as error:
            raise StudyAggregationError(
                "Backtest result does not match "
                "authoritative run manifest capital"
            ) from error

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

        if isinstance(revision, StudyRevision):
            validator = getattr(
                self.catalog_store,
                "validate_study_revision_population",
                None,
            )

            if not callable(validator):
                raise StudyAggregationError(
                    "canonical StudyRevision aggregation "
                    "requires registered Trial "
                    "population-proof validation"
                )

            try:
                validator(
                    study_revision_id,
                    tuple(
                        trial.trial_id
                        for trial in trials
                    ),
                )
            except Exception as error:
                raise StudyAggregationError(
                    "StudyRevision registered Trial "
                    "population proof does not match "
                    "persisted Trial denominator"
                ) from error

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

            self._validate_result_manifest_capital(
                trial,
                payload,
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
