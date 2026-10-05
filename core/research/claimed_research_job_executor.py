"""M9.4d execution composition for one claimed ResearchJob.

BEHAVIOR IMPACT: ADDED
PRIMARY BEHAVIOR IDS: RESEARCH-RULE-014, RESEARCH-RULE-015,
RESEARCH-RULE-016
PRESERVED BEHAVIOR IDS: RESEARCH-RULE-001, RESEARCH-RULE-009,
RESEARCH-RULE-010, RESEARCH-RULE-011

This service owns orchestration only. Financial computation remains in
the authoritative Backtest path. Strategy/provider/risk translation is
supplied explicitly by application/core composition and is never
invented here.
"""

from collections.abc import Callable
from datetime import datetime, timezone

from core.market_data.historical_retrieval import (
    IncompleteHistoricalCoverageError,
)
from core.research.backtest_research_orchestrator import (
    AuthoritativeResearchStateError,
)
from core.research.claimed_trial_execution_inputs import (
    ClaimedTrialExecutionInputs,
    ClaimedTrialInputValidationError,
    TrialExecutionInputResolver,
    snapshot_claimed_trial_execution_inputs,
    validate_claimed_trial_execution_inputs,
)
from core.strategies.strategy_factory import (
    create_registered_research_strategy,
)
from core.research.models.dataset_reference import (
    DATASET_REFERENCE_SCHEMA_ID,
    DatasetReference,
    decode_dataset_reference_bytes,
)
from core.research.models.registered_study import (
    EvidenceReusePolicy,
    ResearchJob,
    ResearchJobState,
    TrialDisposition,
)
from core.research.models.research_catalog import (
    ResearchArtifactKind,
)
from core.research.registered_trial_execution_plan import (
    RegisteredTrialExecutionPlanResolver,
)
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)
from core.research.successor_backtest_research_coordinator import (
    SuccessorBacktestResearchCoordinator,
    SuccessorHistoricalRetrievalError,
)


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _failure_message(error: Exception) -> str:
    value = str(error).strip()

    if not value:
        value = type(error).__name__

    return value[:1000]


