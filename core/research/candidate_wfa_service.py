"""M9.6 adapter from historical eligibility to existing fixed-candidate WFA."""

from datetime import datetime, timezone
import sqlite3
from uuid import uuid4

from core.config.walk_forward_config import WALK_FORWARD_CONFIG
from core.market_data.historical_coverage import TimeRange
from core.market_data.historical_retrieval import IncompleteHistoricalCoverageError
from core.research.claimed_trial_execution_inputs import (
    ClaimedTrialExecutionInputs,
    ClaimedTrialInputValidationError,
    snapshot_claimed_trial_execution_inputs,
    validate_claimed_trial_execution_inputs,
)
from core.research.executable_compatibility import (
    ExecutableCompatibilityOperationalError,
)
from core.research.models.dataset import DatasetIdentityV2
from core.research.models.dataset_reference import (
    DATASET_REFERENCE_SCHEMA_ID,
    decode_dataset_reference_bytes,
)
from core.research.models.qualification import QualificationOutcome
from core.research.models.registered_study import TrialDisposition
from core.research.models.research_catalog import (
    ComputationKind,
    ResearchArtifactKind,
)
from core.research.models.research_evidence import ResearchEvidenceStatus
from core.research.research_artifact_store import (
    ArtifactIdentityMismatchError,
    research_artifact_reference,
)
from core.research.sqlite_research_evidence_store import SQLiteResearchEvidenceStore
from core.research.study_aggregation import (
    StudyAggregationError,
    StudyAggregationService,
)
from core.research.models.wfa_qualification import (
    CANDIDATE_WFA_EVALUATOR_VERSION,
    CANDIDATE_WFA_RESULT_SCHEMA_ID,
    CandidateWfaDecision,
    WfaEvidenceValidity,
    WfaQualificationOutcome,
    candidate_wfa_result_bytes,
    wfa_window_configuration_fingerprint,
    wfa_window_configuration_payload,
)
from core.research.reproducibility import (
    BACKTEST_RUN_MANIFEST_SCHEMA,
    backtest_configuration_fingerprint_v2,
    backtest_run_manifest_payload,
    build_backtest_run_manifest,
    dataset_fingerprint,
    decode_canonical_bytes,
)
from core.strategies.strategy_factory import (
    create_registered_research_strategy,
    get_research_procedure_strategy_class,
)
from core.walk_forward.metrics import WalkForwardMetrics
from core.walk_forward.optimizer import GridSearchOptimizer
from core.walk_forward.runner import WalkForwardRunner
from core.walk_forward.window_generator import WalkForwardWindowGenerator


