from datetime import datetime, timedelta, timezone
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from core.research.models.paper_campaign import PaperCampaign
from core.research.models.registered_study import Study
from core.research.sqlite_paper_campaign_store import SQLitePaperCampaignStore
from core.research.sqlite_qualification_store import (
    QualificationPolicyConcurrencyConflict,
    SQLiteQualificationStore,
)
from core.research.sqlite_research_catalog_store import SQLiteResearchCatalogStore


NOW = datetime(2026, 11, 7, tzinfo=timezone.utc)


def fp(character: str) -> str:
    return "sha256:" + character * 64


def test_list_studies_returns_only_active_by_default(tmp_path):
    store = SQLiteResearchCatalogStore(tmp_path / "research.sqlite3")
    store.save_study(Study("study-a", NOW, "A", False))
    store.save_study(Study("study-b", NOW + timedelta(seconds=1), "B", True))

    assert [item.study_id for item in store.list_studies()] == ["study-a"]
    assert [item.study_id for item in store.list_studies(include_archived=True)] == [
        "study-a",
        "study-b",
    ]


def test_atomic_policy_threshold_reuses_same_and_versions_changed_threshold(tmp_path):
    store = SQLiteQualificationStore(tmp_path / "research.sqlite3")

    first, first_changed = store.ensure_active_policy_threshold(
        Decimal("50"),
        changed_at=NOW,
    )
    same, same_changed = store.ensure_active_policy_threshold(
        Decimal("50.0"),
        changed_at=NOW + timedelta(seconds=1),
    )
    second, second_changed = store.ensure_active_policy_threshold(
        Decimal("60"),
        changed_at=NOW + timedelta(seconds=2),
        expected_active_policy_id=first.policy_id,
    )

    assert first_changed is True
    assert same_changed is False
    assert same.policy_id == first.policy_id
    assert second_changed is True
    assert second.version == first.version + 1
    assert store.load_active_policy().policy_id == second.policy_id


def _artifact_row(connection, artifact_id, kind):
    digest = artifact_id.removeprefix("sha256:")
    connection.execute(
        """
        INSERT INTO research_artifacts (
            artifact_id, artifact_kind, schema_id, relative_path,
            byte_count, created_at
        ) VALUES (?, ?, 'fixture.v1', ?, 0, ?)
        """,
        (
            artifact_id,
            kind,
            f"sha256/{digest[:2]}/{digest}.json",
            NOW.isoformat(),
        ),
    )


def _campaign(campaign_id: str) -> PaperCampaign:
    return PaperCampaign(
        campaign_id=campaign_id,
        created_at=NOW,
        candidate_revision_id=fp("2"),
        wfa_decision_id="wfa-decision-1",
        study_revision_id=fp("3"),
        trial_id=fp("4"),
        experiment_spec_id=fp("5"),
        parameter_configuration_fingerprint=fp("6"),
        configuration_fingerprint=fp("1"),
        created_repository_revision="revision-1",
    )


