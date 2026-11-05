"""SQLite persistence for append-only candidate-bound M9.6 WFA decisions."""

from contextlib import closing
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import sqlite3

from core.config.walk_forward_config import WALK_FORWARD_CONFIG
from core.market_data.historical_coverage import TimeRange
from core.research.executable_compatibility import (
    ExecutableCompatibilityOperationalError,
    GitHistoricalExecutableCompatibilityChecker,
)
from core.research.models.dataset_reference import (
    DATASET_REFERENCE_SCHEMA_ID,
    decode_dataset_reference_bytes,
)
from core.research.models.research_catalog import (
    ComputationKind,
    ResearchArtifactKind,
)
from core.research.models.qualification import FixedCandidateRevision
from core.research.models.qualification_policy import QualificationPolicy
from core.research.models.wfa_qualification import (
    CANDIDATE_WFA_RESULT_SCHEMA_ID,
    CandidateWfaDecision,
    WfaEvidenceValidity,
    WfaQualificationOutcome,
    decode_candidate_wfa_result_bytes,
    wfa_window_configuration_fingerprint,
    wfa_window_configuration_payload,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
    research_artifact_reference,
)
from core.research.registered_trial_execution_plan import (
    RegisteredTrialExecutionPlanResolver,
)
from core.research.registered_study_registration import (
    PARAMETER_VARIANT_SCHEMA_ID,
)
from core.research.reproducibility import (
    BACKTEST_CONFIG_V2_SCHEMA,
    BACKTEST_RESULT_SCHEMA,
    BACKTEST_RUN_MANIFEST_SCHEMA,
    canonical_fingerprint,
    dataset_fingerprint,
    decode_canonical_bytes,
    decode_stable_backtest_result_bytes,
)
from core.research.software_identity import GitSoftwareIdentityProvider
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)
from core.research.sqlite_research_evidence_store import (
    SQLiteResearchEvidenceStore,
)
from core.research.sqlite_qualification_store import (
    SQLiteQualificationStore,
)
from core.research.study_aggregation import (
    StudyAggregationError,
    StudyAggregationService,
)
from core.runtime.dataset_context import DatasetContext
from core.strategies.strategy_factory import (
    get_research_procedure_strategy_class,
)
from core.walk_forward.runner import WalkForwardRunner
from core.walk_forward.window_generator import WalkForwardWindowGenerator
from core.research.research_schema import initialize_research_schema


class _ReservedTransactionStudyAggregationService(StudyAggregationService):
    """Reuse a pre-initialized authoritative evidence reader under WFA lock."""

    def __init__(
        self,
        *,
        catalog_store: SQLiteResearchCatalogStore,
        artifact_store: ContentAddressedResearchArtifactStore,
        evidence_store: SQLiteResearchEvidenceStore,
    ):
        super().__init__(
            catalog_store=catalog_store,
            artifact_store=artifact_store,
            evidence_store=evidence_store,
        )
        self._reserved_evidence_store = evidence_store
        self._require_authoritative_database_binding()

    def _require_authoritative_database_binding(self) -> None:
        catalog_path = Path(self.catalog_store.database_path).resolve()
        evidence_path = Path(
            self._reserved_evidence_store.database_path
        ).resolve()
        if evidence_path != catalog_path:
            raise StudyAggregationError(
                "WFA persistence evidence reader must use "
                "the canonical research database"
            )

    def _authoritative_evidence_store(self):
        self._require_authoritative_database_binding()
        return self._reserved_evidence_store


def _sequence_bounds(values) -> dict:
    values = tuple(values)
    return {
        "count": len(values),
        "first_timestamp": (
            values[0].timestamp if values else None
        ),
        "last_timestamp": (
            values[-1].timestamp if values else None
        ),
    }


