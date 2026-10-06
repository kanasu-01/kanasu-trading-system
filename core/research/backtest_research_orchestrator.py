"""Reusable Backtest execution and research evidence orchestration.

M9.4d1 BEHAVIOR IMPACT: ADDED
PRIMARY BEHAVIOR IDS: RESEARCH-RULE-014, RESEARCH-RULE-015
PRESERVED BEHAVIOR IDS: RESEARCH-RULE-001, RESEARCH-RULE-009,
RESEARCH-RULE-010

M9.4d1 exposes exact research specification preparation as a reusable
phase before any new RunAttempt is created. Existing execute() callers
retain the same authoritative Backtest financial execution and evidence
behavior.
"""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from uuid import uuid4

from core.backtest.backtest_result import BacktestResult
from core.config.backtest_config import BacktestConfig
from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange
from core.market_data.historical_source import HistoricalSource
from core.research.models.research_catalog import (
    ComputationKind,
    ResearchArtifact,
    ResearchArtifactKind,
    RunAttempt,
    RunAttemptState,
)
from core.research.models.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceStatus,
)
from core.research.reproducibility import (
    backtest_configuration_fingerprint_v2,
    backtest_run_manifest_bytes,
    build_backtest_run_manifest,
    dataset_fingerprint,
    decode_stable_backtest_result_bytes,
    stable_backtest_result_fingerprint,
    BACKTEST_RESULT_SCHEMA,
    BACKTEST_RUN_MANIFEST_SCHEMA,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
    research_artifact_reference,
)
from core.research.software_identity import (
    SoftwareIdentity,
    SoftwareIdentityProvider,
)
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)
from core.research.sqlite_research_evidence_store import (
    SQLiteResearchEvidenceStore,
)
from core.runtime.backtest_runtime import (
    execute_backtest_candles,
    retrieve_backtest_candles,
)
from core.runtime.backtest_runtime import (
    DeterministicBacktestComputationError,
    TransientBacktestOperationalError,
)
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.strategies.base_strategy import BaseStrategy


Clock = Callable[[], datetime]
EvidenceIdFactory = Callable[[], str]
RetrieveCandles = Callable[..., list[Candle]]
ExecuteCandles = Callable[..., BacktestResult]
AttemptTerminalizer = Callable[..., RunAttempt]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_evidence_id() -> str:
    return f"evidence-{uuid4().hex}"


@dataclass(frozen=True)
class PreparedResearchRetrieval:
    """
    One already-prepared candle sequence plus durable research references.

    The candles list is deliberately preserved as the exact object used
    by the existing V1 fingerprint and Backtest execution path.
    """

    candles: list[Candle]
    artifact_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.candles, list):
            raise TypeError(
                "candles must be a list"
            )

        if any(
            not isinstance(candle, Candle)
            for candle in self.candles
        ):
            raise TypeError(
                "candles must contain Candle values"
            )

        if not isinstance(
            self.artifact_references,
            tuple,
        ):
            raise TypeError(
                "artifact_references must be a tuple"
            )

        if any(
            not isinstance(value, str)
            or not value
            for value in self.artifact_references
        ):
            raise ValueError(
                "artifact_references must contain "
                "non-empty strings"
            )

        if (
            len(set(self.artifact_references))
            != len(self.artifact_references)
        ):
            raise ValueError(
                "artifact_references contains duplicates"
            )


class PreparedResearchSpecificationError(RuntimeError):
    """
    Prepared retrieval succeeded, but its research specification
    material could not be prepared.

    The original operational exception is retained so callers continue
    to observe its original type and message.
    """

    def __init__(
        self,
        original_error: Exception,
    ):
        if not isinstance(
            original_error,
            Exception,
        ):
            raise TypeError(
                "original_error must be an Exception"
            )

        self.original_error = original_error

        message = str(
            original_error
        )

        if not message:
            message = type(
                original_error
            ).__name__

        super().__init__(
            message
        )