def _seed_campaign_parents(path, campaign):
    SQLitePaperCampaignStore(path)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        for artifact_id, kind in (
            (fp("7"), "STUDY_REVISION_PLAN"),
            (fp("8"), "BACKTEST_RUN_MANIFEST"),
            (fp("9"), "TRIAL_MEMBERSHIP_EVIDENCE"),
            (fp("a"), "BACKTEST_RESULT"),
            (fp("b"), "DATASET_REFERENCE"),
            (fp("c"), "WFA_RESULT"),
        ):
            _artifact_row(connection, artifact_id, kind)

        connection.execute(
            "INSERT INTO studies VALUES (?, ?, ?, ?)",
            ("study-sqlite", NOW.isoformat(), "fixture", 0),
        )
        connection.execute(
            """
            INSERT INTO study_revisions (
                study_revision_id, identity_schema, study_id, revision_number,
                plan_artifact_id, repository_revision, evidence_reuse_policy,
                registered_at, initial_batch_started_at
            ) VALUES (?, 'fixture.v1', 'study-sqlite', 1, ?, 'revision-1',
                      'FORCE_NEW_EXECUTION', ?, NULL)
            """,
            (campaign.study_revision_id, fp("7"), NOW.isoformat()),
        )
        connection.execute(
            """
            INSERT INTO experiment_specs (
                experiment_spec_id, identity_schema, computation_kind,
                manifest_artifact_id, dataset_fingerprint,
                configuration_fingerprint, repository_revision, created_at
            ) VALUES (?, 'kanasu.experiment-spec.v1', 'BACKTEST', ?, ?, ?,
                      'revision-1', ?)
            """,
            (
                campaign.experiment_spec_id,
                fp("8"),
                fp("d"),
                fp("e"),
                NOW.isoformat(),
            ),
        )
        connection.execute(
            """
            INSERT INTO trials (
                trial_id, identity_schema, study_revision_id, instrument_id,
                membership_episode_start, membership_episode_end,
                membership_evidence_fingerprint, membership_evidence_artifact_id,
                parameter_configuration_fingerprint, registered_at,
                experiment_spec_id, disposition, disposition_at,
                reused_attempt_id, failure_classification, failure_message
            ) VALUES (?, 'fixture.v1', ?, 'instrument-reliance', ?, ?, ?, ?, ?, ?,
                      ?, 'EXECUTED', ?, NULL, NULL, NULL)
            """,
            (
                campaign.trial_id,
                campaign.study_revision_id,
                (NOW - timedelta(days=10)).isoformat(),
                (NOW - timedelta(days=1)).isoformat(),
                fp("9"),
                fp("9"),
                campaign.parameter_configuration_fingerprint,
                NOW.isoformat(),
                campaign.experiment_spec_id,
                NOW.isoformat(),
            ),
        )
        connection.execute(
            """
            INSERT INTO fixed_candidate_revisions (
                candidate_revision_id, study_revision_id, trial_id,
                experiment_spec_id, parameter_configuration_fingerprint,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                campaign.candidate_revision_id,
                campaign.study_revision_id,
                campaign.trial_id,
                campaign.experiment_spec_id,
                campaign.parameter_configuration_fingerprint,
                NOW.isoformat(),
            ),
        )
        policy_id = fp("f")
        connection.execute(
            "INSERT INTO qualification_policies VALUES (?, 1, '0', ?)",
            (policy_id, NOW.isoformat()),
        )
        connection.execute(
            """
            INSERT INTO qualification_policy_activations (
                policy_id, activated_at
            ) VALUES (?, ?)
            """,
            (policy_id, NOW.isoformat()),
        )
        connection.execute(
            """
            INSERT INTO qualification_decisions (
                decision_id, created_at, evaluator_version, policy_id,
                policy_version, threshold_text, study_revision_id, trial_id,
                candidate_revision_id, attempt_id, evidence_id,
                result_artifact_id, evidence_validity, criterion_outcome,
                outcome, profitable_trade_count, completed_trade_count,
                rate_numerator, rate_denominator, reason
            ) VALUES ('historical-sqlite', ?, 'fixture', ?, 1, '0', ?, ?, ?,
                      NULL, NULL, ?, 'VALID', 'SATISFIED', 'ELIGIBLE',
                      1, 1, 100, 1, 'fixture')
            """,
            (
                NOW.isoformat(),
                policy_id,
                campaign.study_revision_id,
                campaign.trial_id,
                campaign.candidate_revision_id,
                fp("a"),
            ),
        )
        connection.execute(
            """
            INSERT INTO candidate_wfa_decisions (
                decision_id, created_at, evaluator_version,
                study_revision_id, trial_id, candidate_revision_id,
                historical_qualification_decision_id,
                evaluator_repository_revision,
                dataset_reference_artifact_id, dataset_id, dataset_fingerprint,
                wfa_configuration_fingerprint, result_artifact_id,
                evidence_validity, wfa_verdict, outcome, reason
            ) VALUES (?, ?, 'fixture', ?, ?, ?, 'historical-sqlite',
                      'revision-1', ?, ?, ?, ?, ?,
                      'VALID', 'PASS', 'ELIGIBLE', 'fixture')
            """,
            (
                campaign.wfa_decision_id,
                NOW.isoformat(),
                campaign.study_revision_id,
                campaign.trial_id,
                campaign.candidate_revision_id,
                fp("b"),
                fp("0"),
                fp("1"),
                fp("2"),
                fp("c"),
            ),
        )
        connection.commit()


def test_duplicate_safe_campaign_create_reuses_exact_authority(tmp_path):
    path = tmp_path / "research.sqlite3"
    first = _campaign("paper-campaign-a")
    _seed_campaign_parents(path, first)

    store = SQLitePaperCampaignStore(path)
    created, was_created = store.create_or_load_matching_campaign(first)
    second = _campaign("paper-campaign-b")
    reused, second_created = store.create_or_load_matching_campaign(second)

    assert was_created is True
    assert second_created is False
    assert reused.campaign_id == created.campaign_id
    assert len(store.list_campaigns_for_candidate(first.candidate_revision_id)) == 1
    assert len(store.list_campaigns_for_study("study-sqlite")) == 1


def test_concurrent_same_threshold_creates_only_one_new_policy_version(tmp_path):
    store = SQLiteQualificationStore(tmp_path / "policy.sqlite3")
    base, _ = store.ensure_active_policy_threshold(
        Decimal("50"),
        changed_at=NOW,
    )

    def change(_index):
        local = SQLiteQualificationStore(tmp_path / "policy.sqlite3")
        return local.ensure_active_policy_threshold(
            Decimal("60"),
            changed_at=NOW + timedelta(seconds=1),
            expected_active_policy_id=base.policy_id,
        )[0]

    with ThreadPoolExecutor(max_workers=2) as executor:
        policies = list(executor.map(change, (1, 2)))

    assert policies[0].policy_id == policies[1].policy_id
    assert policies[0].version == base.version + 1
    assert store.load_active_policy().policy_id == policies[0].policy_id


def test_stale_policy_observation_cannot_activate_a_different_threshold(tmp_path):
    store = SQLiteQualificationStore(tmp_path / "policy.sqlite3")
    first, _ = store.ensure_active_policy_threshold(
        Decimal("50"),
        changed_at=NOW,
    )
    second, _ = store.ensure_active_policy_threshold(
        Decimal("60"),
        changed_at=NOW + timedelta(seconds=1),
        expected_active_policy_id=first.policy_id,
    )

    with pytest.raises(
        QualificationPolicyConcurrencyConflict,
        match="changed since caller observation",
    ):
        store.ensure_active_policy_threshold(
            Decimal("50"),
            changed_at=NOW + timedelta(seconds=2),
            expected_active_policy_id=first.policy_id,
        )

    active = store.load_active_policy()
    assert active is not None
    assert active.policy_id == second.policy_id
    assert active.net_profitable_trade_rate_threshold_pct == Decimal("60")


def test_concurrent_send_to_paper_reuses_one_matching_campaign(tmp_path):
    path = tmp_path / "campaign.sqlite3"
    template = _campaign("paper-campaign-seed")
    _seed_campaign_parents(path, template)

    def create(index):
        local = SQLitePaperCampaignStore(path)
        value = _campaign(f"paper-campaign-{index}")
        return local.create_or_load_matching_campaign(value)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(create, (1, 2)))

    ids = {campaign.campaign_id for campaign, _created in results}
    assert len(ids) == 1
    assert sum(1 for _campaign_value, created in results if created) == 1


def test_current_qualification_read_does_not_call_split_active_policy_reader(tmp_path):
    path = tmp_path / "current.sqlite3"
    campaign = _campaign("paper-current")
    _seed_campaign_parents(path, campaign)
    store = SQLiteQualificationStore(path)

    def forbidden_split_read():
        raise AssertionError("load_current_decision must resolve policy in one snapshot")

    store.load_active_policy = forbidden_split_read
    decision = store.load_current_decision(campaign.trial_id)

    assert decision is not None
    assert decision.decision_id == "historical-sqlite"


def test_current_wfa_helper_rejects_wfa_when_active_policy_has_changed(tmp_path):
    from core.research.research_artifact_store import ContentAddressedResearchArtifactStore
    from core.research.sqlite_candidate_wfa_store import SQLiteCandidateWfaStore

    path = tmp_path / "wfa-current.sqlite3"
    campaign = _campaign("paper-current")
    _seed_campaign_parents(path, campaign)
    store = SQLiteCandidateWfaStore(
        path,
        artifact_store=ContentAddressedResearchArtifactStore(tmp_path / "artifacts"),
    )

    assert (
        store.load_current_decision_if_historical_current(
            campaign.candidate_revision_id
        ).decision_id
        == campaign.wfa_decision_id
    )

    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        new_policy = fp("e")
        connection.execute(
            "INSERT INTO qualification_policies VALUES (?, 2, '60', ?)",
            (new_policy, (NOW + timedelta(seconds=1)).isoformat()),
        )
        connection.execute(
            "INSERT INTO qualification_policy_activations (policy_id, activated_at) VALUES (?, ?)",
            (new_policy, (NOW + timedelta(seconds=1)).isoformat()),
        )
        connection.commit()

    assert (
        store.load_current_decision_if_historical_current(
            campaign.candidate_revision_id
        )
        is None
    )


def test_campaign_persistence_rejects_policy_supersession(tmp_path):
    from core.research.sqlite_paper_campaign_store import PaperCampaignAuthorityConflict

    path = tmp_path / "campaign-authority.sqlite3"
    campaign = _campaign("paper-campaign-stale")
    _seed_campaign_parents(path, campaign)

    with sqlite3.connect(path) as connection:
        new_policy = fp("e")
        connection.execute(
            "INSERT INTO qualification_policies VALUES (?, 2, '60', ?)",
            (new_policy, (NOW + timedelta(seconds=1)).isoformat()),
        )
        connection.execute(
            "INSERT INTO qualification_policy_activations (policy_id, activated_at) VALUES (?, ?)",
            (new_policy, (NOW + timedelta(seconds=1)).isoformat()),
        )
        connection.commit()

    store = SQLitePaperCampaignStore(path)
    with pytest.raises(PaperCampaignAuthorityConflict):
        store.create_or_load_matching_campaign(campaign)
    assert store.load_campaign(campaign.campaign_id) is None


def test_session_registration_rejects_wfa_supersession(tmp_path):
    from core.research.models.paper_campaign import PaperCampaignSession, PaperCampaignSessionState
    from core.research.sqlite_paper_campaign_store import PaperCampaignAuthorityConflict

    path = tmp_path / "session-authority.sqlite3"
    campaign = _campaign("paper-campaign-current")
    _seed_campaign_parents(path, campaign)
    store = SQLitePaperCampaignStore(path)
    store.create_campaign(campaign)

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO candidate_wfa_decisions (
                decision_id, created_at, evaluator_version,
                study_revision_id, trial_id, candidate_revision_id,
                historical_qualification_decision_id,
                evaluator_repository_revision,
                dataset_reference_artifact_id, dataset_id, dataset_fingerprint,
                wfa_configuration_fingerprint, result_artifact_id,
                evidence_validity, wfa_verdict, outcome, reason
            ) VALUES ('wfa-decision-2', ?, 'fixture', ?, ?, ?, 'historical-sqlite',
                      'revision-1', ?, ?, ?, ?, ?,
                      'VALID', 'PASS', 'ELIGIBLE', 'fixture')
            """,
            (
                (NOW + timedelta(seconds=1)).isoformat(),
                campaign.study_revision_id,
                campaign.trial_id,
                campaign.candidate_revision_id,
                fp("b"), fp("0"), fp("1"), fp("2"), fp("c"),
            ),
        )
        connection.commit()

    session = PaperCampaignSession(
        session_id="paper-session-stale",
        campaign_id=campaign.campaign_id,
        created_at=NOW + timedelta(seconds=2),
        evaluator_repository_revision="revision-1",
        live_binding_id="angelone-reliance-v1",
        live_provider="angelone",
        live_provider_instrument_id="2885",
        live_provider_symbol="RELIANCE",
        state=PaperCampaignSessionState.CREATED,
    )
    with pytest.raises(PaperCampaignAuthorityConflict):
        store.register_session(session)
    assert store.load_session(session.session_id) is None


