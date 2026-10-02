from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import api.research_application as application
from core.config.app_config import AppConfig
from core.market_data.historical_coverage import TimeRange
from core.research.models.registered_study import (
    EvidenceReusePolicy,
    ResearchQueueSnapshot,
    Study,
    TrialDisposition,
)
from core.research.models.universe import (
    UniverseDefinition,
    UniverseQuality,
    UniverseSnapshot,
)


NOW = datetime(
    2026,
    10,
    2,
    12,
    0,
    tzinfo=timezone.utc,
)

LATER = datetime(
    2026,
    10,
    2,
    12,
    5,
    tzinfo=timezone.utc,
)

REVISION_ID = "sha256:" + ("a" * 64)
PLAN_ARTIFACT_ID = "sha256:" + ("b" * 64)
TRIAL_ID = "sha256:" + ("c" * 64)


def _config(tmp_path) -> AppConfig:
    return AppConfig(
        research_database_path=str(
            tmp_path / "research.sqlite3"
        ),
        research_artifact_root=str(
            tmp_path / "artifacts"
        ),
        research_max_trials_per_revision=50,
        research_max_workers=2,
    )


def _snapshot(
    *,
    pending=1,
    cancelled=0,
    queued=1,
    cancelled_jobs=0,
) -> ResearchQueueSnapshot:
    return ResearchQueueSnapshot(
        study_revision_id=REVISION_ID,
        initial_batch_started_at=NOW,
        total_registered_trials=1,
        pending_trials=pending,
        executed_trials=0,
        reused_trials=0,
        invalid_trials=0,
        insufficient_trials=0,
        failed_trials=0,
        cancelled_trials=cancelled,
        interrupted_trials=0,
        queued_jobs=queued,
        running_jobs=0,
        succeeded_jobs=0,
        failed_jobs=0,
        cancelled_jobs=cancelled_jobs,
        interrupted_jobs=0,
    )


class RecordingStore:
    def __init__(
        self,
        *,
        study=None,
        revision=None,
        trials=(),
        snapshot=None,
    ):
        self.study = study
        self.revision = revision
        self.trials = tuple(trials)
        self.snapshot_value = (
            snapshot
            if snapshot is not None
            else _snapshot()
        )

        self.saved_studies = []
        self.metadata_updates = []
        self.revision_requests = []
        self.trial_list_requests = []
        self.cancel_requests = []

    def save_study(self, study):
        self.saved_studies.append(study)
        self.study = study
        return study

    def load_study(self, study_id):
        if (
            self.study is not None
            and self.study.study_id == study_id
        ):
            return self.study

        return None

    def update_study_metadata(
        self,
        study_id,
        *,
        display_title,
        archived,
    ):
        self.metadata_updates.append(
            (
                study_id,
                display_title,
                archived,
            )
        )

        if self.study is None:
            raise ValueError(
                f"Study does not exist: {study_id}"
            )

        self.study = Study(
            study_id=self.study.study_id,
            created_at=self.study.created_at,
            display_title=display_title,
            archived=archived,
        )

        return self.study

    def load_study_revision(
        self,
        study_revision_id,
    ):
        self.revision_requests.append(
            study_revision_id
        )

        if (
            self.revision is not None
            and self.revision.study_revision_id
            == study_revision_id
        ):
            return self.revision

        return None

    def list_trials_for_revision(
        self,
        study_revision_id,
    ):
        self.trial_list_requests.append(
            study_revision_id
        )
        return self.trials

    def cancel_study_revision_batch(
        self,
        *,
        study_revision_id,
        requested_at,
    ):
        self.cancel_requests.append(
            (
                study_revision_id,
                requested_at,
            )
        )
        return tuple()

    def load_research_queue_snapshot(
        self,
        study_revision_id,
    ):
        assert (
            study_revision_id
            == REVISION_ID
        )
        return self.snapshot_value


def _revision():
    return SimpleNamespace(
        study_revision_id=REVISION_ID,
        study_id="study-001",
        revision_number=1,
        plan_artifact_id=PLAN_ARTIFACT_ID,
        repository_revision="repo-rev-001",
        evidence_reuse_policy=(
            EvidenceReusePolicy.FORCE_NEW_EXECUTION
        ),
        registered_at=NOW,
        initial_batch_started_at=None,
    )


def _trial():
    return SimpleNamespace(
        trial_id=TRIAL_ID,
        study_revision_id=REVISION_ID,
        instrument_id="NSE:A",
        membership_episode_start=NOW,
        membership_episode_end=LATER,
        disposition=TrialDisposition.PENDING,
        disposition_at=NOW,
        experiment_spec_id=None,
        reused_attempt_id=None,
        failure_classification=None,
        failure_message=None,
    )


