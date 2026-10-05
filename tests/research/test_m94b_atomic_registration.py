from datetime import datetime, timezone

import pytest

from core.research.models.registered_study import (
    EvidenceReusePolicy,
    STUDY_REVISION_SCHEMA_ID,
    TRIAL_MEMBERSHIP_EVIDENCE_SCHEMA_ID,
    Study,
    Trial,
    TrialDisposition,
    TrialDispositionEvent,
)
from core.research.models.research_catalog import (
    ResearchArtifactKind,
)
from core.research.reproducibility import (
    canonical_bytes,
    canonical_fingerprint,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
)
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)


UTC = timezone.utc
NOW = datetime(
    2020,
    1,
    1,
    tzinfo=UTC,
)


def _publish(
    catalog,
    artifacts,
    payload,
    *,
    kind,
    schema,
):
    data = canonical_bytes(
        payload,
        schema=schema,
    )

    artifact = artifacts.persist_bytes(
        data,
        artifact_kind=kind,
        schema_id=schema,
        created_at=NOW,
    )

    catalog.save_artifact(
        artifact
    )

    return artifact


def test_whole_revision_transaction_rolls_back_partial_population(
    tmp_path,
):
    catalog = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3"
    )

    artifacts = ContentAddressedResearchArtifactStore(
        tmp_path / "artifacts"
    )

    catalog.save_study(
        Study(
            study_id="study-atomic",
            created_at=NOW,
            display_title="atomic test",
        )
    )

    plan = _publish(
        catalog,
        artifacts,
        {
            "study_id": "study-atomic",
            "plan": "fixture",
        },
        kind=(
            ResearchArtifactKind.STUDY_REVISION_PLAN
        ),
        schema=STUDY_REVISION_SCHEMA_ID,
    )

    membership_one = _publish(
        catalog,
        artifacts,
        {
            "instrument_id": "NSE:A",
            "segment": 1,
        },
        kind=(
            ResearchArtifactKind
            .TRIAL_MEMBERSHIP_EVIDENCE
        ),
        schema=(
            TRIAL_MEMBERSHIP_EVIDENCE_SCHEMA_ID
        ),
    )

    membership_two = _publish(
        catalog,
        artifacts,
        {
            "instrument_id": "NSE:B",
            "segment": 1,
        },
        kind=(
            ResearchArtifactKind
            .TRIAL_MEMBERSHIP_EVIDENCE
        ),
        schema=(
            TRIAL_MEMBERSHIP_EVIDENCE_SCHEMA_ID
        ),
    )

    parameter_fp = canonical_fingerprint(
        {"fast": 5},
        schema="kanasu.study-parameter-variant.v1",
    )

    def trial(
        instrument,
        membership,
    ):
        trial_id = canonical_fingerprint(
            {
                "study_revision_id": (
                    plan.artifact_id
                ),
                "instrument_id": instrument,
                "membership": (
                    membership.artifact_id
                ),
                "parameter": parameter_fp,
            },
            schema="kanasu.trial.v1",
        )

        return Trial(
            trial_id=trial_id,
            study_revision_id=(
                plan.artifact_id
            ),
            instrument_id=instrument,
            membership_episode_start=NOW,
            membership_episode_end=datetime(
                2020,
                2,
                1,
                tzinfo=UTC,
            ),
            membership_evidence_fingerprint=(
                membership.artifact_id
            ),
            membership_evidence_artifact_id=(
                membership.artifact_id
            ),
            parameter_configuration_fingerprint=(
                parameter_fp
            ),
            registered_at=NOW,
            disposition=TrialDisposition.PENDING,
            disposition_at=NOW,
        )

    first = trial(
        "NSE:A",
        membership_one,
    )

    second = trial(
        "NSE:B",
        membership_two,
    )

    # Deliberately duplicate the event primary key. The first Trial/event
    # insertion occurs before the second event fails, proving rollback
    # covers the already-inserted population rows.
    events = (
        TrialDispositionEvent(
            event_id="duplicate-event",
            trial_id=first.trial_id,
            sequence_number=1,
            previous_disposition=None,
            new_disposition=(
                TrialDisposition.PENDING
            ),
            occurred_at=NOW,
        ),
        TrialDispositionEvent(
            event_id="duplicate-event",
            trial_id=second.trial_id,
            sequence_number=1,
            previous_disposition=None,
            new_disposition=(
                TrialDisposition.PENDING
            ),
            occurred_at=NOW,
        ),
    )

    with pytest.raises(
        ValueError,
        match="no partial Trial population",
    ):
        catalog._save_registered_revision_population(
            study_id="study-atomic",
            study_revision_id=(
                plan.artifact_id
            ),
            plan_artifact_id=(
                plan.artifact_id
            ),
            repository_revision="repo-1",
            evidence_reuse_policy=(
                EvidenceReusePolicy
                .ALLOW_EXACT_ACCEPTED
            ),
            registered_at=NOW,
            trials=(first, second),
            initial_events=events,
        )

    assert catalog.load_study_revision(
        plan.artifact_id
    ) is None

    assert catalog.load_trial(
        first.trial_id
    ) is None

    assert catalog.load_trial(
        second.trial_id
    ) is None

    assert catalog.list_study_revisions(
        "study-atomic"
    ) == ()

    with catalog._connect() as connection:
        assert connection.execute(
            """
            SELECT COUNT(*)
            FROM study_revision_population_registrations
            """
        ).fetchone()[0] == 0


def test_population_registration_requires_plan_content_identity(
    tmp_path,
):
    catalog = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3"
    )

    with pytest.raises(
        ValueError,
        match="must equal",
    ):
        catalog._save_registered_revision_population(
            study_id="study",
            study_revision_id=(
                "sha256:" + "1" * 64
            ),
            plan_artifact_id=(
                "sha256:" + "2" * 64
            ),
            repository_revision="repo-1",
            evidence_reuse_policy=(
                EvidenceReusePolicy
                .ALLOW_EXACT_ACCEPTED
            ),
            registered_at=NOW,
            trials=(),
            initial_events=(),
        )