class SQLiteCandidateWfaStore:
    """Persist and read append-only WFA-stage qualification decisions."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        artifact_store: ContentAddressedResearchArtifactStore,
        software_identity_provider=None,
        executable_compatibility_checker=None,
    ):
        if not isinstance(
            artifact_store,
            ContentAddressedResearchArtifactStore,
        ):
            raise TypeError(
                "artifact_store must be a ContentAddressedResearchArtifactStore"
            )
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.artifact_store = artifact_store
        self.software_identity_provider = (
            software_identity_provider
            if software_identity_provider is not None
            else GitSoftwareIdentityProvider()
        )
        self.executable_compatibility_checker = (
            executable_compatibility_checker
            if executable_compatibility_checker is not None
            else GitHistoricalExecutableCompatibilityChecker()
        )
        with closing(self._connect()) as connection:
            initialize_research_schema(connection)
        self.catalog_store = SQLiteResearchCatalogStore(
            self.database_path
        )
        self.evidence_store = SQLiteResearchEvidenceStore(
            self.database_path
        )
        self.plan_resolver = RegisteredTrialExecutionPlanResolver(
            catalog_store=self.catalog_store,
            artifact_store=self.artifact_store,
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _load_canonical_artifact(
        connection: sqlite3.Connection,
        artifact_id: str,
        *,
        authority_label: str,
    ):
        row = connection.execute(
            """
            SELECT
                artifact_id, artifact_kind, schema_id,
                relative_path, byte_count, created_at
            FROM research_artifacts
            WHERE artifact_id = ?
            """,
            (artifact_id,),
        ).fetchone()
        if row is None:
            return None
        try:
            return SQLiteResearchCatalogStore._artifact_from_row(row)
        except Exception as error:
            raise ValueError(
                f"{authority_label} artifact metadata is malformed"
            ) from error

    def _validate_lineage(
        self,
        connection: sqlite3.Connection,
        decision: CandidateWfaDecision,
        *,
        verified_historical_result_artifact_id: str | None = None,
    ) -> str:
        candidate_row = connection.execute(
            """
            SELECT
                candidate_revision_id,
                study_revision_id,
                trial_id,
                experiment_spec_id,
                parameter_configuration_fingerprint,
                created_at
            FROM fixed_candidate_revisions
            WHERE candidate_revision_id = ?
            """,
            (decision.candidate_revision_id,),
        ).fetchone()
        if candidate_row is None:
            raise ValueError("WFA decision CandidateRevision lineage mismatch")
        try:
            candidate = FixedCandidateRevision(
                candidate_revision_id=candidate_row[0],
                study_revision_id=candidate_row[1],
                trial_id=candidate_row[2],
                experiment_spec_id=candidate_row[3],
                parameter_configuration_fingerprint=candidate_row[4],
                created_at=datetime.fromisoformat(candidate_row[5]),
            )
        except Exception as error:
            raise ValueError(
                "WFA decision CandidateRevision authority is malformed"
            ) from error
        if (
            candidate.candidate_revision_id != decision.candidate_revision_id
            or candidate.study_revision_id != decision.study_revision_id
            or candidate.trial_id != decision.trial_id
        ):
            raise ValueError("WFA decision CandidateRevision lineage mismatch")
        historical_experiment_spec_id = candidate.experiment_spec_id

        historical_row = connection.execute(
            """
            SELECT
                decision_id, created_at, evaluator_version,
                policy_id, policy_version, threshold_text,
                study_revision_id, trial_id, candidate_revision_id,
                attempt_id, evidence_id, result_artifact_id,
                evidence_validity, criterion_outcome, outcome,
                profitable_trade_count, completed_trade_count,
                rate_numerator, rate_denominator, reason
            FROM qualification_decisions
            WHERE decision_id = ?
            """,
            (decision.historical_qualification_decision_id,),
        ).fetchone()
        if historical_row is None:
            raise ValueError(
                "WFA decision requires the exact eligible historical decision"
            )
        try:
            historical_decision = (
                SQLiteQualificationStore._decision_from_row(
                    historical_row
                )
            )
        except Exception as error:
            raise ValueError(
                "WFA decision historical qualification decision is malformed"
            ) from error
        if (
            historical_decision.study_revision_id
            != decision.study_revision_id
            or historical_decision.trial_id != decision.trial_id
            or historical_decision.candidate_revision_id
            != decision.candidate_revision_id
            or historical_decision.outcome.value != "ELIGIBLE"
        ):
            raise ValueError(
                "WFA decision requires the exact eligible historical decision"
            )

        active_policy_row = connection.execute(
            """
            SELECT
                a.policy_id,
                p.version,
                p.threshold_text
            FROM qualification_policy_activations AS a
            LEFT JOIN qualification_policies AS p
              ON p.policy_id = a.policy_id
            ORDER BY a.activation_sequence DESC
            LIMIT 1
            """
        ).fetchone()
        if (
            active_policy_row is None
            or active_policy_row[1] is None
            or active_policy_row[2] is None
        ):
            raise ValueError(
                "WFA decision requires a valid active historical qualification policy"
            )
        try:
            active_policy = QualificationPolicy(
                active_policy_row[1],
                Decimal(active_policy_row[2]),
            )
        except Exception as error:
            raise ValueError(
                "WFA decision active historical qualification policy is invalid"
            ) from error
        if active_policy.policy_id != active_policy_row[0]:
            raise ValueError(
                "WFA decision active historical qualification policy identity is inconsistent"
            )

        current_historical_row = connection.execute(
            """
            SELECT
                decision_id, created_at, evaluator_version,
                policy_id, policy_version, threshold_text,
                study_revision_id, trial_id, candidate_revision_id,
                attempt_id, evidence_id, result_artifact_id,
                evidence_validity, criterion_outcome, outcome,
                profitable_trade_count, completed_trade_count,
                rate_numerator, rate_denominator, reason
            FROM qualification_decisions
            WHERE trial_id = ? AND policy_id = ?
            ORDER BY decision_sequence DESC
            LIMIT 1
            """,
            (decision.trial_id, active_policy.policy_id),
        ).fetchone()
        if current_historical_row is None:
            raise ValueError(
                "WFA decision historical eligibility is no longer current"
            )
        try:
            current_historical_decision = (
                SQLiteQualificationStore._decision_from_row(
                    current_historical_row
                )
            )
        except Exception as error:
            raise ValueError(
                "WFA decision current historical qualification decision is malformed"
            ) from error

        try:
            historical_threshold = Decimal(
                historical_decision.threshold_text
            )
            current_threshold = Decimal(
                current_historical_decision.threshold_text
            )
        except Exception as error:
            raise ValueError(
                "WFA decision historical qualification policy evidence is invalid"
            ) from error

        if (
            historical_decision.policy_id != active_policy.policy_id
            or historical_decision.policy_version != active_policy.version
            or historical_threshold
            != active_policy.net_profitable_trade_rate_threshold_pct
            or current_historical_decision.decision_id
            != decision.historical_qualification_decision_id
            or current_historical_decision.candidate_revision_id
            != decision.candidate_revision_id
            or current_historical_decision.outcome.value != "ELIGIBLE"
            or current_historical_decision.policy_version
            != active_policy.version
            or current_threshold
            != active_policy.net_profitable_trade_rate_threshold_pct
        ):
            raise ValueError(
                "WFA decision historical eligibility is no longer current"
            )

        historical = (
            historical_decision.study_revision_id,
            historical_decision.trial_id,
            historical_decision.candidate_revision_id,
            historical_decision.outcome.value,
            historical_decision.attempt_id,
            historical_decision.evidence_id,
            historical_decision.result_artifact_id,
            historical_decision.policy_id,
            historical_decision.policy_version,
            historical_decision.threshold_text,
        )

        if decision.outcome is WfaQualificationOutcome.INSUFFICIENT:
            if (
                decision.dataset_reference_artifact_id is None
                or decision.dataset_id is None
                or decision.dataset_fingerprint is None
                or historical_decision.evidence_id is None
            ):
                raise ValueError(
                    "INSUFFICIENT WFA decision requires frozen historical dataset authority"
                )

            admission_row = connection.execute(
                """
                SELECT dataset_reference_artifact_id
                FROM qualification_dataset_admissions
                WHERE decision_id = ?
                """,
                (decision.historical_qualification_decision_id,),
            ).fetchone()
            if admission_row != (decision.dataset_reference_artifact_id,):
                raise ValueError(
                    "INSUFFICIENT WFA decision DatasetReference does not match "
                    "the qualification-time admission"
                )

            evidence_row = connection.execute(
                """
                SELECT artifact_references, dataset_fingerprint
                FROM research_evidence
                WHERE evidence_id = ?
                """,
                (historical_decision.evidence_id,),
            ).fetchone()
            if evidence_row is None:
                raise ValueError(
                    "INSUFFICIENT WFA decision historical evidence is missing"
                )
            try:
                references = json.loads(evidence_row[0])
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                raise ValueError(
                    "INSUFFICIENT WFA decision historical evidence references are invalid"
                ) from error
            if not isinstance(references, list):
                raise ValueError(
                    "INSUFFICIENT WFA decision historical evidence references are invalid"
                )

            dataset_reference_ids = []
            for reference_text in references:
                if not (
                    isinstance(reference_text, str)
                    and reference_text.startswith("artifact:sha256:")
                ):
                    continue
                artifact_id = reference_text.removeprefix("artifact:")
                artifact_row = connection.execute(
                    """
                    SELECT artifact_kind, schema_id
                    FROM research_artifacts
                    WHERE artifact_id = ?
                    """,
                    (artifact_id,),
                ).fetchone()
                if artifact_row == (
                    ResearchArtifactKind.DATASET_REFERENCE.value,
                    DATASET_REFERENCE_SCHEMA_ID,
                ):
                    dataset_reference_ids.append(artifact_id)

            if dataset_reference_ids != [decision.dataset_reference_artifact_id]:
                raise ValueError(
                    "INSUFFICIENT WFA decision historical evidence no longer "
                    "references the frozen DatasetReference admission"
                )

            binding = connection.execute(
                """
                SELECT dataset_id
                FROM research_dataset_reference_identities
                WHERE artifact_id = ?
                """,
                (decision.dataset_reference_artifact_id,),
            ).fetchone()
            if binding != (decision.dataset_id,):
                raise ValueError(
                    "INSUFFICIENT WFA decision DatasetReference identity binding mismatch"
                )
            if evidence_row[1] != decision.dataset_fingerprint:
                raise ValueError(
                    "INSUFFICIENT WFA decision dataset fingerprint does not match "
                    "historical admission"
                )

        if (
            decision.result_artifact_id is None
            and decision.outcome is not WfaQualificationOutcome.INSUFFICIENT
        ):
            return historical_experiment_spec_id

        trial = connection.execute(
            """
            SELECT
                parameter_configuration_fingerprint,
                experiment_spec_id,
                disposition
            FROM trials
            WHERE trial_id = ?
            """,
            (decision.trial_id,),
        ).fetchone()
        if (
            trial is None
            or trial[:2]
            != (
                candidate.parameter_configuration_fingerprint,
                historical_experiment_spec_id,
            )
        ):
            raise ValueError("WFA decision Trial/Candidate binding mismatch")

        plan = self.plan_resolver.resolve(decision.trial_id)
        if (
            plan.study_revision_id != decision.study_revision_id
            or plan.trial_id != decision.trial_id
            or canonical_fingerprint(
                dict(plan.parameter_configuration),
                schema=PARAMETER_VARIANT_SCHEMA_ID,
            )
            != candidate.parameter_configuration_fingerprint
        ):
            raise ValueError("WFA decision registered Trial plan mismatch")

        if any(value is None for value in historical[4:7]):
            raise ValueError(
                "durable WFA decision requires admitted historical result lineage"
            )
        if (
            verified_historical_result_artifact_id is None
            or historical[6] != verified_historical_result_artifact_id
        ):
            raise ValueError(
                "durable WFA decision historical result is not currently verified"
            )

        experiment_spec = connection.execute(
            """
            SELECT
                computation_kind,
                dataset_fingerprint,
                configuration_fingerprint,
                repository_revision,
                manifest_artifact_id
            FROM experiment_specs
            WHERE experiment_spec_id = ?
            """,
            (historical_experiment_spec_id,),
        ).fetchone()
        if (
            experiment_spec is None
            or experiment_spec[0] != ComputationKind.BACKTEST.value
            or experiment_spec[3] != plan.repository_revision
        ):
            raise ValueError(
                "economic WFA decision requires canonical registered "
                "historical ExperimentSpec"
            )

        evidence = connection.execute(
            """
            SELECT
                status,
                symbol,
                timeframe,
                timezone,
                request_start,
                request_end,
                dataset_fingerprint,
                configuration_fingerprint,
                result_fingerprint,
                repository_revision,
                artifact_references
            FROM research_evidence
            WHERE evidence_id = ?
            """,
            (historical[5],),
        ).fetchone()
        if (
            evidence is None
            or evidence[0] != "ACCEPTED"
            or evidence[6] != experiment_spec[1]
            or evidence[7] != experiment_spec[2]
            or evidence[8] != historical[6]
            or evidence[9] != experiment_spec[3]
        ):
            raise ValueError(
                "economic WFA decision historical evidence authority mismatch"
            )

        try:
            artifact_references = json.loads(evidence[10])
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError(
                "economic WFA decision historical evidence artifact references "
                "are invalid"
            ) from error
        if (
            not isinstance(artifact_references, list)
            or any(
                not isinstance(reference, str)
                for reference in artifact_references
            )
        ):
            raise ValueError(
                "economic WFA decision historical evidence artifact references "
                "are invalid"
            )

        manifest_reference = research_artifact_reference(
            experiment_spec[4]
        )
        result_reference = research_artifact_reference(
            historical[6]
        )
        if (
            manifest_reference not in artifact_references
            or result_reference not in artifact_references
        ):
            raise ValueError(
                "economic WFA decision historical evidence lacks "
                "manifest/result references"
            )

        latest_event = connection.execute(
            """
            SELECT new_disposition, causing_job_id
            FROM trial_disposition_events
            WHERE trial_id = ?
            ORDER BY sequence_number DESC
            LIMIT 1
            """,
            (decision.trial_id,),
        ).fetchone()
        if (
            latest_event is None
            or latest_event[0] != trial[2]
            or latest_event[1] is None
            or trial[2] not in ("EXECUTED", "REUSED")
        ):
            raise ValueError(
                "economic WFA decision historical Trial terminal lineage mismatch"
            )

        current_job = connection.execute(
            """
            SELECT
                state,
                completion_kind,
                attempt_id,
                reused_attempt_id,
                reused_evidence_id,
                reused_result_artifact_id
            FROM research_jobs
            WHERE job_id = ?
            """,
            (latest_event[1],),
        ).fetchone()
        if current_job is None or current_job[0] != "SUCCEEDED":
            raise ValueError(
                "economic WFA decision historical causing job is not successful"
            )

        if trial[2] == "EXECUTED":
            if (
                current_job[1] != "EXECUTED"
                or current_job[2] != historical[4]
            ):
                raise ValueError(
                    "economic WFA decision current RunAttempt lineage "
                    "does not match historical admission"
                )
        else:
            if (
                current_job[1] != "REUSED"
                or current_job[3] != historical[4]
                or current_job[4] != historical[5]
                or current_job[5] != historical[6]
            ):
                raise ValueError(
                    "economic WFA decision current reused lineage "
                    "does not match historical admission"
                )

        attempt = connection.execute(
            """
            SELECT
                experiment_spec_id,
                state,
                result_artifact_id,
                evidence_id
            FROM run_attempts
            WHERE attempt_id = ?
            """,
            (historical[4],),
        ).fetchone()
        if attempt != (
            historical_experiment_spec_id,
            "SUCCEEDED",
            historical[6],
            historical[5],
        ):
            raise ValueError(
                "economic WFA decision historical RunAttempt lineage mismatch"
            )

        historical_result_artifact = connection.execute(
            """
            SELECT artifact_kind, schema_id, byte_count
            FROM research_artifacts
            WHERE artifact_id = ?
            """,
            (historical[6],),
        ).fetchone()
        if (
            historical_result_artifact is None
            or historical_result_artifact[:2]
            != (
                ResearchArtifactKind.BACKTEST_RESULT.value,
                BACKTEST_RESULT_SCHEMA,
            )
        ):
            raise ValueError(
                "economic WFA decision historical result has wrong kind/schema"
            )
        try:
            historical_result_bytes = self.artifact_store.load_bytes(
                historical[6]
            )
            if len(historical_result_bytes) != historical_result_artifact[2]:
                raise ValueError(
                    "historical result byte count mismatch"
                )
            decode_stable_backtest_result_bytes(
                historical_result_bytes
            )
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            raise ValueError(
                "economic WFA decision historical result bytes "
                "are unavailable or invalid"
            ) from error

        manifest_artifact = connection.execute(
            """
            SELECT artifact_kind, schema_id, byte_count
            FROM research_artifacts
            WHERE artifact_id = ?
            """,
            (experiment_spec[4],),
        ).fetchone()
        if (
            manifest_artifact is None
            or manifest_artifact[:2]
            != (
                ResearchArtifactKind.BACKTEST_RUN_MANIFEST.value,
                BACKTEST_RUN_MANIFEST_SCHEMA,
            )
        ):
            raise ValueError(
                "economic WFA decision historical manifest has wrong kind/schema"
            )
        try:
            manifest_bytes = self.artifact_store.load_bytes(
                experiment_spec[4]
            )
            if len(manifest_bytes) != manifest_artifact[2]:
                raise ValueError(
                    "historical manifest byte count mismatch"
                )
            manifest = decode_canonical_bytes(
                manifest_bytes,
                schema=BACKTEST_RUN_MANIFEST_SCHEMA,
            )
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            raise ValueError(
                "economic WFA decision historical manifest bytes "
                "are unavailable or invalid"
            ) from error

        if not isinstance(manifest, dict):
            raise ValueError(
                "economic WFA decision historical manifest must decode to a mapping"
            )
        configuration_payload = dict(manifest)
        if configuration_payload.pop("dataset_fingerprint", None) != experiment_spec[1]:
            raise ValueError(
                "economic WFA decision historical manifest dataset "
                "does not match ExperimentSpec"
            )
        if (
            canonical_fingerprint(
                configuration_payload,
                schema=BACKTEST_CONFIG_V2_SCHEMA,
            )
            != experiment_spec[2]
        ):
            raise ValueError(
                "economic WFA decision historical manifest configuration "
                "does not match ExperimentSpec"
            )

        strategy_cls = get_research_procedure_strategy_class(
            plan.strategy_procedure_id
        )
        if strategy_cls is None:
            raise ValueError(
                "WFA decision registered strategy procedure is unsupported"
            )
        exact_params = dict(plan.parameter_configuration)
        try:
            registered_strategy = strategy_cls(
                params=exact_params
            )
        except Exception as error:
            raise ValueError(
                "WFA decision registered strategy cannot be reconstructed"
            ) from error
        if registered_strategy.research_parameters() != exact_params:
            raise ValueError(
                "WFA decision registered strategy parameters are not executable"
            )

        expected_manifest_context = {
            "symbol": evidence[1],
            "timeframe": plan.timeframe,
            "timezone": plan.timezone,
        }
        expected_manifest_range = {
            "start": plan.trial_range.start,
            "end": plan.trial_range.end,
        }
        manifest_financial = {
            "risk_per_trade_pct": manifest.get(
                "effective_risk_per_trade_pct"
            ),
            **(
                manifest.get("execution")
                if isinstance(manifest.get("execution"), dict)
                else {}
            ),
            **(
                manifest.get("economic_policy")
                if isinstance(manifest.get("economic_policy"), dict)
                else {}
            ),
        }
        if (
            manifest.get("dataset_context") != expected_manifest_context
            or manifest.get("request") != expected_manifest_range
            or manifest.get("strategy_name") != registered_strategy.name
            or manifest.get("strategy_params") != exact_params
            or float(manifest.get("initial_capital", 0.0))
            != float(plan.initial_capital)
            or manifest_financial
            != dict(plan.risk_economic_configuration)
        ):
            raise ValueError(
                "economic WFA decision historical manifest does not "
                "match registered Trial setup"
            )

        admission_row = connection.execute(
            """
            SELECT dataset_reference_artifact_id
            FROM qualification_dataset_admissions
            WHERE decision_id = ?
            """,
            (decision.historical_qualification_decision_id,),
        ).fetchone()
        if admission_row is None:
            raise ValueError(
                "economic WFA decision requires a durable original "
                "DatasetReference admission binding"
            )
        admitted_dataset_reference_artifact_id = admission_row[0]
        if (
            decision.dataset_reference_artifact_id
            != admitted_dataset_reference_artifact_id
        ):
            raise ValueError(
                "WFA decision DatasetReference does not match the "
                "historically admitted DatasetReference"
            )

        dataset_reference_ids = []
        for reference_text in artifact_references:
            if not reference_text.startswith("artifact:sha256:"):
                continue
            artifact_id = reference_text.removeprefix("artifact:")
            artifact_metadata = connection.execute(
                """
                SELECT artifact_kind, schema_id
                FROM research_artifacts
                WHERE artifact_id = ?
                """,
                (artifact_id,),
            ).fetchone()
            if artifact_metadata is None:
                raise ValueError(
                    "economic WFA decision historical evidence references "
                    "a missing artifact"
                )
            if (
                artifact_metadata[0]
                == ResearchArtifactKind.DATASET_REFERENCE.value
            ):
                if artifact_metadata[1] != DATASET_REFERENCE_SCHEMA_ID:
                    raise ValueError(
                        "historical DatasetReference has incompatible schema"
                    )
                dataset_reference_ids.append(artifact_id)

        if dataset_reference_ids != [
            admitted_dataset_reference_artifact_id
        ]:
            raise ValueError(
                "historical ResearchEvidence no longer references exactly "
                "the DatasetReference frozen at qualification admission"
            )

        dataset_artifact = self._load_canonical_artifact(
            connection,
            decision.dataset_reference_artifact_id,
            authority_label="WFA decision DatasetReference",
        )
        if (
            dataset_artifact is None
            or dataset_artifact.artifact_kind
            is not ResearchArtifactKind.DATASET_REFERENCE
            or dataset_artifact.schema_id != DATASET_REFERENCE_SCHEMA_ID
        ):
            raise ValueError(
                "WFA decision dataset reference has wrong artifact kind/schema"
            )
        binding = connection.execute(
            """
            SELECT dataset_id
            FROM research_dataset_reference_identities
            WHERE artifact_id = ?
            """,
            (decision.dataset_reference_artifact_id,),
        ).fetchone()
        if binding != (decision.dataset_id,):
            raise ValueError("WFA decision DatasetReference identity mismatch")

        try:
            dataset_bytes = self.artifact_store.load_bytes(
                decision.dataset_reference_artifact_id
            )
            if len(dataset_bytes) != dataset_artifact.byte_count:
                raise ValueError(
                    "WFA decision DatasetReference byte count mismatch"
                )
            reference = decode_dataset_reference_bytes(dataset_bytes)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            raise ValueError(
                "WFA decision DatasetReference bytes are unavailable or invalid"
            ) from error

        identity = reference.identity
        if identity.dataset_id != decision.dataset_id:
            raise ValueError(
                "WFA decision DatasetReference bytes contradict dataset_id"
            )
        if (
            identity.instrument_id != plan.instrument_id
            or identity.requested_range != plan.trial_range
            or identity.timeframe != plan.timeframe
            or identity.timezone != plan.timezone
            or identity.price_adjustment_basis.value.lower()
            != plan.data_treatment_basis.get("price_adjustment")
        ):
            raise ValueError(
                "WFA decision DatasetReference contradicts registered plan"
            )

        historical_context = DatasetContext(
            symbol=evidence[1],
            timeframe=evidence[2],
            timezone=evidence[3],
        )
        historical_range = TimeRange(
            datetime.fromisoformat(evidence[4]),
            datetime.fromisoformat(evidence[5]),
        )
        if (
            historical_range != plan.trial_range
            or historical_context.timeframe != plan.timeframe
            or historical_context.timezone != plan.timezone
        ):
            raise ValueError(
                "WFA decision historical evidence data inputs contradict registered plan"
            )
        if (
            dataset_fingerprint(
                historical_context,
                historical_range,
                identity.candles,
            )
            != experiment_spec[1]
            or decision.dataset_fingerprint != experiment_spec[1]
        ):
            raise ValueError(
                "WFA decision dataset claim does not match admitted historical dataset"
            )

        if decision.outcome is WfaQualificationOutcome.INSUFFICIENT:
            return historical_experiment_spec_id

        result_artifact = self._load_canonical_artifact(
            connection,
            decision.result_artifact_id,
            authority_label="WFA decision result",
        )
        if (
            result_artifact is None
            or result_artifact.artifact_kind
            is not ResearchArtifactKind.WFA_RESULT
            or result_artifact.schema_id != CANDIDATE_WFA_RESULT_SCHEMA_ID
        ):
            raise ValueError(
                "WFA decision result has wrong artifact kind/schema"
            )

        try:
            payload_bytes = self.artifact_store.load_bytes(
                decision.result_artifact_id
            )
            if len(payload_bytes) != result_artifact.byte_count:
                raise ValueError(
                    "WFA decision result artifact byte count mismatch"
                )
            payload = decode_candidate_wfa_result_bytes(payload_bytes)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            raise ValueError(
                "WFA decision result artifact bytes are unavailable or invalid"
            ) from error

        approved_configuration = wfa_window_configuration_payload(
            in_sample_bars=WALK_FORWARD_CONFIG.in_sample_bars,
            out_sample_bars=WALK_FORWARD_CONFIG.out_sample_bars,
            step_bars=WALK_FORWARD_CONFIG.step_bars,
            mode=WALK_FORWARD_CONFIG.mode,
        )
        approved_configuration_fingerprint = (
            wfa_window_configuration_fingerprint(
                **approved_configuration
            )
        )
        if (
            decision.wfa_configuration_fingerprint
            != approved_configuration_fingerprint
            or payload["wfa_configuration"]
            != approved_configuration
            or payload["wfa_configuration_fingerprint"]
            != approved_configuration_fingerprint
        ):
            raise ValueError(
                "WFA decision does not use the approved M9.6 "
                "300/150/150 rolling configuration"
            )

        try:
            software_identity = self.software_identity_provider.resolve()
        except Exception as error:
            raise RuntimeError(
                "WFA decision evaluator software identity could not be resolved"
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
            raise RuntimeError(
                "WFA decision evaluator software identity is unavailable operationally"
            )
        if worktree_clean is not True:
            raise ValueError(
                "WFA decision evaluator worktree is not clean"
            )
        if (
            decision.evaluator_repository_revision != evaluator_revision
            or payload["evaluator_repository_revision"]
            != evaluator_revision
        ):
            raise ValueError(
                "WFA decision evaluator revision does not match "
                "trusted current software identity"
            )
        try:
            compatibility = self.executable_compatibility_checker.check(
                historical_revision=experiment_spec[3],
                current_revision=evaluator_revision,
            )
        except ExecutableCompatibilityOperationalError as error:
            raise RuntimeError(
                "WFA decision executable compatibility failed operationally"
            ) from error
        if not compatibility.compatible:
            raise ValueError(
                "WFA decision evaluator executable core is incompatible "
                "with the historical candidate"
            )

        expected = {
            "study_revision_id": decision.study_revision_id,
            "trial_id": decision.trial_id,
            "candidate_revision_id": decision.candidate_revision_id,
            "historical_qualification_decision_id": (
                decision.historical_qualification_decision_id
            ),
            "historical_experiment_spec_id": historical_experiment_spec_id,
            "source_dataset_reference_artifact_id": (
                decision.dataset_reference_artifact_id
            ),
            "source_dataset_id": decision.dataset_id,
            "dataset_fingerprint": decision.dataset_fingerprint,
            "requested_range": {
                "start": plan.trial_range.start,
                "end": plan.trial_range.end,
            },
            "instrument_id": plan.instrument_id,
            "timeframe": plan.timeframe,
            "timezone": plan.timezone,
            "strategy_procedure_id": plan.strategy_procedure_id,
            "strategy_parameters": exact_params,
            "initial_capital": plan.initial_capital,
            "risk_economic_configuration": dict(
                plan.risk_economic_configuration
            ),
            "data_treatment_basis": dict(plan.data_treatment_basis),
            "wfa_configuration_fingerprint": (
                approved_configuration_fingerprint
            ),
            "verdict": decision.wfa_verdict,
            "evaluator_repository_revision": evaluator_revision,
        }
        for field_name, expected_value in expected.items():
            if payload[field_name] != expected_value:
                raise ValueError(
                    "WFA decision result artifact authority mismatch: "
                    f"{field_name}"
                )

        try:
            expected_prehistory = (
                WalkForwardRunner._required_prehistory_bars(
                    strategy_cls=strategy_cls,
                    param_space=[exact_params],
                )
            )
            generator = WalkForwardWindowGenerator(
                in_sample_bars=approved_configuration["in_sample_bars"],
                out_sample_bars=approved_configuration["out_sample_bars"],
                step_bars=approved_configuration["step_bars"],
                mode=approved_configuration["mode"],
            )
            expected_windows = tuple(
                generator.generate(
                    list(identity.candles),
                    prehistory_bars=expected_prehistory,
                )
            )
        except (TypeError, ValueError, RuntimeError) as error:
            raise ValueError(
                "WFA decision admitted M5 window generation is invalid"
            ) from error

        if (
            payload["resolved_prehistory_bars"] != expected_prehistory
            or len(payload["windows"]) != len(expected_windows)
            or not expected_windows
        ):
            raise ValueError(
                "WFA decision result windows do not match admitted M5 generation"
            )

        for persisted, generated in zip(
            payload["windows"],
            expected_windows,
        ):
            expected_bounds = {
                "window_index": generated.window_index,
                "train_history": _sequence_bounds(
                    generated.train_history_bars
                ),
                "train_scored": _sequence_bounds(
                    generated.train_bars
                ),
                "test_history": _sequence_bounds(
                    generated.test_history_bars
                ),
                "test_scored": _sequence_bounds(
                    generated.test_bars
                ),
            }
            for field_name, expected_value in expected_bounds.items():
                if persisted[field_name] != expected_value:
                    raise ValueError(
                        "WFA decision result windows do not match "
                        f"admitted M5 generation: {field_name}"
                    )

            if tuple(
                point[0]
                for point in persisted["oos_equity_curve"]
            ) != tuple(
                candle.timestamp
                for candle in generated.test_bars
            ):
                raise ValueError(
                    "WFA decision OOS equity timestamps do not match "
                    "admitted M5 scored candles"
                )

        return historical_experiment_spec_id

    def _append_decision(self, decision: CandidateWfaDecision) -> None:
        """Internal persistence primitive used only by CandidateWfaService."""
        if not isinstance(decision, CandidateWfaDecision):
            raise TypeError("decision must be a CandidateWfaDecision")

        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")

                verified_historical_result_artifact_id = None
                if (
                    decision.result_artifact_id is not None
                    or decision.outcome is WfaQualificationOutcome.INSUFFICIENT
                ):
                    try:
                        verified = _ReservedTransactionStudyAggregationService(
                            catalog_store=self.catalog_store,
                            artifact_store=self.artifact_store,
                            evidence_store=self.evidence_store,
                        ).load_verified_trial_backtest(
                            decision.trial_id
                        )
                    except StudyAggregationError as error:
                        raise ValueError(
                            "economic WFA decision requires currently verified "
                            "historical Backtest admission"
                        ) from error
                    verified_historical_result_artifact_id = (
                        verified.result_artifact_id
                    )

                self._validate_lineage(
                    connection,
                    decision,
                    verified_historical_result_artifact_id=(
                        verified_historical_result_artifact_id
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO candidate_wfa_decisions (
                        decision_id,
                        created_at,
                        evaluator_version,
                        study_revision_id,
                        trial_id,
                        candidate_revision_id,
                        historical_qualification_decision_id,
                        evaluator_repository_revision,
                        dataset_reference_artifact_id,
                        dataset_id,
                        dataset_fingerprint,
                        wfa_configuration_fingerprint,
                        result_artifact_id,
                        evidence_validity,
                        wfa_verdict,
                        outcome,
                        reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        decision.decision_id,
                        decision.created_at.isoformat(timespec="microseconds"),
                        decision.evaluator_version,
                        decision.study_revision_id,
                        decision.trial_id,
                        decision.candidate_revision_id,
                        decision.historical_qualification_decision_id,
                        decision.evaluator_repository_revision,
                        decision.dataset_reference_artifact_id,
                        decision.dataset_id,
                        decision.dataset_fingerprint,
                        decision.wfa_configuration_fingerprint,
                        decision.result_artifact_id,
                        decision.evidence_validity.value,
                        decision.wfa_verdict,
                        decision.outcome.value,
                        decision.reason,
                    ),
                )
            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise ValueError(
                    "CandidateWfaDecision is append-only and must be unique"
                ) from error
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

    @staticmethod
    def _from_row(row) -> CandidateWfaDecision:
        return CandidateWfaDecision(
            decision_id=row[0],
            created_at=datetime.fromisoformat(row[1]),
            evaluator_version=row[2],
            study_revision_id=row[3],
            trial_id=row[4],
            candidate_revision_id=row[5],
            historical_qualification_decision_id=row[6],
            evaluator_repository_revision=row[7],
            dataset_reference_artifact_id=row[8],
            dataset_id=row[9],
            dataset_fingerprint=row[10],
            wfa_configuration_fingerprint=row[11],
            result_artifact_id=row[12],
            evidence_validity=WfaEvidenceValidity(row[13]),
            wfa_verdict=row[14],
            outcome=WfaQualificationOutcome(row[15]),
            reason=row[16],
        )

    def load_decision(self, decision_id: str) -> CandidateWfaDecision | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    decision_id, created_at, evaluator_version,
                    study_revision_id, trial_id, candidate_revision_id,
                    historical_qualification_decision_id,
                    evaluator_repository_revision,
                    dataset_reference_artifact_id, dataset_id,
                    dataset_fingerprint, wfa_configuration_fingerprint,
                    result_artifact_id, evidence_validity, wfa_verdict,
                    outcome, reason
                FROM candidate_wfa_decisions
                WHERE decision_id = ?
                """,
                (decision_id,),
            ).fetchone()
        return None if row is None else self._from_row(row)

    def load_current_decision(
        self,
        candidate_revision_id: str,
    ) -> CandidateWfaDecision | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    decision_id, created_at, evaluator_version,
                    study_revision_id, trial_id, candidate_revision_id,
                    historical_qualification_decision_id,
                    evaluator_repository_revision,
                    dataset_reference_artifact_id, dataset_id,
                    dataset_fingerprint, wfa_configuration_fingerprint,
                    result_artifact_id, evidence_validity, wfa_verdict,
                    outcome, reason
                FROM candidate_wfa_decisions
                WHERE candidate_revision_id = ?
                ORDER BY decision_sequence DESC
                LIMIT 1
                """,
                (candidate_revision_id,),
            ).fetchone()
        return None if row is None else self._from_row(row)