def test_create_study_assigns_opaque_id_and_persists(
    tmp_path,
    monkeypatch,
):
    store = RecordingStore()

    monkeypatch.setattr(
        application,
        "SQLiteResearchCatalogStore",
        lambda _path: store,
    )

    create = getattr(
        application,
        "create_research_study",
    )

    response = create(
        "Cross-sectional SMA study",
        app_config=_config(tmp_path),
        study_id_factory=(
            lambda: "study-generated-001"
        ),
        clock=lambda: NOW,
    )

    assert len(store.saved_studies) == 1

    saved = store.saved_studies[0]

    assert saved.study_id == "study-generated-001"
    assert saved.created_at == NOW
    assert (
        saved.display_title
        == "Cross-sectional SMA study"
    )
    assert saved.archived is False

    assert response.study_id == saved.study_id
    assert response.created_at == NOW
    assert (
        response.display_title
        == saved.display_title
    )
    assert response.archived is False


def test_reopen_study_preserves_identity_title_and_creation_time(
    tmp_path,
    monkeypatch,
):
    original = Study(
        study_id="study-001",
        created_at=NOW,
        display_title="Original title",
        archived=True,
    )
    store = RecordingStore(
        study=original
    )

    monkeypatch.setattr(
        application,
        "SQLiteResearchCatalogStore",
        lambda _path: store,
    )

    reopen = getattr(
        application,
        "reopen_research_study",
    )

    response = reopen(
        "study-001",
        app_config=_config(tmp_path),
    )

    assert store.metadata_updates == [
        (
            "study-001",
            "Original title",
            False,
        )
    ]

    assert response.study_id == "study-001"
    assert response.created_at == NOW
    assert response.display_title == "Original title"
    assert response.archived is False


def test_register_revision_delegates_complete_population_registration(
    tmp_path,
    monkeypatch,
):
    study = Study(
        study_id="study-001",
        created_at=NOW,
        display_title="Research study",
    )
    store = RecordingStore(
        study=study
    )

    captured = {}

    class RecordingArtifactStore:
        def __init__(self, root):
            captured["artifact_root"] = str(root)

    class RecordingRegistrationService:
        def __init__(
            self,
            *,
            catalog_store,
            artifact_store,
            max_trials_per_revision,
        ):
            captured["catalog_store"] = catalog_store
            captured["artifact_store"] = artifact_store
            captured["limit"] = max_trials_per_revision

        def register_study_revision(
            self,
            **kwargs,
        ):
            captured["registration"] = kwargs

            return SimpleNamespace(
                revision=_revision(),
                trials=(_trial(),),
            )

    monkeypatch.setattr(
        application,
        "SQLiteResearchCatalogStore",
        lambda _path: store,
    )
    monkeypatch.setattr(
        application,
        "ContentAddressedResearchArtifactStore",
        RecordingArtifactStore,
        raising=False,
    )
    monkeypatch.setattr(
        application,
        "RegisteredStudyRegistrationService",
        RecordingRegistrationService,
        raising=False,
    )

    definition = UniverseDefinition(
        name="registered-api-universe",
        selection_spec="fixture",
    )

    snapshot = UniverseSnapshot(
        definition=definition,
        members=("NSE:A",),
        quality=UniverseQuality.PIT_VERIFIED,
        as_of=NOW,
        provenance_refs=("source-001",),
        effective_from=NOW,
        effective_to=LATER,
    )

    register = getattr(
        application,
        "register_research_revision",
    )

    response = register(
        study_id="study-001",
        research_intent="Test one frozen population",
        strategy_procedure_id="sma-crossover-v1",
        timeframe="1d",
        research_range=TimeRange(
            NOW,
            LATER,
        ),
        timezone="UTC",
        initial_capital=1_000_000.0,
        risk_economic_configuration={
            "risk_per_trade_pct": 1.0,
        },
        parameter_variants=(
            {
                "fast_period": 20,
                "slow_period": 50,
            },
        ),
        universe_definition=definition,
        universe_snapshots=(snapshot,),
        require_point_in_time=True,
        data_treatment_basis={
            "price_adjustment_basis": "RAW",
        },
        repository_revision="repo-rev-001",
        evidence_reuse_policy=(
            EvidenceReusePolicy.FORCE_NEW_EXECUTION
        ),
        registered_at=NOW,
        app_config=_config(tmp_path),
    )

    assert captured["catalog_store"] is store
    assert captured["limit"] == 50
    assert captured["registration"][
        "study_id"
    ] == "study-001"
    assert captured["registration"][
        "universe_definition"
    ] is definition
    assert captured["registration"][
        "universe_snapshots"
    ] == (snapshot,)

    assert response.study_revision_id == REVISION_ID
    assert response.study_id == "study-001"
    assert response.revision_number == 1
    assert response.total_registered_trials == 1


def test_list_trials_exposes_current_dispositions_without_filtering(
    tmp_path,
    monkeypatch,
):
    store = RecordingStore(
        revision=_revision(),
        trials=(_trial(),),
    )

    monkeypatch.setattr(
        application,
        "SQLiteResearchCatalogStore",
        lambda _path: store,
    )

    list_trials = getattr(
        application,
        "list_research_trials",
    )

    response = list_trials(
        REVISION_ID,
        app_config=_config(tmp_path),
    )

    assert store.revision_requests == [
        REVISION_ID
    ]
    assert store.trial_list_requests == [
        REVISION_ID
    ]

    assert response.study_revision_id == REVISION_ID
    assert response.total_registered_trials == 1
    assert len(response.trials) == 1

    item = response.trials[0]

    assert item.trial_id == TRIAL_ID
    assert item.instrument_id == "NSE:A"
    assert item.disposition == "PENDING"