class AuthoritativeResearchStateError(RuntimeError):
    """
    Authoritative research persistence/integrity state could not be
    durably established.

    This is not an ordinary independent Trial outcome. Callers must
    propagate it to the scheduler fail-closed boundary so no new job is
    claimed by the affected worker-pool run.
    """

    def __init__(
        self,
        original_error: Exception,
    ):
        if not isinstance(
            original_error,
            Exception,
        ):
            raise TypeError(
                "original_error must be an Exception"
            )

        self.original_error = original_error

        message = str(original_error)

        if not message:
            message = type(
                original_error
            ).__name__

        super().__init__(message)


@dataclass(frozen=True)
class PreparedBacktestResearchSpecification:
    """
    Exact material prepared before a physical RunAttempt is created.

    Preparation retains the retrieved candle values used for canonical
    identity. Immediately before final identity validation,
    execute_prepared() creates a private value-identical candle snapshot;
    that exact private sequence is then consumed by financial execution.
    """

    candles: list[Candle]
    requested_range: TimeRange
    identity: SoftwareIdentity
    dataset_fingerprint: str
    configuration_fingerprint: str
    manifest_artifact_id: str
    manifest_reference: str
    retrieval_artifact_references: tuple[str, ...] = ()
    experiment_spec_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.candles,
            list,
        ):
            raise TypeError(
                "candles must be a list"
            )

        if any(
            not isinstance(value, Candle)
            for value in self.candles
        ):
            raise TypeError(
                "candles must contain Candle values"
            )

        if not isinstance(
            self.requested_range,
            TimeRange,
        ):
            raise TypeError(
                "requested_range must be a TimeRange"
            )

        if not isinstance(
            self.identity,
            SoftwareIdentity,
        ):
            raise TypeError(
                "identity must be a SoftwareIdentity"
            )

        for field_name in (
            "dataset_fingerprint",
            "configuration_fingerprint",
            "manifest_artifact_id",
        ):
            value = getattr(
                self,
                field_name,
            )

            if (
                not isinstance(value, str)
                or not value.startswith("sha256:")
            ):
                raise ValueError(
                    f"{field_name} must be a SHA-256 identity"
                )

        if (
            not isinstance(
                self.manifest_reference,
                str,
            )
            or not self.manifest_reference
        ):
            raise ValueError(
                "manifest_reference must be a non-empty string"
            )

        if not isinstance(
            self.retrieval_artifact_references,
            tuple,
        ):
            raise TypeError(
                "retrieval_artifact_references must be a tuple"
            )

        if any(
            not isinstance(value, str)
            or not value
            for value
            in self.retrieval_artifact_references
        ):
            raise ValueError(
                "retrieval artifact references must be "
                "non-empty strings"
            )

        if self.identity.is_exact:
            if (
                not isinstance(
                    self.experiment_spec_id,
                    str,
                )
                or not self.experiment_spec_id.startswith(
                    "sha256:"
                )
            ):
                raise ValueError(
                    "exact software identity requires "
                    "experiment_spec_id"
                )

        elif self.experiment_spec_id is not None:
            raise ValueError(
                "non-exact software identity cannot carry "
                "experiment_spec_id"
            )


@dataclass(frozen=True)
class ReusableBacktestResearchExecution:
    attempt: RunAttempt
    evidence: ResearchEvidence
    result_artifact: ResearchArtifact


@dataclass(frozen=True)
class BacktestResearchExecution:
    result: BacktestResult
    attempt_id: str | None
    evidence_id: str
    evidence_status: ResearchEvidenceStatus


