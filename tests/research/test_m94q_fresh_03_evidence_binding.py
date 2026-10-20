from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from core.research.models.registered_study import (
    ResearchJobCompletionKind,
    ResearchJobState,
    Trial,
    TrialDisposition,
)
from core.research.models.research_catalog import (
    ResearchArtifact,
    ResearchArtifactKind,
    RunAttemptState,
)
from core.research.models.research_evidence import (
    ResearchEvidenceStatus,
)
from core.research.reproducibility import (
    BACKTEST_RESULT_SCHEMA,
    BACKTEST_RUN_MANIFEST_SCHEMA,
)
from core.research.research_artifact_store import (
    research_artifact_reference,
)
from core.research.study_aggregation import (
    StudyAggregationError,
    StudyAggregationService,
)


# M94Q-FRESH-20261020-03 PERMANENT RED REGRESSION
#
# A result-bearing registered Trial must not become authoritative for
# Study aggregation merely because Trial/ResearchJob/RunAttempt/result
# IDs agree. The selected result must also be authorized by the actual
# ACCEPTED ResearchEvidence under the same exact identity contract
# already required for exact evidence reuse.


NOW = datetime(2026, 10, 20, 6, 0, tzinfo=timezone.utc)


def _fp(character):
    return "sha256:" + (character * 64)


REVISION_ID = _fp("1")
TRIAL_ID = _fp("2")
SPEC_ID = _fp("3")
MEMBERSHIP_ID = _fp("4")
PARAMETER_ID = _fp("5")
RESULT_ID = _fp("6")
MANIFEST_ID = _fp("7")
DATASET_FP = _fp("8")
CONFIG_FP = _fp("9")

OTHER_RESULT_ID = _fp("a")
OTHER_DATASET_FP = _fp("b")
OTHER_CONFIG_FP = _fp("c")


def _trial(lineage):
    disposition = (
        TrialDisposition.EXECUTED
        if lineage == "EXECUTED"
        else TrialDisposition.REUSED
    )

    return Trial(
        trial_id=TRIAL_ID,
        study_revision_id=REVISION_ID,
        instrument_id="NSE:RELIANCE",
        membership_episode_start=NOW,
        membership_episode_end=NOW + timedelta(days=1),
        membership_evidence_fingerprint=MEMBERSHIP_ID,
        membership_evidence_artifact_id=MEMBERSHIP_ID,
        parameter_configuration_fingerprint=PARAMETER_ID,
        registered_at=NOW,
        disposition=disposition,
        disposition_at=NOW + timedelta(minutes=1),
        experiment_spec_id=SPEC_ID,
        reused_attempt_id=(
            "attempt-source"
            if lineage == "REUSED"
            else None
        ),
    )


def _artifact(
    artifact_id,
    artifact_kind,
    schema_id,
):
    return ResearchArtifact(
        artifact_id=artifact_id,
        artifact_kind=artifact_kind,
        schema_id=schema_id,
        relative_path=(
            artifact_id.removeprefix("sha256:")
            + ".json"
        ),
        byte_count=1,
        created_at=NOW,
    )


class _Catalog:
    def __init__(self, lineage):
        self.lineage = lineage

        self.attempt = SimpleNamespace(
            attempt_id=(
                "attempt-executed"
                if lineage == "EXECUTED"
                else "attempt-source"
            ),
            experiment_spec_id=SPEC_ID,
            state=RunAttemptState.SUCCEEDED,
            evidence_id="evidence-source",
            result_artifact_id=RESULT_ID,
        )

        self.spec = SimpleNamespace(
            experiment_spec_id=SPEC_ID,
            dataset_fingerprint=DATASET_FP,
            configuration_fingerprint=CONFIG_FP,
            repository_revision="revision-authoritative",
            manifest_artifact_id=MANIFEST_ID,
        )

        self.artifacts = {
            RESULT_ID: _artifact(
                RESULT_ID,
                ResearchArtifactKind.BACKTEST_RESULT,
                BACKTEST_RESULT_SCHEMA,
            ),
            MANIFEST_ID: _artifact(
                MANIFEST_ID,
                ResearchArtifactKind.BACKTEST_RUN_MANIFEST,
                BACKTEST_RUN_MANIFEST_SCHEMA,
            ),
        }

    def load_trial_disposition_events(
        self,
        trial_id,
    ):
        assert trial_id == TRIAL_ID

        return (
            SimpleNamespace(
                trial_id=TRIAL_ID,
                new_disposition=(
                    TrialDisposition.EXECUTED
                    if self.lineage == "EXECUTED"
                    else TrialDisposition.REUSED
                ),
                causing_job_id="job-current",
            ),
        )

    def load_research_job(
        self,
        job_id,
    ):
        assert job_id == "job-current"

        if self.lineage == "EXECUTED":
            return SimpleNamespace(
                job_id=job_id,
                trial_id=TRIAL_ID,
                state=ResearchJobState.SUCCEEDED,
                completion_kind=(
                    ResearchJobCompletionKind.EXECUTED
                ),
                attempt_id="attempt-executed",
                reused_attempt_id=None,
                reused_evidence_id=None,
                reused_result_artifact_id=None,
            )

        return SimpleNamespace(
            job_id=job_id,
            trial_id=TRIAL_ID,
            state=ResearchJobState.SUCCEEDED,
            completion_kind=(
                ResearchJobCompletionKind.REUSED
            ),
            attempt_id=None,
            reused_attempt_id="attempt-source",
            reused_evidence_id="evidence-source",
            reused_result_artifact_id=RESULT_ID,
        )

    def load_run_attempt(
        self,
        attempt_id,
    ):
        assert attempt_id == self.attempt.attempt_id
        return self.attempt

    def load_experiment_spec(
        self,
        experiment_spec_id,
    ):
        assert experiment_spec_id == SPEC_ID
        return self.spec

    def load_artifact(
        self,
        artifact_id,
    ):
        return self.artifacts.get(artifact_id)


