from datetime import datetime, timedelta, timezone

import asyncio

import api.main as main_module
from core.config.app_config import AppConfig
from core.research.models.research_catalog import (
    ComputationKind,
    ResearchArtifact,
    ResearchArtifactKind,
    RunAttemptState,
)
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)


CREATED_AT = datetime(
    2026,
    9,
    28,
    3,
    30,
    tzinfo=timezone.utc,
)


def fingerprint(character: str) -> str:
    return f"sha256:{character * 64}"


def prepare_running_attempt(database_path):
    store = SQLiteResearchCatalogStore(
        database_path,
        attempt_id_factory=lambda: "attempt-startup-stale",
    )

    manifest = ResearchArtifact(
        artifact_id=fingerprint("a"),
        artifact_kind=(
            ResearchArtifactKind.BACKTEST_RUN_MANIFEST
        ),
        schema_id="kanasu.backtest-run-manifest.v1",
        relative_path=(
            "sha256/aa/" + "a" * 64 + ".json"
        ),
        byte_count=123,
        created_at=CREATED_AT,
    )
    store.save_artifact(manifest)

    spec = store.resolve_experiment_spec(
        computation_kind=ComputationKind.BACKTEST,
        manifest_artifact_id=manifest.artifact_id,
        dataset_fingerprint=fingerprint("b"),
        configuration_fingerprint=fingerprint("c"),
        repository_revision=(
            "0f4cc985cf73e2301971e07644058f057ddb7a09"
        ),
        created_at=CREATED_AT,
    )

    return store.create_running_attempt(
        experiment_spec_id=spec.experiment_spec_id,
        created_at=CREATED_AT,
        runtime_session_id="runtime-before-restart",
    )


async def run_application_lifespan():
    async with main_module.application_lifespan(
        main_module.app
    ):
        pass


def test_api_startup_recovers_stale_running_attempt(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "research.sqlite3"
    running = prepare_running_attempt(database_path)

    monkeypatch.setattr(
        main_module,
        "load_app_config",
        lambda: AppConfig(
            research_database_path=str(database_path),
            research_artifact_root=str(
                tmp_path / "research_artifacts"
            ),
        ),
    )

    asyncio.run(run_application_lifespan())

    recovered = SQLiteResearchCatalogStore(
        database_path
    ).load_run_attempt(running.attempt_id)

    assert recovered.state is RunAttemptState.INTERRUPTED
    assert recovered.terminal_at is not None
    assert recovered.runtime_session_id == (
        "runtime-before-restart"
    )
    assert recovered.result_artifact_id is None
    assert recovered.evidence_id is None
    assert (
        recovered.failure_classification
        == "application_restart"
    )

    persisted = SQLiteResearchCatalogStore(
        database_path
    ).load_run_attempt(running.attempt_id)

    assert persisted == recovered


def test_api_startup_recovery_is_idempotent(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "research.sqlite3"
    running = prepare_running_attempt(database_path)

    monkeypatch.setattr(
        main_module,
        "load_app_config",
        lambda: AppConfig(
            research_database_path=str(database_path),
            research_artifact_root=str(
                tmp_path / "research_artifacts"
            ),
        ),
    )

    asyncio.run(run_application_lifespan())

    first = SQLiteResearchCatalogStore(
        database_path
    ).load_run_attempt(running.attempt_id)

    asyncio.run(run_application_lifespan())

    second = SQLiteResearchCatalogStore(
        database_path
    ).load_run_attempt(running.attempt_id)

    assert first.state is RunAttemptState.INTERRUPTED
    assert second == first