class ClaimedResearchJobExecutor:
    """Execute exactly one already-claimed registered research job."""

    def __init__(
        self,
        *,
        catalog_store: SQLiteResearchCatalogStore,
        plan_resolver: RegisteredTrialExecutionPlanResolver,
        execution_input_resolver: TrialExecutionInputResolver,
        successor_coordinator: SuccessorBacktestResearchCoordinator,
        clock: Clock | None = None,
    ):
        if not isinstance(
            catalog_store,
            SQLiteResearchCatalogStore,
        ):
            raise TypeError(
                "catalog_store must be a "
                "SQLiteResearchCatalogStore"
            )

        if not isinstance(
            plan_resolver,
            RegisteredTrialExecutionPlanResolver,
        ):
            raise TypeError(
                "plan_resolver must be a "
                "RegisteredTrialExecutionPlanResolver"
            )

        if not callable(
            execution_input_resolver
        ):
            raise TypeError(
                "execution_input_resolver must be callable"
            )

        if not isinstance(
            successor_coordinator,
            SuccessorBacktestResearchCoordinator,
        ):
            raise TypeError(
                "successor_coordinator must be a "
                "SuccessorBacktestResearchCoordinator"
            )

        if clock is not None and not callable(clock):
            raise TypeError(
                "clock must be callable or None"
            )

        self.catalog_store = catalog_store
        self.plan_resolver = plan_resolver
        self.execution_input_resolver = (
            execution_input_resolver
        )
        self.successor_coordinator = (
            successor_coordinator
        )
        self._clock = clock or _utc_now

    def _load_running_job(
        self,
        claimed_job: ResearchJob,
    ) -> ResearchJob:
        if not isinstance(
            claimed_job,
            ResearchJob,
        ):
            raise TypeError(
                "claimed_job must be a ResearchJob"
            )

        current = (
            self.catalog_store
            .load_research_job(
                claimed_job.job_id
            )
        )

        if current is None:
            raise RuntimeError(
                "claimed ResearchJob disappeared "
                "before execution"
            )

        if (
            current.trial_id
            != claimed_job.trial_id
        ):
            raise RuntimeError(
                "claimed ResearchJob Trial identity changed"
            )

        if (
            current.state
            is not ResearchJobState.RUNNING
        ):
            raise ValueError(
                "claimed ResearchJob must still be RUNNING"
            )

        if (
            current.attempt_id is not None
            or current.terminal_at is not None
            or current.completion_kind is not None
            or current.reused_attempt_id is not None
            or current.reused_evidence_id is not None
            or current.reused_result_artifact_id is not None
        ):
            raise ValueError(
                "new claimed-job execution requires "
                "an uncompleted ResearchJob with no "
                "attempt or reuse lineage"
            )

        return current

    def _acknowledge_cancellation_if_requested(
        self,
        job_id: str,
    ) -> ResearchJob | None:
        """
        Acknowledge one durable cooperative cancellation before
        financial execution has acquired RunAttempt/reuse lineage.
        """

        current = (
            self.catalog_store
            .load_research_job(
                job_id
            )
        )

        if current is None:
            raise RuntimeError(
                "claimed ResearchJob disappeared "
                "during cancellation checkpoint"
            )

        if (
            current.state
            is ResearchJobState.CANCELLED
        ):
            return current

        if (
            current.state
            is not ResearchJobState.RUNNING
            or current.cancel_requested_at is None
        ):
            return None

        if (
            current.attempt_id is not None
            or current.terminal_at is not None
            or current.completion_kind is not None
            or current.reused_attempt_id is not None
            or current.reused_evidence_id is not None
            or current.reused_result_artifact_id is not None
        ):
            return None

        _, terminal_job, _ = (
            self.catalog_store
            .acknowledge_running_research_job_cancellation(
                job_id=job_id,
                terminal_at=self._clock(),
            )
        )

        return terminal_job

    def _terminalize_preparation_failure(
        self,
        job: ResearchJob,
        *,
        classification: str,
        error: Exception,
        trial_disposition: TrialDisposition = (
            TrialDisposition.FAILED
        ),
    ) -> ResearchJob:
        _, terminal_job, _ = (
            self.catalog_store
            .fail_running_job_without_attempt(
                job_id=job.job_id,
                terminal_at=self._clock(),
                failure_classification=(
                    classification
                ),
                failure_message=(
                    _failure_message(error)
                ),
                trial_disposition=(
                    trial_disposition
                ),
            )
        )

        return terminal_job

    def _resolve_inputs(
        self,
        plan,
    ) -> ClaimedTrialExecutionInputs:
        inputs = self.execution_input_resolver(
            plan
        )

        if not isinstance(
            inputs,
            ClaimedTrialExecutionInputs,
        ):
            raise TypeError(
                "execution_input_resolver must return "
                "ClaimedTrialExecutionInputs"
            )

        inputs = (
            snapshot_claimed_trial_execution_inputs(
                inputs
            )
        )

        validate_claimed_trial_execution_inputs(
            plan,
            inputs,
        )

        return inputs

    def _successor_dataset_reference(
        self,
        artifact_references,
    ) -> tuple[str, DatasetReference] | None:
        matches = []

        for reference in artifact_references:
            if (
                not isinstance(reference, str)
                or not reference.startswith(
                    "artifact:sha256:"
                )
            ):
                continue

            artifact_id = reference.removeprefix(
                "artifact:"
            )

            artifact = (
                self.catalog_store
                .load_artifact(
                    artifact_id
                )
            )

            if artifact is None:
                continue

            if (
                artifact.artifact_kind
                is not ResearchArtifactKind.DATASET_REFERENCE
            ):
                continue

            if (
                artifact.schema_id
                != DATASET_REFERENCE_SCHEMA_ID
            ):
                raise AuthoritativeResearchStateError(
                    RuntimeError(
                        "DatasetReference artifact metadata "
                        "is incompatible with canonical lineage"
                    )
                )

            matches.append(
                (artifact_id, artifact)
            )

        if len(matches) != 1:
            return None

        artifact_id, artifact = matches[0]

        try:
            payload = (
                self.successor_coordinator
                .orchestrator
                .artifact_store
                .load_bytes(
                    artifact_id
                )
            )

            if len(payload) != artifact.byte_count:
                raise RuntimeError(
                    "DatasetReference artifact byte count "
                    "does not match durable metadata"
                )

            reference = (
                decode_dataset_reference_bytes(
                    payload
                )
            )

        except (
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            raise AuthoritativeResearchStateError(
                RuntimeError(
                    "DatasetReference artifact is unavailable "
                    "or corrupt"
                )
            ) from error

        try:
            self.catalog_store.save_dataset_reference_artifact(
                artifact,
                reference,
            )
        except Exception as error:
            raise AuthoritativeResearchStateError(
                error
            ) from error

        return (
            artifact_id,
            reference,
        )

    def _successor_reuse_dataset_lineage(
        self,
        *,
        prepared,
        reusable,
    ) -> tuple[str, str] | None:
        requested = (
            self._successor_dataset_reference(
                prepared.retrieval_artifact_references
            )
        )

        source = (
            self._successor_dataset_reference(
                reusable.evidence.artifact_references
            )
        )

        if (
            requested is None
            or source is None
        ):
            return None

        if (
            requested[1].identity.dataset_id
            != source[1].identity.dataset_id
        ):
            return None

        return (
            requested[0],
            source[0],
        )

    def execute(
        self,
        claimed_job: ResearchJob,
    ) -> ResearchJob:
        """
        Progress one RUNNING job to one durable terminal outcome.

        Ordinary Trial-specific preparation or financial-computation
        failure is persisted and returned as FAILED. Persistence or
        lifecycle-coherence failure is not swallowed.
        """

        job = self._load_running_job(
            claimed_job
        )

        # A registered plan is authoritative durable history. Failure
        # to read/verify it is treated as persistence/integrity failure
        # and deliberately propagates to stop new scheduler claims.
        plan = self.plan_resolver.resolve(
            job.trial_id
        )

        try:
            inputs = self._resolve_inputs(
                plan
            )
        except AuthoritativeResearchStateError:
            raise
        except ClaimedTrialInputValidationError as error:
            return self._terminalize_preparation_failure(
                job,
                classification="invalid_input",
                error=error,
                trial_disposition=(
                    TrialDisposition.INVALID
                ),
            )
        except Exception as error:
            return self._terminalize_preparation_failure(
                job,
                classification="unknown_failure",
                error=error,
            )

        cancelled = (
            self._acknowledge_cancellation_if_requested(
                job.job_id
            )
        )

        if cancelled is not None:
            return cancelled

        try:
            preparation_strategy = (
                create_registered_research_strategy(
                    plan.strategy_procedure_id,
                    inputs.config,
                )
            )

            prepared = (
                self.successor_coordinator
                .prepare_specification(
                    strategy=preparation_strategy,
                    config=inputs.config,
                    runtime_context=(
                        inputs.runtime_context
                    ),
                    dataset_context=(
                        inputs.dataset_context
                    ),
                    instrument_id=(
                        plan.instrument_id
                    ),
                    provider=inputs.provider,
                    price_adjustment_basis=(
                        inputs.price_adjustment_basis
                    ),
                )
            )

            if (
                not prepared.identity.is_exact
                or prepared.experiment_spec_id
                is None
            ):
                raise ValueError(
                    "registered Trial requires exact "
                    "software identity and ExperimentSpec"
                )

            if (
                prepared.identity.repository_revision
                != plan.repository_revision
            ):
                raise ValueError(
                    "prepared software revision does not "
                    "match the registered StudyRevision"
                )

            if (
                prepared.requested_range
                != plan.trial_range
            ):
                raise ValueError(
                    "prepared Backtest range does not "
                    "match the Trial membership episode"
                )

            # Retrieval/preparation may have received references to the
            # first isolated binding. Create the final private binding
            # only after that phase, then re-prove registered semantics.
            inputs = (
                snapshot_claimed_trial_execution_inputs(
                    inputs
                )
            )

            validate_claimed_trial_execution_inputs(
                plan,
                inputs,
            )

            execution_strategy = (
                create_registered_research_strategy(
                    plan.strategy_procedure_id,
                    inputs.config,
                )
            )

        except (ClaimedTrialInputValidationError, ValueError) as error:
            return self._terminalize_preparation_failure(
                job,
                classification="invalid_input",
                error=error,
                trial_disposition=(
                    TrialDisposition.INVALID
                ),
            )
        except AuthoritativeResearchStateError:
            # D08: authoritative persistence/integrity failure is not
            # an independent Trial outcome. Leave the already-claimed
            # job truthfully RUNNING for explicit durable recovery and
            # propagate to the worker-pool fail-closed boundary.
            raise
        except SuccessorHistoricalRetrievalError as error:
            if isinstance(
                error.original_error,
                IncompleteHistoricalCoverageError,
            ):
                return self._terminalize_preparation_failure(
                    job,
                    classification=(
                        "insufficient_history"
                    ),
                    error=error.original_error,
                    trial_disposition=(
                        TrialDisposition.INSUFFICIENT
                    ),
                )

            if isinstance(
                error.original_error,
                (ConnectionError, TimeoutError),
            ):
                classification = (
                    "transient_operational_failure"
                )
            else:
                classification = "unknown_failure"

            return self._terminalize_preparation_failure(
                job,
                classification=classification,
                error=error.original_error,
            )

        except Exception as error:
            return self._terminalize_preparation_failure(
                job,
                classification="unknown_failure",
                error=error,
            )

        cancelled = (
            self._acknowledge_cancellation_if_requested(
                job.job_id
            )
        )

        if cancelled is not None:
            return cancelled

        experiment_spec_id = (
            prepared.experiment_spec_id
        )

        if (
            plan.evidence_reuse_policy
            is EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ):
            reusable = (
                self.successor_coordinator
                .orchestrator
                .find_exact_reusable_execution(
                    experiment_spec_id
                )
            )

            reuse_dataset_lineage = None

            if reusable is not None:
                reuse_dataset_lineage = (
                    self._successor_reuse_dataset_lineage(
                        prepared=prepared,
                        reusable=reusable,
                    )
                )

                if reuse_dataset_lineage is None:
                    reusable = None

            cancelled = (
                self._acknowledge_cancellation_if_requested(
                    job.job_id
                )
            )

            if cancelled is not None:
                return cancelled

            if reusable is not None:
                try:
                    _, terminal_job, _ = (
                        self.catalog_store
                        ._complete_running_job_with_exact_reuse(
                            job_id=job.job_id,
                            experiment_spec_id=(
                                experiment_spec_id
                            ),
                            reused_attempt_id=(
                                reusable.attempt.attempt_id
                            ),
                            terminal_at=self._clock(),
                            requested_dataset_reference_artifact_id=(
                                reuse_dataset_lineage[0]
                            ),
                            source_dataset_reference_artifact_id=(
                                reuse_dataset_lineage[1]
                            ),
                        )
                    )
                except ValueError as error:
                    if (
                        "cancellation request blocks "
                        "exact reuse completion"
                        not in str(error)
                    ):
                        raise

                    cancelled = (
                        self._acknowledge_cancellation_if_requested(
                            job.job_id
                        )
                    )

                    if cancelled is None:
                        raise

                    return cancelled

                return terminal_job

        cancelled = (
            self._acknowledge_cancellation_if_requested(
                job.job_id
            )
        )

        if cancelled is not None:
            return cancelled

        try:
            _, linked_job, attempt = (
                self.catalog_store
                .bind_trial_spec_create_attempt_for_running_job(
                    job_id=job.job_id,
                    experiment_spec_id=(
                        experiment_spec_id
                    ),
                    attempt_created_at=self._clock(),
                )
            )
        except ValueError as error:
            if (
                "cancellation request blocks "
                "fresh RunAttempt creation"
                not in str(error)
            ):
                raise

            cancelled = (
                self._acknowledge_cancellation_if_requested(
                    job.job_id
                )
            )

            if cancelled is None:
                raise

            return cancelled

        if (
            linked_job.attempt_id
            != attempt.attempt_id
        ):
            raise RuntimeError(
                "ResearchJob/RunAttempt linkage is "
                "internally inconsistent"
            )

        def terminalize(
            attempt_id,
            **kwargs,
        ):
            return (
                self.catalog_store
                .terminalize_running_job_attempt_with_evidence(
                    attempt_id,
                    job_id=job.job_id,
                    **kwargs,
                )
            )

        try:
            (
                self.successor_coordinator
                .orchestrator
                .execute_prepared(
                    prepared=prepared,
                    strategy=execution_strategy,
                    config=inputs.config,
                    runtime_context=(
                        inputs.runtime_context
                    ),
                    dataset_context=(
                        inputs.dataset_context
                    ),
                    attempt=attempt,
                    attempt_terminalizer=(
                        terminalize
                    ),
                )
            )

        except Exception:
            # Deterministic financial failures are expected to have
            # been durably terminalized by the coordinated terminalizer.
            # If persistence failed, the job remains non-terminal and
            # the original exception must propagate so scheduling stops.
            persisted = (
                self.catalog_store
                .load_research_job(
                    job.job_id
                )
            )

            if (
                persisted is not None
                and persisted.state
                is ResearchJobState.FAILED
                and persisted.attempt_id
                == attempt.attempt_id
            ):
                return persisted

            raise

        terminal_job = (
            self.catalog_store
            .load_research_job(
                job.job_id
            )
        )

        if (
            terminal_job is None
            or terminal_job.state
            is not ResearchJobState.SUCCEEDED
            or terminal_job.attempt_id
            != attempt.attempt_id
        ):
            raise RuntimeError(
                "fresh execution returned without "
                "durable ResearchJob success"
            )

        return terminal_job