class BacktestResearchOrchestrator:
    """Compose canonical Backtest execution with durable M9.2 lineage."""

    def __init__(
        self,
        *,
        catalog_store: SQLiteResearchCatalogStore,
        evidence_store: SQLiteResearchEvidenceStore,
        artifact_store: ContentAddressedResearchArtifactStore,
        software_identity_provider: SoftwareIdentityProvider,
        evidence_id_factory: EvidenceIdFactory | None = None,
        clock: Clock | None = None,
        retrieve_candles: RetrieveCandles = retrieve_backtest_candles,
        execute_candles: ExecuteCandles = execute_backtest_candles,
    ):
        self.catalog_store = catalog_store
        self.evidence_store = evidence_store
        self.artifact_store = artifact_store
        self.software_identity_provider = software_identity_provider
        self._evidence_id_factory = (
            evidence_id_factory or _new_evidence_id
        )
        self._clock = clock or _utc_now
        self._retrieve_candles = retrieve_candles
        self._execute_candles = execute_candles

    def _software_identity(self) -> SoftwareIdentity:
        try:
            return self.software_identity_provider.resolve()
        except Exception:
            return SoftwareIdentity(
                repository_revision=None,
                worktree_clean=None,
            )

    @staticmethod
    def _software_state(identity: SoftwareIdentity) -> str:
        if identity.is_exact:
            return "exact"

        if (
            identity.repository_revision is not None
            and identity.worktree_clean is False
        ):
            return "dirty"

        return "unknown"

    def _evidence(
        self,
        *,
        status: ResearchEvidenceStatus,
        dataset_context: DatasetContext,
        requested_range: TimeRange,
        identity: SoftwareIdentity,
        summary: str,
        dataset_fingerprint_value: str | None = None,
        configuration_fingerprint: str | None = None,
        result_fingerprint: str | None = None,
        artifact_references: tuple[str, ...] = (),
        persist: bool = True,
    ) -> ResearchEvidence:
        provenance = {
            "computation_kind": ComputationKind.BACKTEST.value,
            "software_identity_state": self._software_state(
                identity
            ),
        }

        if (
            identity.repository_revision is not None
            and not identity.is_exact
        ):
            provenance["observed_repository_revision"] = (
                identity.repository_revision
            )

        record = ResearchEvidence(
            evidence_id=self._evidence_id_factory(),
            created_at=self._clock(),
            status=status,
            dataset_context=dataset_context,
            requested_range=requested_range,
            dataset_fingerprint=dataset_fingerprint_value,
            configuration_fingerprint=configuration_fingerprint,
            result_fingerprint=result_fingerprint,
            provenance=provenance,
            repository_revision=(
                identity.repository_revision
                if identity.is_exact
                else None
            ),
            summary=summary,
            artifact_references=artifact_references,
        )

        if persist:
            self.evidence_store.save(record)

        return record

    def _try_pre_spec_evidence(
        self,
        *,
        dataset_context: DatasetContext,
        requested_range: TimeRange,
        identity: SoftwareIdentity,
        summary: str,
        dataset_fingerprint_value: str | None = None,
        configuration_fingerprint: str | None = None,
        artifact_references: tuple[str, ...] = (),
    ) -> None:
        try:
            self._evidence(
                status=ResearchEvidenceStatus.INCOMPLETE,
                dataset_context=dataset_context,
                requested_range=requested_range,
                identity=identity,
                summary=summary,
                dataset_fingerprint_value=dataset_fingerprint_value,
                configuration_fingerprint=configuration_fingerprint,
                artifact_references=artifact_references,
            )
        except Exception:
            # Pre-specification evidence is best-effort and must not
            # replace the operational error that prevented execution.
            return

    @staticmethod
    def _failure_message(error: Exception) -> str:
        message = str(error)
        if not message:
            message = type(error).__name__
        return message[:1000]

    @staticmethod
    def _semantic_failure_classification(
        error: Exception,
    ) -> str:
        if isinstance(
            error,
            DeterministicBacktestComputationError,
        ):
            return "deterministic_compute_failure"

        if isinstance(
            error,
            TransientBacktestOperationalError,
        ):
            return "transient_operational_failure"

        return "unknown_failure"

    @classmethod
    def _semantic_failure_message(
        cls,
        error: Exception,
    ) -> str:
        original = getattr(
            error,
            "original_error",
            error,
        )
        return cls._failure_message(original)

    def prepare_specification(
        self,
        *,
        historical_source: HistoricalSource | None,
        strategy: BaseStrategy,
        config: BacktestConfig,
        runtime_context: RuntimeContext,
        dataset_context: DatasetContext,
        prepared_retrieval: (
            Callable[[], PreparedResearchRetrieval]
            | None
        ) = None,
    ) -> PreparedBacktestResearchSpecification:
        """
        Prepare deterministic Backtest research identity without
        creating a physical RunAttempt or executing financial logic.
        """

        identity = self._software_identity()

        requested_range = TimeRange(
            config.start,
            config.end,
        )

        retrieval_artifact_references: tuple[
            str,
            ...,
        ] = ()

        try:
            if prepared_retrieval is None:
                if historical_source is None:
                    raise ValueError(
                        "historical_source is required "
                        "without prepared_retrieval"
                    )

                candles = self._retrieve_candles(
                    historical_source=historical_source,
                    config=config,
                    dataset_context=dataset_context,
                )

            else:
                prepared = prepared_retrieval()

                if not isinstance(
                    prepared,
                    PreparedResearchRetrieval,
                ):
                    raise TypeError(
                        "prepared_retrieval must return "
                        "PreparedResearchRetrieval"
                    )

                candles = prepared.candles

                retrieval_artifact_references = (
                    prepared.artifact_references
                )

        except AuthoritativeResearchStateError:
            # Authoritative persistence/integrity failure is not an
            # ordinary Trial-specific preparation outcome.
            raise
        except PreparedResearchSpecificationError as error:
            original_error = error.original_error

            self._try_pre_spec_evidence(
                dataset_context=dataset_context,
                requested_range=requested_range,
                identity=identity,
                summary=(
                    "research_specification_preparation_failed: "
                    + self._failure_message(
                        original_error
                    )
                ),
            )

            raise original_error

        except Exception as error:
            self._try_pre_spec_evidence(
                dataset_context=dataset_context,
                requested_range=requested_range,
                identity=identity,
                summary=(
                    "historical_data_retrieval_failed: "
                    + self._failure_message(
                        error
                    )
                ),
            )

            raise

        dataset_fp = None
        configuration_fp = None
        manifest_reference = None

        try:
            dataset_fp = dataset_fingerprint(
                dataset_context,
                requested_range,
                candles,
            )

            manifest = build_backtest_run_manifest(
                dataset_context,
                requested_range,
                dataset_fp,
                strategy,
                initial_capital=config.initial_capital,
                runtime_context=runtime_context,
            )

            try:
                manifest_artifact = (
                    self.artifact_store
                    .persist_backtest_manifest(
                        manifest,
                        created_at=self._clock(),
                    )
                )

                manifest_artifact = (
                    self.catalog_store.save_artifact(
                        manifest_artifact
                    )
                )
            except Exception as error:
                raise AuthoritativeResearchStateError(
                    error
                ) from error

            manifest_reference = (
                research_artifact_reference(
                    manifest_artifact.artifact_id
                )
            )

            configuration_fp = (
                backtest_configuration_fingerprint_v2(
                    manifest
                )
            )

        except AuthoritativeResearchStateError:
            # Authoritative persistence/integrity failure must reach
            # the scheduler unchanged and must not be represented as
            # an ordinary incomplete research outcome.
            raise
        except Exception as error:
            self._try_pre_spec_evidence(
                dataset_context=dataset_context,
                requested_range=requested_range,
                identity=identity,
                summary=(
                    "research_specification_preparation_failed: "
                    + self._failure_message(
                        error
                    )
                ),
                dataset_fingerprint_value=(
                    dataset_fp
                ),
                configuration_fingerprint=(
                    configuration_fp
                ),
                artifact_references=(
                    retrieval_artifact_references
                    + (
                        (manifest_reference,)
                        if manifest_reference
                        is not None
                        else ()
                    )
                ),
            )

            raise

        experiment_spec_id = None

        if identity.is_exact:
            try:
                spec = (
                    self.catalog_store
                    .resolve_experiment_spec(
                        computation_kind=(
                            ComputationKind.BACKTEST
                        ),
                        manifest_artifact_id=(
                            manifest_artifact.artifact_id
                        ),
                        dataset_fingerprint=(
                            dataset_fp
                        ),
                        configuration_fingerprint=(
                            configuration_fp
                        ),
                        repository_revision=(
                            identity.repository_revision
                        ),
                        created_at=self._clock(),
                    )
                )
            except Exception as error:
                raise AuthoritativeResearchStateError(
                    error
                ) from error

            experiment_spec_id = (
                spec.experiment_spec_id
            )

        return PreparedBacktestResearchSpecification(
            candles=candles,
            requested_range=requested_range,
            identity=identity,
            dataset_fingerprint=dataset_fp,
            configuration_fingerprint=(
                configuration_fp
            ),
            manifest_artifact_id=(
                manifest_artifact.artifact_id
            ),
            manifest_reference=(
                manifest_reference
            ),
            retrieval_artifact_references=(
                retrieval_artifact_references
            ),
            experiment_spec_id=(
                experiment_spec_id
            ),
        )

    def find_exact_reusable_execution(
        self,
        experiment_spec_id: str,
    ) -> ReusableBacktestResearchExecution | None:
        """Resolve only fully verified exact accepted historical evidence."""

        spec = self.catalog_store.load_experiment_spec(
            experiment_spec_id
        )
        if spec is None:
            raise ValueError(
                f"ExperimentSpec does not exist: {experiment_spec_id}"
            )

        candidates = (
            self.catalog_store
            .list_succeeded_attempts_for_experiment_spec(
                experiment_spec_id
            )
        )

        for attempt in candidates:
            if (
                attempt.evidence_id is None
                or attempt.result_artifact_id is None
            ):
                continue

            evidence = self.evidence_store.load(
                attempt.evidence_id
            )
            artifact = self.catalog_store.load_artifact(
                attempt.result_artifact_id
            )
            manifest_artifact = (
                self.catalog_store.load_artifact(
                    spec.manifest_artifact_id
                )
            )

            if (
                evidence is None
                or artifact is None
                or manifest_artifact is None
            ):
                continue
            if evidence.status is not ResearchEvidenceStatus.ACCEPTED:
                continue
            if (
                manifest_artifact.artifact_kind
                is not ResearchArtifactKind.BACKTEST_RUN_MANIFEST
                or manifest_artifact.schema_id
                != BACKTEST_RUN_MANIFEST_SCHEMA
            ):
                continue
            if artifact.artifact_kind is not ResearchArtifactKind.BACKTEST_RESULT:
                continue
            if artifact.schema_id != BACKTEST_RESULT_SCHEMA:
                continue
            if evidence.dataset_fingerprint != spec.dataset_fingerprint:
                continue
            if evidence.configuration_fingerprint != spec.configuration_fingerprint:
                continue
            if evidence.repository_revision != spec.repository_revision:
                continue
            if evidence.result_fingerprint != artifact.artifact_id:
                continue
            if (
                research_artifact_reference(
                    manifest_artifact.artifact_id
                )
                not in evidence.artifact_references
            ):
                continue
            if (
                research_artifact_reference(artifact.artifact_id)
                not in evidence.artifact_references
            ):
                continue

            try:
                manifest_payload = (
                    self.artifact_store.load_bytes(
                        manifest_artifact.artifact_id
                    )
                )
                payload = self.artifact_store.load_bytes(
                    artifact.artifact_id
                )
            except (FileNotFoundError, RuntimeError):
                continue

            if (
                len(manifest_payload)
                != manifest_artifact.byte_count
                or len(payload) != artifact.byte_count
            ):
                continue

            try:
                decode_stable_backtest_result_bytes(
                    payload
                )
            except (TypeError, ValueError):
                continue

            return ReusableBacktestResearchExecution(
                attempt=attempt,
                evidence=evidence,
                result_artifact=artifact,
            )

        return None

    def _validate_prepared_execution_identity(
        self,
        *,
        prepared: PreparedBacktestResearchSpecification,
        strategy: BaseStrategy,
        config: BacktestConfig,
        runtime_context: RuntimeContext,
        dataset_context: DatasetContext,
    ) -> None:
        """
        Prove that the exact inputs about to execute still match
        the canonical research identity prepared earlier.

        M9.4g1 intentionally reuses the existing M4/M9 canonical
        dataset fingerprint and Backtest run-manifest authorities.
        """

        execution_range = TimeRange(
            config.start,
            config.end,
        )

        if execution_range != prepared.requested_range:
            raise ValueError(
                "prepared execution identity mismatch: "
                "requested range changed"
            )

        execution_dataset_fingerprint = (
            dataset_fingerprint(
                dataset_context,
                execution_range,
                prepared.candles,
            )
        )

        if (
            execution_dataset_fingerprint
            != prepared.dataset_fingerprint
        ):
            raise ValueError(
                "prepared execution identity mismatch: "
                "dataset inputs changed"
            )

        execution_manifest = (
            build_backtest_run_manifest(
                dataset_context,
                execution_range,
                execution_dataset_fingerprint,
                strategy,
                initial_capital=(
                    config.initial_capital
                ),
                runtime_context=runtime_context,
            )
        )

        execution_configuration_fingerprint = (
            backtest_configuration_fingerprint_v2(
                execution_manifest
            )
        )

        if (
            execution_configuration_fingerprint
            != prepared.configuration_fingerprint
        ):
            raise ValueError(
                "prepared execution identity mismatch: "
                "Backtest configuration changed"
            )

        expected_manifest_reference = (
            research_artifact_reference(
                prepared.manifest_artifact_id
            )
        )

        if (
            expected_manifest_reference
            != prepared.manifest_reference
        ):
            raise ValueError(
                "prepared execution identity mismatch: "
                "manifest reference changed"
            )

        try:
            prepared_manifest_bytes = (
                self.artifact_store.load_bytes(
                    prepared.manifest_artifact_id
                )
            )
        except (
            OSError,
            RuntimeError,
        ) as error:
            raise AuthoritativeResearchStateError(
                RuntimeError(
                    "prepared execution identity mismatch: "
                    "manifest artifact is unavailable or corrupt"
                )
            ) from error

        execution_manifest_bytes = (
            backtest_run_manifest_bytes(
                execution_manifest
            )
        )

        if (
            execution_manifest_bytes
            != prepared_manifest_bytes
        ):
            raise ValueError(
                "prepared execution identity mismatch: "
                "manifest does not describe execution inputs"
            )
    def execute_prepared(
        self,
        *,
        prepared: PreparedBacktestResearchSpecification,
        strategy: BaseStrategy,
        config: BacktestConfig,
        runtime_context: RuntimeContext,
        dataset_context: DatasetContext,
        attempt: RunAttempt | None = None,
        attempt_terminalizer: AttemptTerminalizer | None = None,
    ) -> BacktestResearchExecution:
        """
        Execute one already-prepared Backtest specification.

        M9.4 may supply the RUNNING RunAttempt already linked to its
        ResearchJob. Existing callers may omit it and retain the
        established attempt-creation behavior.
        """

        if not isinstance(
            prepared,
            PreparedBacktestResearchSpecification,
        ):
            raise TypeError(
                "prepared must be a "
                "PreparedBacktestResearchSpecification"
            )

        if attempt is not None:
            if not isinstance(attempt, RunAttempt):
                raise TypeError(
                    "attempt must be a RunAttempt or None"
                )
            if attempt.state is not RunAttemptState.RUNNING:
                raise ValueError(
                    "supplied RunAttempt must be RUNNING"
                )
            if prepared.experiment_spec_id is None:
                raise ValueError(
                    "non-exact prepared research cannot use "
                    "a supplied RunAttempt"
                )
            if (
                attempt.experiment_spec_id
                != prepared.experiment_spec_id
            ):
                raise ValueError(
                    "supplied RunAttempt must match the "
                    "prepared ExperimentSpec"
                )

            if attempt_terminalizer is None:
                raise ValueError(
                    "supplied RunAttempt requires attempt_terminalizer"
                )

        elif prepared.experiment_spec_id is not None:
            attempt = (
                self.catalog_store
                .create_running_attempt(
                    experiment_spec_id=(
                        prepared.experiment_spec_id
                    ),
                    created_at=self._clock(),
                )
            )

        if (
            attempt is None
            and attempt_terminalizer is not None
        ):
            raise ValueError(
                "attempt_terminalizer requires a RunAttempt"
            )

        terminalizer = attempt_terminalizer

        if (
            attempt is not None
            and terminalizer is None
        ):
            terminalizer = (
                self.catalog_store
                .terminalize_attempt_with_evidence
            )

        try:
            # M9.4h N01: final identity verification and financial
            # execution consume one private snapshot. Caller-owned
            # mutable objects are not consulted after this point.
            execution_prepared = replace(
                prepared,
                candles=deepcopy(
                    prepared.candles
                ),
            )
            execution_strategy = deepcopy(
                strategy
            )
            execution_config = deepcopy(
                config
            )
            execution_runtime_context = deepcopy(
                runtime_context
            )
            execution_dataset_context = deepcopy(
                dataset_context
            )

            self._validate_prepared_execution_identity(
                prepared=execution_prepared,
                strategy=execution_strategy,
                config=execution_config,
                runtime_context=(
                    execution_runtime_context
                ),
                dataset_context=(
                    execution_dataset_context
                ),
            )

            result = self._execute_candles(
                candles=execution_prepared.candles,
                strategy=execution_strategy,
                config=execution_config,
                runtime_context=(
                    execution_runtime_context
                ),
                dataset_context=(
                    execution_dataset_context
                ),
            )

        except AuthoritativeResearchStateError:
            raise
        except Exception as error:
            evidence = self._evidence(
                status=(
                    ResearchEvidenceStatus.FAILED
                ),
                dataset_context=dataset_context,
                requested_range=(
                    prepared.requested_range
                ),
                identity=prepared.identity,
                summary=(
                    self._semantic_failure_classification(
                        error
                    )
                    + ": "
                    + self._semantic_failure_message(
                        error
                    )
                ),
                dataset_fingerprint_value=(
                    prepared.dataset_fingerprint
                ),
                configuration_fingerprint=(
                    prepared.configuration_fingerprint
                ),
                artifact_references=(
                    prepared
                    .retrieval_artifact_references
                    + (
                        prepared.manifest_reference,
                    )
                ),
                persist=(attempt is None),
            )

            if attempt is not None:
                terminalizer(
                    attempt.attempt_id,
                    state=RunAttemptState.FAILED,
                    terminal_at=self._clock(),
                    evidence=evidence,
                    failure_classification=(
                        self._semantic_failure_classification(
                            error
                        )
                    ),
                    failure_message=(
                        self._semantic_failure_message(
                            error
                        )
                    ),
                )

            raise

        result_fp = (
            stable_backtest_result_fingerprint(
                result
            )
        )

        result_artifact = (
            self.artifact_store
            .persist_backtest_result(
                result,
                created_at=self._clock(),
            )
        )

        if attempt is None:
            result_artifact = (
                self.catalog_store
                .save_artifact(
                    result_artifact
                )
            )

        result_reference = (
            research_artifact_reference(
                result_artifact.artifact_id
            )
        )

        evidence_status = (
            ResearchEvidenceStatus.ACCEPTED
            if prepared.identity.is_exact
            else ResearchEvidenceStatus.INCOMPLETE
        )

        evidence = self._evidence(
            status=evidence_status,
            dataset_context=dataset_context,
            requested_range=(
                prepared.requested_range
            ),
            identity=prepared.identity,
            summary=(
                "Automatic Backtest reproducibility evidence accepted."
                if prepared.identity.is_exact
                else (
                    "Financial Backtest completed, but exact "
                    "software identity was unavailable."
                )
            ),
            dataset_fingerprint_value=(
                prepared.dataset_fingerprint
            ),
            configuration_fingerprint=(
                prepared.configuration_fingerprint
            ),
            result_fingerprint=result_fp,
            artifact_references=(
                prepared
                .retrieval_artifact_references
                + (
                    prepared.manifest_reference,
                    result_reference,
                )
            ),
            persist=(attempt is None),
        )

        if attempt is not None:
            attempt = terminalizer(
                attempt.attempt_id,
                state=RunAttemptState.SUCCEEDED,
                terminal_at=self._clock(),
                runtime_session_id=result.session_id,
                result_artifact=result_artifact,
                evidence=evidence,
            )

        return BacktestResearchExecution(
            result=result,
            attempt_id=(
                attempt.attempt_id
                if attempt is not None
                else None
            ),
            evidence_id=evidence.evidence_id,
            evidence_status=evidence.status,
        )

    def execute(
        self,
        *,
        historical_source: HistoricalSource | None,
        strategy: BaseStrategy,
        config: BacktestConfig,
        runtime_context: RuntimeContext,
        dataset_context: DatasetContext,
        prepared_retrieval: (
            Callable[[], PreparedResearchRetrieval]
            | None
        ) = None,
    ) -> BacktestResearchExecution:
        prepared = self.prepare_specification(
            historical_source=historical_source,
            strategy=strategy,
            config=config,
            runtime_context=runtime_context,
            dataset_context=dataset_context,
            prepared_retrieval=prepared_retrieval,
        )

        return self.execute_prepared(
            prepared=prepared,
            strategy=strategy,
            config=config,
            runtime_context=runtime_context,
            dataset_context=dataset_context,
        )
