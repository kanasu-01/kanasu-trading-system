"""Permanent M9.4q IND-01 through IND-04 regressions (ChatGPT-authored).

Original published baseline: 9f41a54c0c31985e4d33069401279586782c1858.
The eight parametrized cases in this module are included in GitHub Actions
run 39482590794 (1684 passed) for reviewed correction e6002758f22e0bb07d0886dcc1603eba21e6e501.
Codex independently audited that exact SHA, ran the complete 1684-test suite
and 122 additional reviewer-authored tests, and returned runtime PASS.
M9.5 remains blocked pending final approved milestone integration and
independent acceptance of the exact published milestone HEAD.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from core.market_data.historical_coverage import TimeRange
from core.research.models.registered_study import (
    EvidenceReusePolicy,
    Study,
    TrialDisposition,
)
from core.research.models.research_catalog import (
    ComputationKind,
    ResearchArtifact,
    ResearchArtifactKind,
)
from core.research.models.universe import (
    UniverseDefinition,
    UniverseQuality,
    UniverseSnapshot,
)
from core.research.registered_study_registration import (
    RegisteredStudyRegistrationService,
)
from core.research.reproducibility import (
    BACKTEST_RUN_MANIFEST_SCHEMA,
    canonical_fingerprint,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
)
from core.research.registered_trial_execution_plan import (
    RegisteredTrialExecutionPlanResolver,
)
from core.research.study_aggregation import StudyAggregationService
from core.research.sqlite_research_catalog_store import SQLiteResearchCatalogStore

UTC = timezone.utc
JAN = datetime(2020, 1, 1, tzinfo=UTC)
FEB = datetime(2020, 2, 1, tzinfo=UTC)
MAR = datetime(2020, 3, 1, tzinfo=UTC)
APR = datetime(2020, 4, 1, tzinfo=UTC)
MAY = datetime(2020, 5, 1, tzinfo=UTC)


def environment(tmp_path):
    catalog = SQLiteResearchCatalogStore(tmp_path / "research.sqlite3")
    artifacts = ContentAddressedResearchArtifactStore(tmp_path / "artifacts")
    catalog.save_study(Study(
        study_id="study-ind-identity",
        created_at=JAN,
        display_title="identity-boundary-regression",
    ))
    registration = RegisteredStudyRegistrationService(
        catalog_store=catalog, artifact_store=artifacts,
    )
    universe = UniverseDefinition(name="identity-universe", selection_spec="fixture")
    snapshot = UniverseSnapshot(
        definition=universe,
        members=("NSE:A",),
        quality=UniverseQuality.PIT_VERIFIED,
        as_of=JAN,
        provenance_refs=("independent-source",),
        effective_from=JAN,
        effective_to=FEB,
    )
    population = registration.register_study_revision(
        study_id="study-ind-identity",
        research_intent="Verify immutable registered Trial consumption",
        strategy_procedure_id="fixture-v1",
        timeframe="1d",
        research_range=TimeRange(JAN, FEB),
        timezone="UTC",
        initial_capital=1_000_000.0,
        risk_economic_configuration={"risk_per_trade_pct": 1.0},
        parameter_variants=({"variant": 1},),
        universe_definition=universe,
        universe_snapshots=(snapshot,),
        require_point_in_time=True,
        data_treatment_basis={"price_adjustment": "raw"},
        repository_revision="repo-ind-identity",
        evidence_reuse_policy=EvidenceReusePolicy.FORCE_NEW_EXECUTION,
        registered_at=MAR,
    )
    return catalog, artifacts, population


def corrupt_trial_instrument(catalog, trial_id):
    with closing(sqlite3.connect(catalog.database_path)) as connection:
        with connection:
            connection.execute(
                "UPDATE trials SET instrument_id = ? WHERE trial_id = ?",
                ("NSE:FOREIGN", trial_id),
            )


def raw_started_and_job_count(catalog, revision_id):
    with closing(sqlite3.connect(catalog.database_path)) as connection:
        started = connection.execute(
            "SELECT initial_batch_started_at FROM study_revisions WHERE study_revision_id=?",
            (revision_id,),
        ).fetchone()[0]
        count = connection.execute(
            "SELECT COUNT(*) FROM research_jobs WHERE trial_id IN "
            "(SELECT trial_id FROM trials WHERE study_revision_id=?)",
            (revision_id,),
        ).fetchone()[0]
    return started, count


def test_ind01_resolver_never_uses_unvalidated_initial_trial(monkeypatch, tmp_path):
    catalog, artifacts, population = environment(tmp_path)
    trial = population.trials[0]
    resolver = RegisteredTrialExecutionPlanResolver(
        catalog_store=catalog,
        artifact_store=artifacts,
    )
    # Simulate a contradictory initial row repaired before the validated
    # registered-population snapshot is loaded.
    corrupt_early_trial = replace(
        trial, membership_episode_end=trial.membership_episode_end - timedelta(days=1),
    )
    monkeypatch.setattr(catalog, "load_trial", lambda _: corrupt_early_trial)
    plan = resolver.resolve(trial.trial_id)
    assert plan.trial_range.end == trial.membership_episode_end
    assert plan.trial_id == trial.trial_id


def test_ind01_aggregation_consumes_validated_trial_snapshot(monkeypatch, tmp_path):
    catalog, artifacts, population = environment(tmp_path)
    # The old aggregation path consumes a generic read. A canonical
    # aggregation must instead consume the validated registered snapshot.
    def forbidden_unvalidated_read(_):
        raise AssertionError("unvalidated Trial reader was used")

    monkeypatch.setattr(
        catalog, "list_trials_for_revision", forbidden_unvalidated_read,
    )
    result = StudyAggregationService(
        catalog_store=catalog, artifact_store=artifacts,
    ).aggregate_revision(population.revision.study_revision_id)
    assert result.pending_trials == 1
    assert result.failed_trials == 0
    assert result.total_registered_trials == 1


def test_ind03_start_rejects_corrupt_identity_atomically(tmp_path):
    catalog, _, population = environment(tmp_path)
    rev = population.revision.study_revision_id
    corrupt_trial_instrument(catalog, population.trials[0].trial_id)
    with pytest.raises(ValueError):
        catalog.start_study_revision_batch(rev, APR)
    assert raw_started_and_job_count(catalog, rev) == (None, 0)


def test_ind04_trial_detail_rejects_corrupt_registered_identity(tmp_path):
    catalog, _, population = environment(tmp_path)
    trial_id = population.trials[0].trial_id
    corrupt_trial_instrument(catalog, trial_id)
    with pytest.raises(ValueError):
        catalog.load_research_trial_detail_snapshot(trial_id)


def test_ind02_attempt_binding_rechecks_after_preparation(tmp_path):
    catalog, _, population = environment(tmp_path)
    rev = population.revision.study_revision_id
    trial_id = population.trials[0].trial_id
    catalog.start_study_revision_batch(rev, APR)
    job = catalog.claim_next_research_job(
        rev, "worker-ind02", MAY, max_running_jobs=1,
    )
    assert job is not None
    manifest_id = canonical_fingerprint(
        {"label": "ind02-manifest"}, schema=BACKTEST_RUN_MANIFEST_SCHEMA,
    )
    catalog.save_artifact(ResearchArtifact(
        artifact_id=manifest_id,
        artifact_kind=ResearchArtifactKind.BACKTEST_RUN_MANIFEST,
        schema_id=BACKTEST_RUN_MANIFEST_SCHEMA,
        relative_path="m94q-ind02/manifest.json",
        byte_count=2,
        created_at=APR,
    ))
    spec = catalog.resolve_experiment_spec(
        computation_kind=ComputationKind.BACKTEST,
        manifest_artifact_id=manifest_id,
        dataset_fingerprint=canonical_fingerprint(
            {"label": "dataset"}, schema="kanasu.test.ind02-dataset.v1",
        ),
        configuration_fingerprint=canonical_fingerprint(
            {"label": "config"}, schema="kanasu.test.ind02-config.v1",
        ),
        repository_revision="repo-ind-identity",
        created_at=APR,
    )
    corrupt_trial_instrument(catalog, trial_id)
    with pytest.raises(ValueError):
        catalog._bind_trial_spec_create_attempt_for_running_job(
            job_id=job.job_id,
            experiment_spec_id=spec.experiment_spec_id,
            attempt_created_at=MAY,
        )
    with closing(sqlite3.connect(catalog.database_path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM run_attempts").fetchone()[0] == 0
        assert connection.execute(
            "SELECT attempt_id FROM research_jobs WHERE job_id=?", (job.job_id,),
        ).fetchone()[0] is None


def test_valid_registered_identity_control(tmp_path):
    catalog, artifacts, population = environment(tmp_path)
    rev = population.revision.study_revision_id
    trial = population.trials[0]
    plan = RegisteredTrialExecutionPlanResolver(
        catalog_store=catalog, artifact_store=artifacts,
    ).resolve(trial.trial_id)
    assert plan.trial_id == trial.trial_id
    assert plan.trial_range.end == trial.membership_episode_end
    detail = catalog.load_research_trial_detail_snapshot(trial.trial_id)
    assert detail is not None and detail.trial.trial_id == trial.trial_id
    first = catalog.start_study_revision_batch(rev, APR)
    second = catalog.start_study_revision_batch(rev, APR)
    assert first.study_revision_id == second.study_revision_id == rev
    assert raw_started_and_job_count(catalog, rev)[1] == 1

# Public application boundary must reject before modifying durable Start state.
def _application_config(catalog, artifacts):
    from core.config.app_config import AppConfig
    return AppConfig(
        research_database_path=str(catalog.database_path),
        research_artifact_root=str(artifacts.root_directory),
        research_max_workers=2,
    )


def test_ind03_application_start_failure_preserves_unstarted_state(tmp_path):
    from api.research_application import start_research_revision

    catalog, artifacts, population = environment(tmp_path)
    revision_id = population.revision.study_revision_id
    corrupt_trial_instrument(catalog, population.trials[0].trial_id)
    config = _application_config(catalog, artifacts)

    with pytest.raises(ValueError):
        start_research_revision(
            revision_id,
            started_at=APR,
            app_config=config,
        )

    assert raw_started_and_job_count(catalog, revision_id) == (None, 0)


def test_ind04_application_trial_detail_rejects_corrupt_identity(tmp_path):
    from api.research_application import get_research_trial_detail

    catalog, artifacts, population = environment(tmp_path)
    trial_id = population.trials[0].trial_id
    corrupt_trial_instrument(catalog, trial_id)

    with pytest.raises(ValueError):
        get_research_trial_detail(
            trial_id,
            app_config=_application_config(catalog, artifacts),
        )