def _paper_session(campaign, session_id, created_at):
    from core.research.models.paper_campaign import (
        PaperCampaignSession,
        PaperCampaignSessionState,
    )

    return PaperCampaignSession(
        session_id=session_id,
        campaign_id=campaign.campaign_id,
        created_at=created_at,
        evaluator_repository_revision="revision-1",
        live_binding_id="angelone-reliance-v1",
        live_provider="angelone",
        live_provider_instrument_id="2885",
        live_provider_symbol="RELIANCE",
        state=PaperCampaignSessionState.CREATED,
    )


def test_session_registration_binds_exact_latest_observed_generation(tmp_path):
    from core.research.models.paper_campaign import PaperCampaignSessionState
    from core.research.sqlite_paper_campaign_store import (
        PaperCampaignAuthorityConflict,
    )

    path = tmp_path / "session-generation.sqlite3"
    campaign = _campaign("paper-campaign-generation")
    _seed_campaign_parents(path, campaign)
    store = SQLitePaperCampaignStore(path)
    store.create_campaign(campaign)

    first = _paper_session(
        campaign,
        "paper-session-a",
        NOW + timedelta(seconds=1),
    )
    store.register_session(
        first,
        expected_latest_session_id=None,
    )
    store.mark_running_if_created(
        first.session_id,
        started_at=NOW + timedelta(seconds=2),
    )
    store.terminalize_session(
        first.session_id,
        state=PaperCampaignSessionState.STOPPED,
        terminal_at=NOW + timedelta(seconds=3),
        terminal_snapshot_json="{}",
        failure_type=None,
        failure_message=None,
    )

    second = _paper_session(
        campaign,
        "paper-session-b",
        NOW + timedelta(seconds=4),
    )
    store.register_session(
        second,
        expected_latest_session_id=first.session_id,
    )
    store.mark_running_if_created(
        second.session_id,
        started_at=NOW + timedelta(seconds=5),
    )
    store.terminalize_session(
        second.session_id,
        state=PaperCampaignSessionState.STOPPED,
        terminal_at=NOW + timedelta(seconds=6),
        terminal_snapshot_json="{}",
        failure_type=None,
        failure_message=None,
    )

    stale = _paper_session(
        campaign,
        "paper-session-stale",
        NOW + timedelta(seconds=7),
    )
    with pytest.raises(
        PaperCampaignAuthorityConflict,
        match="generation changed since caller observation",
    ):
        store.register_session(
            stale,
            expected_latest_session_id=first.session_id,
        )

    assert store.load_session(stale.session_id) is None
    assert [
        item.session_id
        for item in store.list_sessions(campaign.campaign_id)
    ] == [first.session_id, second.session_id]