class CandidateWfaOperationalError(RuntimeError):
    """Reliable M9.6 evaluation could not continue because authority failed."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_decision_id() -> str:
    return f"wfa-qualification-{uuid4().hex}"


def _is_operational_failure(error: BaseException) -> bool:
    current = error
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, sqlite3.Error):
            return True
        if isinstance(current, PermissionError):
            return True
        if isinstance(current, OSError) and not isinstance(
            current,
            FileNotFoundError,
        ):
            return True
        current = current.__cause__ or current.__context__
    return False


def _is_deterministic_evidence_failure(error: BaseException) -> bool:
    """Recognize proven evidence contradictions without hiding infrastructure faults."""

    if _is_operational_failure(error):
        return False

    chain = []
    current = error
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__

    if any(
        isinstance(item, ArtifactIdentityMismatchError)
        for item in chain
    ):
        return True

    root = chain[-1]
    if isinstance(
        root,
        (TypeError, ValueError, KeyError, FileNotFoundError),
    ):
        return True

    if len(chain) == 1 and isinstance(error, StudyAggregationError):
        return True

    # _load_authoritative_historical_evidence deliberately translates a
    # proven deterministic StudyAggregationError into ValueError. Preserve
    # that semantic wrapper without treating deeper/unknown causal chains
    # as deterministic. Operational causes were already excluded above.
    return (
        len(chain) == 2
        and isinstance(chain[0], ValueError)
        and isinstance(chain[1], StudyAggregationError)
    )


class CandidateWfaService:
    """Evaluate all currently historically eligible fixed candidates in a revision."""

    def __init__(
        self,
        *,
        catalog_store,
        artifact_store,
        qualification_store,
        wfa_store,
        plan_resolver,
        execution_input_resolver,
        retrieval_service,
        software_identity_provider,
        executable_compatibility_checker,
        clock=None,
        decision_id_factory=None,
    ) -> None:
        if not callable(execution_input_resolver):
            raise TypeError("execution_input_resolver must be callable")
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable or None")
        if decision_id_factory is not None and not callable(decision_id_factory):
            raise TypeError("decision_id_factory must be callable or None")

        self.catalog_store = catalog_store
        self.artifact_store = artifact_store
        self.qualification_store = qualification_store
        self.wfa_store = wfa_store
        self.plan_resolver = plan_resolver
        self.execution_input_resolver = execution_input_resolver
        self.retrieval_service = retrieval_service
        self.software_identity_provider = software_identity_provider
        self.executable_compatibility_checker = executable_compatibility_checker
        self._clock = clock or _utc_now
        self._decision_id_factory = decision_id_factory or _new_decision_id

        self._wfa_configuration = wfa_window_configuration_payload(
            in_sample_bars=WALK_FORWARD_CONFIG.in_sample_bars,
            out_sample_bars=WALK_FORWARD_CONFIG.out_sample_bars,
            step_bars=WALK_FORWARD_CONFIG.step_bars,
            mode=WALK_FORWARD_CONFIG.mode,
        )
        self._wfa_configuration_fingerprint = (
            wfa_window_configuration_fingerprint(
                **self._wfa_configuration
            )
        )

    def _append_decision(
        self,
        *,
        historical_decision,
        validity: WfaEvidenceValidity,
        outcome: WfaQualificationOutcome,
        reason: str,
        evaluator_repository_revision: str | None = None,
        dataset_reference_artifact_id: str | None = None,
        dataset_id: str | None = None,
        dataset_fingerprint_value: str | None = None,
        result_artifact_id: str | None = None,
        wfa_verdict: str | None = None,
    ) -> CandidateWfaDecision:
        decision = CandidateWfaDecision(
            decision_id=self._decision_id_factory(),
            created_at=self._clock(),
            evaluator_version=CANDIDATE_WFA_EVALUATOR_VERSION,
            study_revision_id=historical_decision.study_revision_id,
            trial_id=historical_decision.trial_id,
            candidate_revision_id=historical_decision.candidate_revision_id,
            historical_qualification_decision_id=(
                historical_decision.decision_id
            ),
            evaluator_repository_revision=evaluator_repository_revision,
            dataset_reference_artifact_id=dataset_reference_artifact_id,
            dataset_id=dataset_id,
            dataset_fingerprint=dataset_fingerprint_value,
            wfa_configuration_fingerprint=(
                self._wfa_configuration_fingerprint
            ),
            result_artifact_id=result_artifact_id,
            evidence_validity=validity,
            wfa_verdict=wfa_verdict,
            outcome=outcome,
            reason=reason,
        )
        try:
            self.wfa_store._append_decision(decision)
            reloaded = self.wfa_store.load_decision(decision.decision_id)
        except Exception as error:
            raise CandidateWfaOperationalError(
                "WFA qualification decision could not be durably persisted"
            ) from error
        if reloaded != decision:
            raise CandidateWfaOperationalError(
                "WFA qualification decision read-back mismatch"
            )
        return decision

    def _invalid(
        self,
        historical_decision,
        reason: str,
        **known,
    ) -> CandidateWfaDecision:
        return self._append_decision(
            historical_decision=historical_decision,
            validity=WfaEvidenceValidity.INVALID,
            outcome=WfaQualificationOutcome.INVALID,
            reason=reason,
            **known,
        )

    def _insufficient(
        self,
        historical_decision,
        reason: str,
        **known,
    ) -> CandidateWfaDecision:
        return self._append_decision(
            historical_decision=historical_decision,
            validity=WfaEvidenceValidity.INSUFFICIENT,
            outcome=WfaQualificationOutcome.INSUFFICIENT,
            reason=reason,
            **known,
        )

    def _resolve_inputs(self, plan) -> ClaimedTrialExecutionInputs:
        inputs = self.execution_input_resolver(plan)
        if not isinstance(inputs, ClaimedTrialExecutionInputs):
            raise ClaimedTrialInputValidationError(
                "execution_input_resolver did not return ClaimedTrialExecutionInputs"
            )
        inputs = snapshot_claimed_trial_execution_inputs(inputs)
        validate_claimed_trial_execution_inputs(plan, inputs)
        return inputs

    @staticmethod
    def _lineage_from_snapshot(snapshot, trial, result_artifact_id):
        events = snapshot.disposition_events
        if not events or events[-1].causing_job_id is None:
            raise ValueError("verified Trial lacks terminal causing-job lineage")
        job = next(
            (
                item
                for item in snapshot.jobs
                if item.job_id == events[-1].causing_job_id
            ),
            None,
        )
        if job is None:
            raise ValueError("verified Trial causing job is absent")

        if trial.disposition is TrialDisposition.EXECUTED:
            attempt_id = job.attempt_id
            candidates = dict(snapshot.owned_attempts)
        elif trial.disposition is TrialDisposition.REUSED:
            attempt_id = job.reused_attempt_id
            candidates = dict(snapshot.reused_attempts)
        else:
            raise ValueError("verified Trial disposition is not result-bearing")

        if attempt_id is None or attempt_id not in candidates:
            raise ValueError("verified Trial attempt lineage is absent")
        attempt = candidates[attempt_id]
        if attempt.evidence_id is None:
            raise ValueError("verified Trial evidence identity is absent")
        if attempt.result_artifact_id != result_artifact_id:
            raise ValueError("verified Trial result lineage changed")
        return attempt_id, attempt.evidence_id

    def _load_authoritative_historical_evidence(
        self,
        *,
        historical_decision,
        trial,
        experiment_spec,
    ):
        verifier = StudyAggregationService(
            catalog_store=self.catalog_store,
            artifact_store=self.artifact_store,
        )
        try:
            verified = verifier.load_verified_trial_backtest(trial.trial_id)
            snapshot = self.catalog_store.load_research_trial_detail_snapshot(
                trial.trial_id
            )
            if snapshot is None:
                raise ValueError("verified Trial snapshot disappeared")
            attempt_id, evidence_id = self._lineage_from_snapshot(
                snapshot,
                trial,
                verified.result_artifact_id,
            )
        except StudyAggregationError as error:
            if not _is_deterministic_evidence_failure(error):
                raise CandidateWfaOperationalError(
                    "historical Backtest evidence could not be reliably verified"
                ) from error
            raise ValueError(
                "historical Backtest result/evidence authority is invalid"
            ) from error
        except Exception as error:
            if _is_operational_failure(error):
                raise CandidateWfaOperationalError(
                    "historical Backtest lineage could not be reliably read"
                ) from error
            raise

        if (
            verified.result_artifact_id
            != historical_decision.result_artifact_id
            or attempt_id != historical_decision.attempt_id
            or evidence_id != historical_decision.evidence_id
        ):
            raise ValueError(
                "historical qualification decision does not match "
                "authoritative result/attempt/evidence lineage"
            )

        database_path = getattr(self.catalog_store, "database_path", None)
        if database_path is None:
            raise CandidateWfaOperationalError(
                "canonical M9.6 historical evidence requires catalog database authority"
            )

        try:
            evidence = SQLiteResearchEvidenceStore(database_path).load(
                evidence_id
            )
        except Exception as error:
            raise CandidateWfaOperationalError(
                "authoritative historical ResearchEvidence could not be loaded"
            ) from error

        if (
            evidence is None
            or evidence.evidence_id != evidence_id
            or evidence.status is not ResearchEvidenceStatus.ACCEPTED
            or evidence.dataset_fingerprint
            != experiment_spec.dataset_fingerprint
            or evidence.configuration_fingerprint
            != experiment_spec.configuration_fingerprint
            or evidence.result_fingerprint
            != verified.result_artifact_id
            or evidence.repository_revision
            != experiment_spec.repository_revision
        ):
            raise ValueError(
                "authoritative historical ResearchEvidence contradicts "
                "the admitted ExperimentSpec/result lineage"
            )

        manifest_reference = research_artifact_reference(
            experiment_spec.manifest_artifact_id
        )
        result_reference = research_artifact_reference(
            verified.result_artifact_id
        )
        if (
            manifest_reference not in evidence.artifact_references
            or result_reference not in evidence.artifact_references
        ):
            raise ValueError(
                "authoritative historical ResearchEvidence lacks "
                "manifest/result artifact references"
            )

        return evidence

    def _load_source_dataset_reference(
        self,
        evidence,
        *,
        admitted_artifact_id: str,
    ):
        if not isinstance(admitted_artifact_id, str) or not admitted_artifact_id:
            raise ValueError(
                "historical qualification lacks a frozen DatasetReference admission"
            )

        matches = []
        for reference in evidence.artifact_references:
            if not (
                isinstance(reference, str)
                and reference.startswith("artifact:sha256:")
            ):
                continue
            artifact_id = reference.removeprefix("artifact:")
            artifact = self.catalog_store.load_artifact(artifact_id)
            if artifact is None:
                raise ValueError(
                    "historical evidence references missing research artifact"
                )
            if artifact.artifact_kind is ResearchArtifactKind.DATASET_REFERENCE:
                if artifact.schema_id != DATASET_REFERENCE_SCHEMA_ID:
                    raise ValueError(
                        "historical DatasetReference has incompatible schema"
                    )
                matches.append((artifact_id, artifact))

        if len(matches) != 1:
            raise ValueError(
                "historical eligible evidence must contain exactly one DatasetReference"
            )

        artifact_id, artifact = matches[0]
        if artifact_id != admitted_artifact_id:
            raise ValueError(
                "historical evidence no longer references the DatasetReference "
                "frozen at qualification admission"
            )
        payload = self.artifact_store.load_bytes(artifact_id)
        if len(payload) != artifact.byte_count:
            raise ValueError("historical DatasetReference byte count mismatch")
        reference = decode_dataset_reference_bytes(payload)
        registered_dataset_id = (
            self.catalog_store.load_dataset_reference_identity(artifact_id)
        )
        if registered_dataset_id != reference.identity.dataset_id:
            raise ValueError(
                "historical DatasetReference identity binding is missing or contradictory"
            )
        return artifact_id, reference

    def _load_historical_manifest_payload(self, experiment_spec):
        artifact = self.catalog_store.load_artifact(
            experiment_spec.manifest_artifact_id
        )
        if artifact is None:
            raise ValueError("historical Backtest manifest artifact is missing")
        if (
            artifact.artifact_kind is not ResearchArtifactKind.BACKTEST_RUN_MANIFEST
            or artifact.schema_id != BACKTEST_RUN_MANIFEST_SCHEMA
        ):
            raise ValueError(
                "historical Backtest manifest has wrong artifact kind/schema"
            )
        payload = self.artifact_store.load_bytes(artifact.artifact_id)
        if len(payload) != artifact.byte_count:
            raise ValueError("historical Backtest manifest byte count mismatch")
        return decode_canonical_bytes(
            payload,
            schema=BACKTEST_RUN_MANIFEST_SCHEMA,
        )

    @staticmethod
    def _dataset_known_fields(
        *,
        evaluator_repository_revision: str,
        dataset_reference_artifact_id: str,
        dataset_id: str,
        dataset_fingerprint_value: str,
    ) -> dict:
        return {
            "evaluator_repository_revision": evaluator_repository_revision,
            "dataset_reference_artifact_id": dataset_reference_artifact_id,
            "dataset_id": dataset_id,
            "dataset_fingerprint_value": dataset_fingerprint_value,
        }

    @staticmethod
    def _qualification_outcome_for_verdict(
        verdict: str,
    ) -> WfaQualificationOutcome:
        if verdict == "PASS":
            return WfaQualificationOutcome.ELIGIBLE
        if verdict == "FAIL":
            return WfaQualificationOutcome.REJECTED
        raise ValueError("unsupported WFA verdict")

    def _evaluate_one(self, historical_decision, trial) -> CandidateWfaDecision:
        if (
            historical_decision.outcome is not QualificationOutcome.ELIGIBLE
            or historical_decision.candidate_revision_id is None
        ):
            raise CandidateWfaOperationalError(
                "eligible-list query returned a non-eligible historical decision"
            )

        try:
            candidate = self.qualification_store.load_candidate_revision(
                historical_decision.candidate_revision_id
            )
        except Exception as error:
            raise CandidateWfaOperationalError(
                "fixed candidate authority could not be read"
            ) from error
        if candidate is None:
            raise CandidateWfaOperationalError(
                "eligible historical decision references a missing CandidateRevision"
            )

        if (
            candidate.study_revision_id != historical_decision.study_revision_id
            or candidate.trial_id != historical_decision.trial_id
            or trial.trial_id != historical_decision.trial_id
            or trial.study_revision_id != historical_decision.study_revision_id
            or candidate.parameter_configuration_fingerprint
            != trial.parameter_configuration_fingerprint
            or candidate.experiment_spec_id != trial.experiment_spec_id
        ):
            return self._invalid(
                historical_decision,
                "historical Candidate/Trial/StudyRevision identity is contradictory",
            )

        try:
            plan = self.plan_resolver.resolve(trial.trial_id)
            inputs = self._resolve_inputs(plan)
        except Exception as error:
            if _is_operational_failure(error):
                raise CandidateWfaOperationalError(
                    "registered historical executable authority could not be read"
                ) from error
            if isinstance(
                error,
                (ClaimedTrialInputValidationError, TypeError, ValueError),
            ):
                return self._invalid(
                    historical_decision,
                    "registered historical executable inputs failed validation",
                )
            raise CandidateWfaOperationalError(
                "registered historical executable authority failed unexpectedly"
            ) from error

        if (
            plan.study_revision_id != candidate.study_revision_id
            or plan.trial_id != candidate.trial_id
            or dict(plan.parameter_configuration)
            != dict(inputs.config.strategy_params)
        ):
            return self._invalid(
                historical_decision,
                "resolved registered plan does not match fixed candidate inputs",
            )

        try:
            experiment_spec = self.catalog_store.load_experiment_spec(
                candidate.experiment_spec_id
            )
        except Exception as error:
            raise CandidateWfaOperationalError(
                "historical ExperimentSpec could not be read"
            ) from error
        if experiment_spec is None:
            return self._invalid(
                historical_decision,
                "historical Candidate ExperimentSpec is missing",
            )
        if (
            experiment_spec.computation_kind is not ComputationKind.BACKTEST
            or experiment_spec.experiment_spec_id != trial.experiment_spec_id
            or experiment_spec.repository_revision != plan.repository_revision
        ):
            return self._invalid(
                historical_decision,
                "historical ExperimentSpec does not match registered Trial authority",
            )

        if (
            historical_decision.attempt_id is None
            or historical_decision.evidence_id is None
            or historical_decision.result_artifact_id is None
        ):
            return self._invalid(
                historical_decision,
                "eligible historical decision lacks admitted result lineage",
            )

        try:
            evidence = self._load_authoritative_historical_evidence(
                historical_decision=historical_decision,
                trial=trial,
                experiment_spec=experiment_spec,
            )
        except CandidateWfaOperationalError:
            raise
        except Exception as error:
            if _is_deterministic_evidence_failure(error):
                return self._invalid(
                    historical_decision,
                    "historical admitted result/evidence authority is contradictory",
                )
            raise CandidateWfaOperationalError(
                "historical admitted result/evidence authority could not be reliably verified"
            ) from error

        if (
            evidence.requested_range != plan.trial_range
            or evidence.dataset_context != inputs.dataset_context
        ):
            return self._invalid(
                historical_decision,
                "historical admitted evidence does not match registered data inputs",
            )

        try:
            admitted_dataset_artifact_id = (
                self.qualification_store.load_dataset_admission(
                    historical_decision.decision_id
                )
            )
        except Exception as error:
            raise CandidateWfaOperationalError(
                "historical DatasetReference admission could not be loaded"
            ) from error
        if admitted_dataset_artifact_id is None:
            return self._invalid(
                historical_decision,
                "historical qualification lacks a frozen DatasetReference admission",
            )

        try:
            dataset_artifact_id, source_reference = (
                self._load_source_dataset_reference(
                    evidence,
                    admitted_artifact_id=admitted_dataset_artifact_id,
                )
            )
        except Exception as error:
            if _is_deterministic_evidence_failure(error):
                return self._invalid(
                    historical_decision,
                    "historical admitted DatasetReference is missing, corrupt or ambiguous",
                )
            raise CandidateWfaOperationalError(
                "historical DatasetReference could not be read reliably"
            ) from error

        source_identity = source_reference.identity
        if (
            source_identity.instrument_id != plan.instrument_id
            or source_identity.requested_range != plan.trial_range
            or source_identity.timeframe != plan.timeframe
            or source_identity.timezone != plan.timezone
            or source_identity.price_adjustment_basis
            is not inputs.price_adjustment_basis
        ):
            return self._invalid(
                historical_decision,
                "historical DatasetReference contradicts registered dataset authority",
            )

        try:
            admitted_legacy_dataset_fingerprint = dataset_fingerprint(
                inputs.dataset_context,
                plan.trial_range,
                source_identity.candles,
            )
        except (TypeError, ValueError):
            return self._invalid(
                historical_decision,
                "historical DatasetReference cannot reproduce canonical historical data",
            )
        if (
            admitted_legacy_dataset_fingerprint
            != experiment_spec.dataset_fingerprint
        ):
            return self._invalid(
                historical_decision,
                "historical DatasetReference candles contradict the admitted historical dataset",
            )

        try:
            software_identity = self.software_identity_provider.resolve()
        except Exception as error:
            raise CandidateWfaOperationalError(
                "current evaluator software identity could not be resolved"
            ) from error
        evaluator_revision = getattr(
            software_identity,
            "repository_revision",
            None,
        )
        worktree_clean = getattr(
            software_identity,
            "worktree_clean",
            None,
        )
        if evaluator_revision is None or worktree_clean is None:
            raise CandidateWfaOperationalError(
                "current evaluator software identity is unavailable operationally"
            )
        if worktree_clean is not True:
            return self._invalid(
                historical_decision,
                "current evaluator worktree is not clean",
                evaluator_repository_revision=evaluator_revision,
                dataset_reference_artifact_id=dataset_artifact_id,
                dataset_id=source_identity.dataset_id,
                dataset_fingerprint_value=experiment_spec.dataset_fingerprint,
            )

        try:
            compatibility = self.executable_compatibility_checker.check(
                historical_revision=experiment_spec.repository_revision,
                current_revision=evaluator_revision,
            )
        except ExecutableCompatibilityOperationalError as error:
            raise CandidateWfaOperationalError(
                "Git executable-compatibility verification failed operationally"
            ) from error
        except Exception as error:
            raise CandidateWfaOperationalError(
                "executable-compatibility verification failed unexpectedly"
            ) from error

        if not compatibility.compatible:
            return self._invalid(
                historical_decision,
                "historical fixed executable claim is incompatible with current core",
                evaluator_repository_revision=evaluator_revision,
                dataset_reference_artifact_id=dataset_artifact_id,
                dataset_id=source_identity.dataset_id,
                dataset_fingerprint_value=experiment_spec.dataset_fingerprint,
            )

        try:
            strategy = create_registered_research_strategy(
                plan.strategy_procedure_id,
                inputs.config,
            )
            strategy_cls = get_research_procedure_strategy_class(
                plan.strategy_procedure_id
            )
        except (TypeError, ValueError, RuntimeError):
            return self._invalid(
                historical_decision,
                "registered strategy procedure cannot be reproduced",
                evaluator_repository_revision=evaluator_revision,
                dataset_reference_artifact_id=dataset_artifact_id,
                dataset_id=source_identity.dataset_id,
                dataset_fingerprint_value=experiment_spec.dataset_fingerprint,
            )
        if strategy_cls is None or type(strategy) is not strategy_cls:
            return self._invalid(
                historical_decision,
                "registered strategy procedure resolves to the wrong implementation",
                evaluator_repository_revision=evaluator_revision,
                dataset_reference_artifact_id=dataset_artifact_id,
                dataset_id=source_identity.dataset_id,
                dataset_fingerprint_value=experiment_spec.dataset_fingerprint,
            )
        exact_params = dict(plan.parameter_configuration)
        if strategy.research_parameters() != exact_params:
            return self._invalid(
                historical_decision,
                "current strategy effective parameters differ from fixed candidate",
                evaluator_repository_revision=evaluator_revision,
                dataset_reference_artifact_id=dataset_artifact_id,
                dataset_id=source_identity.dataset_id,
                dataset_fingerprint_value=experiment_spec.dataset_fingerprint,
            )

        known_dataset = self._dataset_known_fields(
            evaluator_repository_revision=evaluator_revision,
            dataset_reference_artifact_id=dataset_artifact_id,
            dataset_id=source_identity.dataset_id,
            dataset_fingerprint_value=experiment_spec.dataset_fingerprint,
        )

        try:
            retrieval = self.retrieval_service.retrieve(
                inputs.dataset_context,
                plan.trial_range,
                instrument_id=plan.instrument_id,
                provider=inputs.provider,
                price_adjustment_basis=inputs.price_adjustment_basis,
            )
        except IncompleteHistoricalCoverageError:
            return self._insufficient(
                historical_decision,
                "authoritative historical retrieval is incomplete for WFA",
                **known_dataset,
            )
        except Exception as error:
            if _is_operational_failure(error) or isinstance(
                error,
                (ConnectionError, TimeoutError),
            ):
                raise CandidateWfaOperationalError(
                    "authoritative historical retrieval failed operationally"
                ) from error
            if isinstance(error, (TypeError, ValueError)):
                return self._invalid(
                    historical_decision,
                    "authoritative historical retrieval returned invalid data/evidence",
                    **known_dataset,
                )
            raise CandidateWfaOperationalError(
                "authoritative historical retrieval failed unexpectedly"
            ) from error

        candles = list(retrieval.candles)
        try:
            current_identity = DatasetIdentityV2(
                instrument_id=plan.instrument_id,
                requested_range=plan.trial_range,
                timeframe=plan.timeframe,
                timezone=plan.timezone,
                price_adjustment_basis=inputs.price_adjustment_basis,
                candles=candles,
            )
            legacy_dataset_fingerprint = dataset_fingerprint(
                inputs.dataset_context,
                plan.trial_range,
                candles,
            )
        except (TypeError, ValueError):
            return self._invalid(
                historical_decision,
                "retrieved historical candles cannot form canonical dataset identity",
                **known_dataset,
            )

        if (
            current_identity.dataset_id != source_identity.dataset_id
            or current_identity.instrument_id != source_identity.instrument_id
            or current_identity.requested_range != source_identity.requested_range
            or current_identity.timeframe != source_identity.timeframe
            or current_identity.timezone != source_identity.timezone
            or current_identity.price_adjustment_basis
            is not source_identity.price_adjustment_basis
            or current_identity.candles != source_identity.candles
            or legacy_dataset_fingerprint != experiment_spec.dataset_fingerprint
        ):
            return self._invalid(
                historical_decision,
                "WFA retrieval does not reproduce the admitted historical dataset",
                **known_dataset,
            )

        try:
            current_manifest = build_backtest_run_manifest(
                inputs.dataset_context,
                plan.trial_range,
                legacy_dataset_fingerprint,
                strategy,
                initial_capital=inputs.config.initial_capital,
                runtime_context=inputs.runtime_context,
            )
            historical_manifest_payload = self._load_historical_manifest_payload(
                experiment_spec
            )
        except Exception as error:
            if _is_deterministic_evidence_failure(error):
                return self._invalid(
                    historical_decision,
                    "historical Backtest manifest is invalid",
                    **known_dataset,
                )
            raise CandidateWfaOperationalError(
                "historical Backtest manifest could not be read reliably"
            ) from error

        if (
            backtest_run_manifest_payload(current_manifest)
            != historical_manifest_payload
            or backtest_configuration_fingerprint_v2(current_manifest)
            != experiment_spec.configuration_fingerprint
        ):
            return self._invalid(
                historical_decision,
                "current executable inputs do not reproduce historical configuration",
                **known_dataset,
            )

        generator = WalkForwardWindowGenerator(
            in_sample_bars=self._wfa_configuration["in_sample_bars"],
            out_sample_bars=self._wfa_configuration["out_sample_bars"],
            step_bars=self._wfa_configuration["step_bars"],
            mode=self._wfa_configuration["mode"],
        )
        runner = WalkForwardRunner(
            window_generator=generator,
            optimizer=GridSearchOptimizer(),
            metrics=WalkForwardMetrics(),
        )
        param_space = [exact_params]
        try:
            resolved_prehistory_bars = runner._required_prehistory_bars(
                strategy_cls=strategy_cls,
                param_space=param_space,
            )
            expected_windows = tuple(
                generator.generate(
                    candles,
                    prehistory_bars=resolved_prehistory_bars,
                )
            )
        except Exception as error:
            if _is_deterministic_evidence_failure(error):
                return self._invalid(
                    historical_decision,
                    "fixed strategy WFA prehistory/window contract is invalid",
                    **known_dataset,
                )
            raise CandidateWfaOperationalError(
                "fixed strategy WFA prehistory/window resolution failed unexpectedly"
            ) from error

        if not expected_windows:
            return self._insufficient(
                historical_decision,
                "historical dataset has insufficient bars for fixed-strategy WFA",
                **known_dataset,
            )

        try:
            result = runner.run(
                strategy_cls=strategy_cls,
                param_space=param_space,
                candles=candles,
                dataset_context=inputs.dataset_context,
                initial_capital=inputs.config.initial_capital,
                runtime_context=inputs.runtime_context,
            )
        except Exception as error:
            raise CandidateWfaOperationalError(
                "existing WFA execution failed operationally"
            ) from error

        if len(result.windows) != len(expected_windows):
            return self._invalid(
                historical_decision,
                "returned WFA windows differ from warm-up-aware expected windows",
                **known_dataset,
            )
        for expected, returned in zip(expected_windows, result.windows):
            evaluations = tuple(returned.optimization_result.evaluations)
            if (
                expected.window_index != returned.window_index
                or dict(returned.best_params) != exact_params
                or dict(returned.optimization_result.best_params) != exact_params
                or len(evaluations) != 1
                or dict(evaluations[0].params) != exact_params
            ):
                return self._invalid(
                    historical_decision,
                    "WFA altered or ambiguously selected the fixed strategy parameters",
                    **known_dataset,
                )

        if result.verdict not in {"PASS", "FAIL"}:
            return self._invalid(
                historical_decision,
                "existing WFA engine returned an unsupported verdict",
                **known_dataset,
            )

        try:
            payload = candidate_wfa_result_bytes(
                study_revision_id=plan.study_revision_id,
                trial_id=plan.trial_id,
                candidate_revision_id=candidate.candidate_revision_id,
                historical_qualification_decision_id=historical_decision.decision_id,
                historical_experiment_spec_id=experiment_spec.experiment_spec_id,
                source_dataset_reference_artifact_id=dataset_artifact_id,
                source_dataset_id=source_identity.dataset_id,
                dataset_fingerprint=legacy_dataset_fingerprint,
                requested_range=plan.trial_range,
                instrument_id=plan.instrument_id,
                timeframe=plan.timeframe,
                timezone=plan.timezone,
                strategy_procedure_id=plan.strategy_procedure_id,
                strategy_parameters=exact_params,
                initial_capital=inputs.config.initial_capital,
                risk_economic_configuration=plan.risk_economic_configuration,
                data_treatment_basis=plan.data_treatment_basis,
                wfa_configuration=self._wfa_configuration,
                wfa_configuration_fingerprint=(
                    self._wfa_configuration_fingerprint
                ),
                resolved_prehistory_bars=resolved_prehistory_bars,
                expected_windows=expected_windows,
                result=result,
                evaluator_repository_revision=evaluator_revision,
            )
        except (TypeError, ValueError, OverflowError):
            return self._invalid(
                historical_decision,
                "existing WFA result contains invalid/non-canonical evidence",
                **known_dataset,
            )

        try:
            artifact = self.artifact_store.persist_bytes(
                payload,
                artifact_kind=ResearchArtifactKind.WFA_RESULT,
                schema_id=CANDIDATE_WFA_RESULT_SCHEMA_ID,
                created_at=self._clock(),
            )
            artifact = self.catalog_store.save_artifact(artifact)
            reloaded_artifact = self.catalog_store.load_artifact(
                artifact.artifact_id
            )
            reloaded_payload = self.artifact_store.load_bytes(
                artifact.artifact_id
            )
        except Exception as error:
            raise CandidateWfaOperationalError(
                "candidate-bound WFA result artifact could not be durably persisted"
            ) from error

        if (
            reloaded_artifact != artifact
            or reloaded_payload != payload
            or artifact.artifact_kind is not ResearchArtifactKind.WFA_RESULT
            or artifact.schema_id != CANDIDATE_WFA_RESULT_SCHEMA_ID
        ):
            raise CandidateWfaOperationalError(
                "candidate-bound WFA result artifact read-back mismatch"
            )

        outcome = self._qualification_outcome_for_verdict(
            result.verdict
        )
        return self._append_decision(
            historical_decision=historical_decision,
            validity=WfaEvidenceValidity.VALID,
            outcome=outcome,
            reason=(
                "existing WFA verdict PASS makes exact fixed strategy WFA eligible"
                if result.verdict == "PASS"
                else "existing WFA verdict FAIL rejects exact fixed strategy for qualified Paper"
            ),
            evaluator_repository_revision=evaluator_revision,
            dataset_reference_artifact_id=dataset_artifact_id,
            dataset_id=source_identity.dataset_id,
            dataset_fingerprint_value=legacy_dataset_fingerprint,
            result_artifact_id=artifact.artifact_id,
            wfa_verdict=result.verdict,
        )

    def evaluate_study_revision(
        self,
        study_revision_id: str,
        *,
        observed_eligible_decisions=None,
    ) -> tuple[CandidateWfaDecision, ...]:
        if not isinstance(study_revision_id, str) or not study_revision_id:
            raise ValueError("study_revision_id must be a non-empty string")

        try:
            trials = self.catalog_store.list_registered_trials_for_revision(
                study_revision_id
            )
        except Exception as error:
            raise CandidateWfaOperationalError(
                "authoritative Trial population could not be loaded"
            ) from error

        if observed_eligible_decisions is None:
            try:
                eligible_decisions = (
                    self.qualification_store.list_current_eligible_decisions(
                        study_revision_id
                    )
                )
            except Exception as error:
                raise CandidateWfaOperationalError(
                    "current historical qualification authority could not be loaded"
                ) from error
        else:
            eligible_decisions = tuple(observed_eligible_decisions)
            if any(
                decision.study_revision_id != study_revision_id
                or decision.outcome is not QualificationOutcome.ELIGIBLE
                or decision.candidate_revision_id is None
                for decision in eligible_decisions
            ):
                raise CandidateWfaOperationalError(
                    "observed historical qualification authority is inconsistent"
                )

        trials_by_id = {trial.trial_id: trial for trial in trials}
        results = []
        for historical_decision in eligible_decisions:
            trial = trials_by_id.get(historical_decision.trial_id)
            if trial is None:
                raise CandidateWfaOperationalError(
                    "current eligible decision is outside authoritative Trial population"
                )
            results.append(
                self._evaluate_one(
                    historical_decision,
                    trial,
                )
            )
        return tuple(results)
