"""M9.7 admission and persistence service for qualified Paper campaigns."""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import sqlite3
from uuid import uuid4

from core.market_data.instrument_registry import StaticInstrumentRegistry
from core.market_data.provider_instrument_binding import ProviderInstrumentBinding
from core.paper_trading.paper_trading_snapshot import PaperTradingSnapshot
from core.research.claimed_trial_execution_inputs import (
    ClaimedTrialExecutionInputs,
    ClaimedTrialInputValidationError,
    snapshot_claimed_trial_execution_inputs,
    validate_claimed_trial_execution_inputs,
)
from core.research.executable_compatibility import (
    ExecutableCompatibilityOperationalError,
)
from core.research.models.paper_campaign import (
    PAPER_CAMPAIGN_CONFIG_SCHEMA_ID,
    PaperCampaign,
    PaperCampaignHistory,
    PaperCampaignSession,
    PaperCampaignSessionState,
)
from core.research.models.qualification import QualificationOutcome
from core.research.models.research_catalog import (
    ComputationKind,
    ResearchArtifactKind,
)
from core.research.models.wfa_qualification import (
    CANDIDATE_WFA_RESULT_SCHEMA_ID,
    WfaEvidenceValidity,
    WfaQualificationOutcome,
    decode_candidate_wfa_result_bytes,
)
from core.research.reproducibility import canonical_fingerprint
from core.research.sqlite_paper_campaign_store import (
    PaperCampaignAuthorityConflict,
)


Clock = Callable[[], datetime]
CampaignIdFactory = Callable[[], str]
TrialExecutionInputResolver = Callable[
    [object], ClaimedTrialExecutionInputs
]


class QualifiedPaperAdmissionError(ValueError):
    """Candidate or campaign is not currently authorized for qualified Paper."""


class QualifiedPaperOperationalError(RuntimeError):
    """Authoritative state could not be established reliably."""


class PaperCampaignNotFound(LookupError):
    """Requested PaperCampaign does not exist."""


class PaperCampaignLifecycleConflict(RuntimeError):
    """Requested campaign lifecycle action conflicts with durable state."""


_SESSION_GENERATION_UNCHECKED = object()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _campaign_id() -> str:
    return "paper-campaign-" + uuid4().hex


def _require_aware(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


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


def _is_deterministic_authority_failure(error: BaseException) -> bool:
    current = error
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (FileNotFoundError, TypeError, ValueError)):
            return True
        current = current.__cause__ or current.__context__
    return False


@dataclass(frozen=True)
class QualifiedPaperCampaignAuthority:
    campaign: PaperCampaign | None
    candidate: object
    wfa_decision: object
    historical_decision: object
    trial: object
    plan: object
    execution_inputs: ClaimedTrialExecutionInputs
    evaluator_repository_revision: str
    configuration_fingerprint: str


@dataclass(frozen=True)
class QualifiedPaperSessionAuthority:
    campaign_authority: QualifiedPaperCampaignAuthority
    live_binding: ProviderInstrumentBinding
    observed_at: datetime


