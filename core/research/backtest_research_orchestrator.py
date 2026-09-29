"""Reusable M9.2 Backtest execution and evidence orchestration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from core.backtest.backtest_result import BacktestResult
from core.config.backtest_config import BacktestConfig
from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange
from core.market_data.historical_source import HistoricalSource
from core.research.models.research_catalog import (
    ComputationKind,
    RunAttemptState,
)
from core.research.models.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceStatus,
)
from core.research.reproducibility import (
    backtest_configuration_fingerprint_v2,
    build_backtest_run_manifest,
    dataset_fingerprint,
    stable_backtest_result_fingerprint,
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
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.strategies.base_strategy import BaseStrategy


Clock = Callable[[], datetime]
EvidenceIdFactory = Callable[[], str]
RetrieveCandles = Callable[..., list[Candle]]
ExecuteCandles = Callable[..., BacktestResult]


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
        except Exception as error:
            self._try_pre_spec_evidence(
                dataset_context=dataset_context,
                requested_range=requested_range,
                identity=identity,
                summary=(
                    "historical_data_retrieval_failed: "
                    + self._failure_message(error)
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

            manifest_artifact = (
                self.artifact_store.persist_backtest_manifest(
                    manifest,
                    created_at=self._clock(),
                )
            )

            manifest_artifact = (
                self.catalog_store.save_artifact(
                    manifest_artifact
                )
            )

            manifest_reference = research_artifact_reference(
                manifest_artifact.artifact_id
            )

            configuration_fp = (
                backtest_configuration_fingerprint_v2(
                    manifest
                )
            )
        except Exception as error:
            self._try_pre_spec_evidence(
                dataset_context=dataset_context,
                requested_range=requested_range,
                identity=identity,
                summary=(
                    "research_specification_preparation_failed: "
                    + self._failure_message(error)
                ),
                dataset_fingerprint_value=dataset_fp,
                configuration_fingerprint=configuration_fp,
                artifact_references=(
                    retrieval_artifact_references
                    + (
                        (manifest_reference,)
                        if manifest_reference is not None
                        else ()
                    )
                ),
            )
            raise

        attempt = None

        if identity.is_exact:
            spec = self.catalog_store.resolve_experiment_spec(
                computation_kind=ComputationKind.BACKTEST,
                manifest_artifact_id=manifest_artifact.artifact_id,
                dataset_fingerprint=dataset_fp,
                configuration_fingerprint=configuration_fp,
                repository_revision=identity.repository_revision,
                created_at=self._clock(),
            )

            attempt = self.catalog_store.create_running_attempt(
                experiment_spec_id=spec.experiment_spec_id,
                created_at=self._clock(),
            )

        try:
            result = self._execute_candles(
                candles=candles,
                strategy=strategy,
                config=config,
                runtime_context=runtime_context,
                dataset_context=dataset_context,
            )
        except Exception as error:
            evidence = self._evidence(
                status=ResearchEvidenceStatus.FAILED,
                dataset_context=dataset_context,
                requested_range=requested_range,
                identity=identity,
                summary=(
                    "backtest_execution_failed: "
                    + self._failure_message(error)
                ),
                dataset_fingerprint_value=dataset_fp,
                configuration_fingerprint=configuration_fp,
                artifact_references=(
                    retrieval_artifact_references
                    + (manifest_reference,)
                ),
                persist=(attempt is None),
            )

            if attempt is not None:
                self.catalog_store.terminalize_attempt_with_evidence(
                    attempt.attempt_id,
                    state=RunAttemptState.FAILED,
                    terminal_at=self._clock(),
                    evidence=evidence,
                    failure_classification=(
                        "backtest_execution_failed"
                    ),
                    failure_message=self._failure_message(
                        error
                    ),
                )

            raise

        result_fp = stable_backtest_result_fingerprint(
            result
        )

        result_artifact = (
            self.artifact_store.persist_backtest_result(
                result,
                created_at=self._clock(),
            )
        )

        if attempt is None:
            result_artifact = self.catalog_store.save_artifact(
                result_artifact
            )

        result_reference = research_artifact_reference(
            result_artifact.artifact_id
        )

        evidence_status = (
            ResearchEvidenceStatus.ACCEPTED
            if identity.is_exact
            else ResearchEvidenceStatus.INCOMPLETE
        )

        evidence = self._evidence(
            status=evidence_status,
            dataset_context=dataset_context,
            requested_range=requested_range,
            identity=identity,
            summary=(
                "Automatic Backtest reproducibility evidence accepted."
                if identity.is_exact
                else (
                    "Financial Backtest completed, but exact "
                    "software identity was unavailable."
                )
            ),
            dataset_fingerprint_value=dataset_fp,
            configuration_fingerprint=configuration_fp,
            result_fingerprint=result_fp,
            artifact_references=(
                retrieval_artifact_references
                + (
                    manifest_reference,
                    result_reference,
                )
            ),
            persist=(attempt is None),
        )

        if attempt is not None:
            attempt = (
                self.catalog_store.terminalize_attempt_with_evidence(
                    attempt.attempt_id,
                    state=RunAttemptState.SUCCEEDED,
                    terminal_at=self._clock(),
                    runtime_session_id=result.session_id,
                    result_artifact=result_artifact,
                    evidence=evidence,
                )
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