def test_start_revision_uses_authoritative_bounded_queue_service(
    tmp_path,
    monkeypatch,
):
    store = RecordingStore(
        revision=_revision()
    )
    captured = {}

    class RecordingQueue:
        def __init__(
            self,
            *,
            catalog_store,
            app_config,
        ):
            captured["catalog_store"] = catalog_store
            captured["app_config"] = app_config

        def start_revision(
            self,
            study_revision_id,
            *,
            started_at,
        ):
            captured["start"] = (
                study_revision_id,
                started_at,
            )
            return _snapshot()

    monkeypatch.setattr(
        application,
        "SQLiteResearchCatalogStore",
        lambda _path: store,
    )
    monkeypatch.setattr(
        application,
        "ResearchJobQueueService",
        RecordingQueue,
        raising=False,
    )

    start = getattr(
        application,
        "start_research_revision",
    )

    response = start(
        REVISION_ID,
        started_at=NOW,
        app_config=_config(tmp_path),
    )

    assert captured["catalog_store"] is store
    assert captured["start"] == (
        REVISION_ID,
        NOW,
    )
    assert response.total_registered_trials == 1
    assert response.queued_jobs == 1
    assert response.total_jobs == 1


def test_cancel_revision_uses_durable_cancellation_then_truthful_snapshot(
    tmp_path,
    monkeypatch,
):
    store = RecordingStore(
        revision=_revision(),
        snapshot=_snapshot(
            pending=0,
            cancelled=1,
            queued=0,
            cancelled_jobs=1,
        ),
    )

    monkeypatch.setattr(
        application,
        "SQLiteResearchCatalogStore",
        lambda _path: store,
    )

    cancel = getattr(
        application,
        "cancel_research_revision",
    )

    response = cancel(
        REVISION_ID,
        requested_at=NOW,
        app_config=_config(tmp_path),
    )

    assert store.cancel_requests == [
        (
            REVISION_ID,
            NOW,
        )
    ]

    assert response.total_registered_trials == 1
    assert response.cancelled_trials == 1
    assert response.cancelled_jobs == 1


def test_aggregation_delegates_independent_account_service(
    tmp_path,
    monkeypatch,
):
    store = RecordingStore(
        revision=_revision()
    )
    captured = {}

    class RecordingArtifactStore:
        def __init__(self, root):
            captured["artifact_root"] = str(root)

    distribution = SimpleNamespace(
        count=1,
        mean=2.5,
        median=2.5,
        minimum=2.5,
        maximum=2.5,
        positive_count=1,
        positive_proportion=1.0,
    )

    aggregation = SimpleNamespace(
        study_revision_id=REVISION_ID,
        aggregation_basis=(
            "INDEPENDENT_TRIAL_ACCOUNT_DISTRIBUTION"
        ),
        total_registered_trials=2,
        result_bearing_trials=1,
        excluded_trials=1,
        pending_trials=0,
        executed_trials=1,
        reused_trials=0,
        invalid_trials=0,
        insufficient_trials=0,
        failed_trials=1,
        cancelled_trials=0,
        interrupted_trials=0,
        account_return_pct=distribution,
        max_equity_drawdown_pct=distribution,
        result_artifact_ids=(
            "sha256:" + ("d" * 64),
        ),
    )

    class RecordingAggregationService:
        def __init__(
            self,
            *,
            catalog_store,
            artifact_store,
        ):
            captured["catalog_store"] = catalog_store
            captured["artifact_store"] = artifact_store

        def aggregate_revision(
            self,
            study_revision_id,
        ):
            captured["revision_id"] = (
                study_revision_id
            )
            return aggregation

    monkeypatch.setattr(
        application,
        "SQLiteResearchCatalogStore",
        lambda _path: store,
    )
    monkeypatch.setattr(
        application,
        "ContentAddressedResearchArtifactStore",
        RecordingArtifactStore,
        raising=False,
    )
    monkeypatch.setattr(
        application,
        "StudyAggregationService",
        RecordingAggregationService,
        raising=False,
    )

    aggregate = getattr(
        application,
        "get_research_aggregation",
    )

    response = aggregate(
        REVISION_ID,
        app_config=_config(tmp_path),
    )

    assert captured["catalog_store"] is store
    assert captured["revision_id"] == REVISION_ID

    assert (
        response.aggregation_basis
        == "INDEPENDENT_TRIAL_ACCOUNT_DISTRIBUTION"
    )
    assert response.total_registered_trials == 2
    assert response.result_bearing_trials == 1
    assert response.excluded_trials == 1

    assert response.account_return_pct.count == 1
    assert response.account_return_pct.mean == 2.5

    assert not hasattr(
        response,
        "portfolio_return_pct",
    )
    assert not hasattr(
        response,
        "portfolio_pnl",
    )