class QualifiedPaperCampaignService:
    """Admit exact WFA-qualified candidates and persist Paper campaign history."""

    def __init__(
        self,
        *,
        catalog_store,
        artifact_store,
        qualification_store,
        wfa_store,
        campaign_store,
        plan_resolver,
        execution_input_resolver: TrialExecutionInputResolver,
        software_identity_provider,
        executable_compatibility_checker,
        instrument_registry: StaticInstrumentRegistry,
        clock: Clock | None = None,
        campaign_id_factory: CampaignIdFactory | None = None,
    ) -> None:
        if not callable(execution_input_resolver):
            raise TypeError("execution_input_resolver must be callable")
        if not isinstance(instrument_registry, StaticInstrumentRegistry):
            raise TypeError("instrument_registry must be a StaticInstrumentRegistry")
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable or None")
        if campaign_id_factory is not None and not callable(campaign_id_factory):
            raise TypeError("campaign_id_factory must be callable or None")

        self.catalog_store = catalog_store
        self.artifact_store = artifact_store
        self.qualification_store = qualification_store
        self.wfa_store = wfa_store
        self.campaign_store = campaign_store
        self.plan_resolver = plan_resolver
        self.execution_input_resolver = execution_input_resolver
        self.software_identity_provider = software_identity_provider
        self.executable_compatibility_checker = executable_compatibility_checker
        self.instrument_registry = instrument_registry
        self._clock = clock or _utc_now
        self._campaign_id_factory = campaign_id_factory or _campaign_id

    def _load_exact_software_identity(self):
        try:
            identity = self.software_identity_provider.resolve()
        except Exception as error:
            raise QualifiedPaperOperationalError(
                "current executable software identity could not be resolved"
            ) from error

        revision = getattr(identity, "repository_revision", None)
        clean = getattr(identity, "worktree_clean", None)
        if revision is None or clean is None:
            raise QualifiedPaperOperationalError(
                "current executable software identity is unavailable operationally"
            )
        if clean is not True:
            raise QualifiedPaperAdmissionError(
                "current executable worktree is not clean"
            )
        return identity

    def _validate_wfa_artifact(
        self,
        *,
        decision,
        candidate,
        plan,
        inputs: ClaimedTrialExecutionInputs,
    ) -> None:
        if decision.result_artifact_id is None:
            raise QualifiedPaperAdmissionError(
                "WFA-eligible decision lacks result artifact"
            )

        try:
            artifact = self.catalog_store.load_artifact(
                decision.result_artifact_id
            )
        except Exception as error:
            if _is_operational_failure(error):
                raise QualifiedPaperOperationalError(
                    "WFA result artifact metadata could not be read reliably"
                ) from error
            if _is_deterministic_authority_failure(error):
                raise QualifiedPaperAdmissionError(
                    "WFA result artifact metadata is invalid"
                ) from error
            raise QualifiedPaperOperationalError(
                "WFA result artifact metadata read failed unexpectedly"
            ) from error

        if artifact is None:
            raise QualifiedPaperAdmissionError(
                "WFA result artifact metadata is missing"
            )
        if (
            artifact.artifact_kind is not ResearchArtifactKind.WFA_RESULT
            or artifact.schema_id != CANDIDATE_WFA_RESULT_SCHEMA_ID
        ):
            raise QualifiedPaperAdmissionError(
                "WFA result artifact has wrong kind or schema"
            )

        try:
            payload_bytes = self.artifact_store.load_bytes(
                artifact.artifact_id
            )
        except Exception as error:
            if _is_operational_failure(error):
                raise QualifiedPaperOperationalError(
                    "WFA result artifact bytes could not be read reliably"
                ) from error
            raise QualifiedPaperAdmissionError(
                "WFA result artifact bytes are missing or contradictory"
            ) from error

        if len(payload_bytes) != artifact.byte_count:
            raise QualifiedPaperAdmissionError(
                "WFA result artifact byte count mismatch"
            )

        try:
            payload = decode_candidate_wfa_result_bytes(payload_bytes)
        except Exception as error:
            if _is_operational_failure(error):
                raise QualifiedPaperOperationalError(
                    "WFA result artifact could not be decoded reliably"
                ) from error
            raise QualifiedPaperAdmissionError(
                "WFA result artifact is not valid canonical M9.6 evidence"
            ) from error

        expected = {
            "study_revision_id": decision.study_revision_id,
            "trial_id": decision.trial_id,
            "candidate_revision_id": decision.candidate_revision_id,
            "historical_qualification_decision_id": (
                decision.historical_qualification_decision_id
            ),
            "historical_experiment_spec_id": (
                candidate.experiment_spec_id
            ),
            "source_dataset_reference_artifact_id": (
                decision.dataset_reference_artifact_id
            ),
            "source_dataset_id": decision.dataset_id,
            "dataset_fingerprint": decision.dataset_fingerprint,
            "instrument_id": plan.instrument_id,
            "timeframe": plan.timeframe,
            "timezone": plan.timezone,
            "strategy_procedure_id": plan.strategy_procedure_id,
            "initial_capital": inputs.config.initial_capital,
            "wfa_configuration_fingerprint": (
                decision.wfa_configuration_fingerprint
            ),
            "evaluator_repository_revision": (
                decision.evaluator_repository_revision
            ),
            "verdict": decision.wfa_verdict,
        }
        if any(
            payload.get(key) != value
            for key, value in expected.items()
        ):
            raise QualifiedPaperAdmissionError(
                "WFA result artifact contradicts current WFA/candidate lineage"
            )

        requested_range = payload.get("requested_range")
        if (
            not isinstance(requested_range, dict)
            or requested_range.get("start") != plan.trial_range.start
            or requested_range.get("end") != plan.trial_range.end
            or payload.get("strategy_parameters")
            != dict(plan.parameter_configuration)
            or payload.get("risk_economic_configuration")
            != dict(plan.risk_economic_configuration)
            or payload.get("data_treatment_basis")
            != dict(plan.data_treatment_basis)
        ):
            raise QualifiedPaperAdmissionError(
                "WFA result artifact does not describe the exact registered candidate inputs"
            )

    @staticmethod
    def _configuration_fingerprint(
        *,
        candidate,
        wfa_decision,
        plan,
        inputs: ClaimedTrialExecutionInputs,
    ) -> str:
        payload = {
            "candidate_revision_id": candidate.candidate_revision_id,
            "wfa_decision_id": wfa_decision.decision_id,
            "study_revision_id": candidate.study_revision_id,
            "trial_id": candidate.trial_id,
            "experiment_spec_id": candidate.experiment_spec_id,
            "strategy_procedure_id": plan.strategy_procedure_id,
            "instrument_id": plan.instrument_id,
            "symbol": inputs.dataset_context.symbol,
            "timeframe": inputs.dataset_context.timeframe,
            "timezone": inputs.dataset_context.timezone,
            "initial_capital": inputs.config.initial_capital,
            "parameter_configuration": dict(plan.parameter_configuration),
            "risk_economic_configuration": dict(
                inputs.risk_economic_configuration
            ),
            "data_treatment_basis": dict(inputs.data_treatment_basis),
            "historical_provider": inputs.provider,
            "price_adjustment_basis": inputs.price_adjustment_basis.value,
            "registered_repository_revision": plan.repository_revision,
        }
        return canonical_fingerprint(
            payload,
            schema=PAPER_CAMPAIGN_CONFIG_SCHEMA_ID,
        )

    def _resolve_candidate_authority(
        self,
        candidate_revision_id: str,
    ) -> QualifiedPaperCampaignAuthority:
        try:
            candidate = self.qualification_store.load_candidate_revision(
                candidate_revision_id
            )
            wfa_decision = self.wfa_store.load_current_decision(
                candidate_revision_id
            )
        except Exception as error:
            if _is_operational_failure(error):
                raise QualifiedPaperOperationalError(
                    "candidate/WFA authority could not be read reliably"
                ) from error
            if _is_deterministic_authority_failure(error):
                raise QualifiedPaperAdmissionError(
                    "candidate/WFA authority is invalid"
                ) from error
            raise QualifiedPaperOperationalError(
                "candidate/WFA authority read failed unexpectedly"
            ) from error

        if candidate is None:
            raise QualifiedPaperAdmissionError("CandidateRevision does not exist")
        if wfa_decision is None:
            raise QualifiedPaperAdmissionError(
                "CandidateRevision has no current WFA decision"
            )
        if (
            wfa_decision.evidence_validity is not WfaEvidenceValidity.VALID
            or wfa_decision.wfa_verdict != "PASS"
            or wfa_decision.outcome is not WfaQualificationOutcome.ELIGIBLE
        ):
            raise QualifiedPaperAdmissionError(
                "CandidateRevision is not currently WFA eligible"
            )
        if (
            wfa_decision.candidate_revision_id != candidate.candidate_revision_id
            or wfa_decision.study_revision_id != candidate.study_revision_id
            or wfa_decision.trial_id != candidate.trial_id
        ):
            raise QualifiedPaperAdmissionError(
                "current WFA decision contradicts CandidateRevision lineage"
            )

        try:
            historical_decision = self.qualification_store.load_current_decision(
                candidate.trial_id
            )
        except Exception as error:
            if _is_operational_failure(error):
                raise QualifiedPaperOperationalError(
                    "current historical qualification authority could not be read reliably"
                ) from error
            if _is_deterministic_authority_failure(error):
                raise QualifiedPaperAdmissionError(
                    "current historical qualification authority is invalid"
                ) from error
            raise QualifiedPaperOperationalError(
                "current historical qualification authority read failed unexpectedly"
            ) from error
        if (
            historical_decision is None
            or historical_decision.outcome is not QualificationOutcome.ELIGIBLE
            or historical_decision.candidate_revision_id
            != candidate.candidate_revision_id
            or historical_decision.decision_id
            != wfa_decision.historical_qualification_decision_id
        ):
            raise QualifiedPaperAdmissionError(
                "WFA eligibility no longer rests on current historical qualification"
            )

        try:
            trial = self.catalog_store.load_trial(candidate.trial_id)
            experiment_spec = self.catalog_store.load_experiment_spec(
                candidate.experiment_spec_id
            )
        except Exception as error:
            if _is_operational_failure(error):
                raise QualifiedPaperOperationalError(
                    "registered candidate lineage could not be read reliably"
                ) from error
            if _is_deterministic_authority_failure(error):
                raise QualifiedPaperAdmissionError(
                    "registered candidate lineage is invalid"
                ) from error
            raise QualifiedPaperOperationalError(
                "registered candidate lineage read failed unexpectedly"
            ) from error
        if trial is None or experiment_spec is None:
            raise QualifiedPaperAdmissionError(
                "registered candidate lineage is incomplete"
            )

        try:
            plan = self.plan_resolver.resolve(candidate.trial_id)
        except Exception as error:
            if _is_operational_failure(error):
                raise QualifiedPaperOperationalError(
                    "registered candidate plan could not be read reliably"
                ) from error
            if _is_deterministic_authority_failure(error):
                raise QualifiedPaperAdmissionError(
                    "registered candidate plan is missing or contradictory"
                ) from error
            raise QualifiedPaperOperationalError(
                "registered candidate plan resolution failed unexpectedly"
            ) from error
        if (
            trial.study_revision_id != candidate.study_revision_id
            or trial.trial_id != candidate.trial_id
            or trial.experiment_spec_id != candidate.experiment_spec_id
            or trial.parameter_configuration_fingerprint
            != candidate.parameter_configuration_fingerprint
            or plan.study_revision_id != candidate.study_revision_id
            or plan.trial_id != candidate.trial_id
            or experiment_spec.computation_kind is not ComputationKind.BACKTEST
            or experiment_spec.experiment_spec_id != candidate.experiment_spec_id
            or experiment_spec.repository_revision != plan.repository_revision
        ):
            raise QualifiedPaperAdmissionError(
                "registered Trial/ExperimentSpec/plan contradicts CandidateRevision"
            )

        try:
            inputs = self.execution_input_resolver(plan)
            if not isinstance(inputs, ClaimedTrialExecutionInputs):
                raise TypeError(
                    "execution_input_resolver must return ClaimedTrialExecutionInputs"
                )
            inputs = snapshot_claimed_trial_execution_inputs(inputs)
            validate_claimed_trial_execution_inputs(plan, inputs)
        except Exception as error:
            if _is_operational_failure(error):
                raise QualifiedPaperOperationalError(
                    "registered candidate executable inputs could not be resolved reliably"
                ) from error
            if isinstance(error, ClaimedTrialInputValidationError) or (
                _is_deterministic_authority_failure(error)
            ):
                raise QualifiedPaperAdmissionError(
                    "registered candidate executable inputs cannot be reproduced exactly"
                ) from error
            raise QualifiedPaperOperationalError(
                "registered candidate executable input resolution failed unexpectedly"
            ) from error

        if inputs.config.timeframe not in {"5m", "15m"}:
            raise QualifiedPaperAdmissionError(
                "qualified Paper MVP supports only the certified 5m and 15m timeframes"
            )
        if inputs.dataset_context.timezone != "Asia/Kolkata":
            raise QualifiedPaperAdmissionError(
                "qualified Paper MVP supports only Asia/Kolkata candidate time semantics"
            )
        if inputs.provider != "angelone":
            raise QualifiedPaperAdmissionError(
                "qualified Paper MVP requires the registered AngelOne data provider"
            )

        self._validate_wfa_artifact(
            decision=wfa_decision,
            candidate=candidate,
            plan=plan,
            inputs=inputs,
        )
        software_identity = self._load_exact_software_identity()
        try:
            compatibility = self.executable_compatibility_checker.check(
                historical_revision=experiment_spec.repository_revision,
                current_revision=software_identity.repository_revision,
            )
        except ExecutableCompatibilityOperationalError as error:
            raise QualifiedPaperOperationalError(
                "executable compatibility could not be established"
            ) from error
        except Exception as error:
            if _is_operational_failure(error):
                raise QualifiedPaperOperationalError(
                    "executable compatibility check failed operationally"
                ) from error
            if _is_deterministic_authority_failure(error):
                raise QualifiedPaperAdmissionError(
                    "fixed CandidateRevision executable compatibility is invalid"
                ) from error
            raise QualifiedPaperOperationalError(
                "executable compatibility check failed unexpectedly"
            ) from error
        if not compatibility.compatible:
            raise QualifiedPaperAdmissionError(
                "fixed CandidateRevision executable core changed after registration"
            )

        configuration_fingerprint = self._configuration_fingerprint(
            candidate=candidate,
            wfa_decision=wfa_decision,
            plan=plan,
            inputs=inputs,
        )
        return QualifiedPaperCampaignAuthority(
            campaign=None,
            candidate=candidate,
            wfa_decision=wfa_decision,
            historical_decision=historical_decision,
            trial=trial,
            plan=plan,
            execution_inputs=inputs,
            evaluator_repository_revision=(
                software_identity.repository_revision
            ),
            configuration_fingerprint=configuration_fingerprint,
        )

    def create_campaign(self, candidate_revision_id: str) -> PaperCampaign:
        authority = self._resolve_candidate_authority(candidate_revision_id)
        campaign = PaperCampaign(
            campaign_id=self._campaign_id_factory(),
            created_at=self._clock(),
            candidate_revision_id=authority.candidate.candidate_revision_id,
            wfa_decision_id=authority.wfa_decision.decision_id,
            study_revision_id=authority.candidate.study_revision_id,
            trial_id=authority.candidate.trial_id,
            experiment_spec_id=authority.candidate.experiment_spec_id,
            parameter_configuration_fingerprint=(
                authority.candidate.parameter_configuration_fingerprint
            ),
            configuration_fingerprint=authority.configuration_fingerprint,
            created_repository_revision=(
                authority.evaluator_repository_revision
            ),
        )
        try:
            return self.campaign_store.create_campaign(campaign)
        except PaperCampaignAuthorityConflict as error:
            raise QualifiedPaperAdmissionError(str(error)) from error
        except Exception as error:
            if _is_operational_failure(error):
                raise QualifiedPaperOperationalError(
                    "qualified Paper campaign could not be persisted reliably"
                ) from error
            raise

    def create_or_reuse_campaign(
        self,
        candidate_revision_id: str,
    ) -> tuple[PaperCampaign, bool]:
        authority = self._resolve_candidate_authority(candidate_revision_id)
        campaign = PaperCampaign(
            campaign_id=self._campaign_id_factory(),
            created_at=self._clock(),
            candidate_revision_id=authority.candidate.candidate_revision_id,
            wfa_decision_id=authority.wfa_decision.decision_id,
            study_revision_id=authority.candidate.study_revision_id,
            trial_id=authority.candidate.trial_id,
            experiment_spec_id=authority.candidate.experiment_spec_id,
            parameter_configuration_fingerprint=(
                authority.candidate.parameter_configuration_fingerprint
            ),
            configuration_fingerprint=authority.configuration_fingerprint,
            created_repository_revision=(
                authority.evaluator_repository_revision
            ),
        )
        try:
            return self.campaign_store.create_or_load_matching_campaign(campaign)
        except PaperCampaignAuthorityConflict as error:
            raise QualifiedPaperAdmissionError(str(error)) from error
        except Exception as error:
            if _is_operational_failure(error):
                raise QualifiedPaperOperationalError(
                    "qualified Paper campaign could not be persisted reliably"
                ) from error
            raise

    def list_campaigns_for_study(
        self,
        study_id: str,
    ) -> tuple[PaperCampaign, ...]:
        return self.campaign_store.list_campaigns_for_study(study_id)

    def list_campaigns_for_candidate(
        self,
        candidate_revision_id: str,
    ) -> tuple[PaperCampaign, ...]:
        return self.campaign_store.list_campaigns_for_candidate(
            candidate_revision_id
        )

    def campaign_is_current(
        self,
        campaign_id: str,
    ) -> bool:
        try:
            self._load_campaign_authority(campaign_id)
        except QualifiedPaperAdmissionError:
            return False
        return True

    def _load_campaign_authority(
        self,
        campaign_id: str,
    ) -> QualifiedPaperCampaignAuthority:
        campaign = self.campaign_store.load_campaign(campaign_id)
        if campaign is None:
            raise PaperCampaignNotFound(campaign_id)
        authority = self._resolve_candidate_authority(
            campaign.candidate_revision_id
        )
        if (
            authority.wfa_decision.decision_id != campaign.wfa_decision_id
            or authority.candidate.study_revision_id != campaign.study_revision_id
            or authority.candidate.trial_id != campaign.trial_id
            or authority.candidate.experiment_spec_id != campaign.experiment_spec_id
            or authority.candidate.parameter_configuration_fingerprint
            != campaign.parameter_configuration_fingerprint
            or authority.configuration_fingerprint
            != campaign.configuration_fingerprint
        ):
            raise QualifiedPaperAdmissionError(
                "PaperCampaign no longer matches current qualified candidate authority"
            )
        return QualifiedPaperCampaignAuthority(
            campaign=campaign,
            candidate=authority.candidate,
            wfa_decision=authority.wfa_decision,
            historical_decision=authority.historical_decision,
            trial=authority.trial,
            plan=authority.plan,
            execution_inputs=authority.execution_inputs,
            evaluator_repository_revision=(
                authority.evaluator_repository_revision
            ),
            configuration_fingerprint=authority.configuration_fingerprint,
        )

    def _resolve_live_binding(
        self,
        *,
        instrument_id: str,
        observed_at: datetime,
    ) -> ProviderInstrumentBinding:
        _require_aware(observed_at, "observed_at")
        candidates = []
        for binding in self.instrument_registry.bindings_for(
            instrument_id=instrument_id,
            provider="angelone",
        ):
            for boundary in (binding.effective_from, binding.effective_to):
                if boundary is not None and (
                    boundary.utcoffset() is None
                    or observed_at.utcoffset() is None
                ):
                    raise QualifiedPaperAdmissionError(
                        "live provider binding timezone awareness is incompatible"
                    )
            if (
                binding.effective_from is not None
                and observed_at < binding.effective_from
            ):
                continue
            if (
                binding.effective_to is not None
                and observed_at >= binding.effective_to
            ):
                continue
            candidates.append(binding)

        if len(candidates) != 1:
            raise QualifiedPaperAdmissionError(
                "exact current AngelOne live binding is missing or ambiguous"
            )
        binding = candidates[0]
        if (
            binding.provider_symbol is None
            or binding.provider_exchange is None
            or binding.provider_exchange.upper() != "NSE"
        ):
            raise QualifiedPaperAdmissionError(
                "qualified Paper requires one explicit NSE AngelOne symbol/token binding"
            )
        return binding

    def prepare_session(
        self,
        campaign_id: str,
    ) -> QualifiedPaperSessionAuthority:
        authority = self._load_campaign_authority(campaign_id)
        observed_at = self._clock()
        binding = self._resolve_live_binding(
            instrument_id=authority.plan.instrument_id,
            observed_at=observed_at,
        )
        if binding.provider_symbol != authority.execution_inputs.dataset_context.symbol:
            raise QualifiedPaperAdmissionError(
                "live provider symbol does not match the registered candidate symbol"
            )
        return QualifiedPaperSessionAuthority(
            campaign_authority=authority,
            live_binding=binding,
            observed_at=observed_at,
        )

    def register_prepared_session(
        self,
        authority: QualifiedPaperSessionAuthority,
        *,
        session_id: str,
        expected_latest_session_id=_SESSION_GENERATION_UNCHECKED,
    ) -> PaperCampaignSession:
        campaign = authority.campaign_authority.campaign
        if campaign is None:
            raise ValueError("session authority must belong to a persisted campaign")

        current = self.prepare_session(campaign.campaign_id)
        if (
            current.campaign_authority.evaluator_repository_revision
            != authority.campaign_authority.evaluator_repository_revision
            or current.campaign_authority.configuration_fingerprint
            != authority.campaign_authority.configuration_fingerprint
            or current.live_binding != authority.live_binding
        ):
            raise QualifiedPaperAdmissionError(
                "qualified Paper authority changed during session preparation"
            )

        session = PaperCampaignSession(
            session_id=session_id,
            campaign_id=campaign.campaign_id,
            created_at=self._clock(),
            evaluator_repository_revision=(
                authority.campaign_authority.evaluator_repository_revision
            ),
            live_binding_id=authority.live_binding.binding_id,
            live_provider=authority.live_binding.provider,
            live_provider_instrument_id=(
                authority.live_binding.provider_instrument_id
            ),
            live_provider_symbol=authority.live_binding.provider_symbol,
            state=PaperCampaignSessionState.CREATED,
        )
        try:
            if expected_latest_session_id is _SESSION_GENERATION_UNCHECKED:
                self.campaign_store.register_session(session)
            else:
                self.campaign_store.register_session(
                    session,
                    expected_latest_session_id=expected_latest_session_id,
                )
        except PaperCampaignAuthorityConflict as error:
            raise QualifiedPaperAdmissionError(str(error)) from error
        except Exception as error:
            if _is_operational_failure(error):
                raise QualifiedPaperOperationalError(
                    "qualified Paper session could not be registered reliably"
                ) from error
            raise
        return session

    def mark_session_running(self, session_id: str) -> PaperCampaignSession:
        return self.campaign_store.mark_running_if_created(
            session_id,
            started_at=self._clock(),
        )

    @staticmethod
    def _snapshot_json(snapshot: PaperTradingSnapshot) -> str:
        return json.dumps(
            asdict(snapshot),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    def terminalize_snapshot(
        self,
        snapshot: PaperTradingSnapshot,
    ) -> PaperCampaignSession:
        if not isinstance(snapshot, PaperTradingSnapshot):
            raise TypeError("snapshot must be a PaperTradingSnapshot")
        if snapshot.status not in {"STOPPED", "FAILED"}:
            raise ValueError("terminal Paper snapshot must be STOPPED or FAILED")

        existing = self.campaign_store.load_session(snapshot.session_id)
        if existing is None:
            raise QualifiedPaperOperationalError(
                "terminal Paper snapshot has no durable campaign session"
            )
        state = (
            PaperCampaignSessionState.STOPPED
            if snapshot.status == "STOPPED"
            else PaperCampaignSessionState.FAILED
        )
        failure_type = None
        failure_message = None
        if state is PaperCampaignSessionState.FAILED:
            if (
                not snapshot.failure_type
                or snapshot.failure_message is None
            ):
                raise QualifiedPaperOperationalError(
                    "FAILED Paper snapshot lacks authoritative failure detail"
                )
            failure_type = snapshot.failure_type
            failure_message = snapshot.failure_message

        try:
            snapshot_json = self._snapshot_json(snapshot)
        except (TypeError, ValueError) as error:
            raise QualifiedPaperOperationalError(
                "terminal Paper snapshot is not durably serializable"
            ) from error

        return self.campaign_store.terminalize_session(
            snapshot.session_id,
            state=state,
            terminal_at=self._clock(),
            terminal_snapshot_json=snapshot_json,
            failure_type=failure_type,
            failure_message=failure_message,
        )

    def fail_prepared_session(
        self,
        session_id: str,
        error: Exception,
    ) -> PaperCampaignSession:
        message = str(error).strip() or type(error).__name__
        return self.campaign_store.terminalize_session(
            session_id,
            state=PaperCampaignSessionState.FAILED,
            terminal_at=self._clock(),
            terminal_snapshot_json=None,
            failure_type=type(error).__name__,
            failure_message=message[:1000],
        )

    def active_session(self) -> PaperCampaignSession | None:
        return self.campaign_store.load_active_session()

    def history(self, campaign_id: str) -> PaperCampaignHistory:
        history = self.campaign_store.load_history(campaign_id)
        if history is None:
            raise PaperCampaignNotFound(campaign_id)
        return history

    def recover_after_application_restart(self) -> int:
        return self.campaign_store.recover_incomplete_sessions(
            terminal_at=self._clock()
        )