class _EvidenceStore:
    def __init__(self, evidence):
        self.evidence = evidence

    def load(
        self,
        evidence_id,
    ):
        assert evidence_id == "evidence-source"
        return self.evidence


def _evidence(case):
    evidence = SimpleNamespace(
        evidence_id="evidence-source",
        status=ResearchEvidenceStatus.ACCEPTED,
        dataset_fingerprint=DATASET_FP,
        configuration_fingerprint=CONFIG_FP,
        repository_revision="revision-authoritative",
        result_fingerprint=RESULT_ID,
        artifact_references=(
            research_artifact_reference(MANIFEST_ID),
            research_artifact_reference(RESULT_ID),
        ),
    )

    if case == "valid":
        return evidence

    if case == "missing_evidence":
        return None

    if case == "non_accepted":
        evidence.status = ResearchEvidenceStatus.INCOMPLETE
    elif case == "dataset_mismatch":
        evidence.dataset_fingerprint = OTHER_DATASET_FP
    elif case == "configuration_mismatch":
        evidence.configuration_fingerprint = OTHER_CONFIG_FP
    elif case == "repository_mismatch":
        evidence.repository_revision = "revision-other"
    elif case == "result_fingerprint_mismatch":
        evidence.result_fingerprint = OTHER_RESULT_ID
    elif case == "missing_manifest_reference":
        evidence.artifact_references = (
            research_artifact_reference(RESULT_ID),
        )
    elif case == "missing_result_reference":
        evidence.artifact_references = (
            research_artifact_reference(MANIFEST_ID),
        )
    else:
        raise AssertionError(
            f"unsupported evidence case: {case}"
        )

    return evidence


def _service(
    lineage,
    evidence_case,
):
    catalog = _Catalog(lineage)

    service = StudyAggregationService(
        catalog_store=catalog,
        artifact_store=object(),
    )

    # Current production aggregation has no evidence-store dependency.
    # Attach the authority explicitly so the regression proves that
    # _resolve_result_artifact_id currently ignores it. The GREEN
    # correction may promote this to an explicit constructor dependency.
    service.evidence_store = _EvidenceStore(
        _evidence(evidence_case)
    )

    return service, _trial(lineage)


@pytest.mark.parametrize(
    "lineage",
    ("EXECUTED", "REUSED"),
)
@pytest.mark.parametrize(
    "evidence_case",
    (
        "missing_evidence",
        "non_accepted",
        "dataset_mismatch",
        "configuration_mismatch",
        "repository_mismatch",
        "result_fingerprint_mismatch",
        "missing_manifest_reference",
        "missing_result_reference",
    ),
)
def test_m94q_fresh_03_selected_result_requires_exact_accepted_evidence(
    lineage,
    evidence_case,
):
    service, trial = _service(
        lineage,
        evidence_case,
    )

    with pytest.raises(
        StudyAggregationError,
        match="evidence|authoritative|result",
    ):
        service._resolve_result_artifact_id(
            trial
        )


# M94Q-FRESH-20261020-03 POSITIVE CONTROL
@pytest.mark.parametrize(
    "lineage",
    ("EXECUTED", "REUSED"),
)
def test_m94q_fresh_03_exact_accepted_evidence_remains_valid(
    lineage,
):
    service, trial = _service(
        lineage,
        "valid",
    )

    assert (
        service._resolve_result_artifact_id(
            trial
        )
        == RESULT_ID
    )