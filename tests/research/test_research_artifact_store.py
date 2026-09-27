from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import os

import pytest

from core.config.backtest_economic_policy import BACKTEST_ECONOMIC_POLICY
from core.config.execution_config import ExecutionConfig
from core.market_data.historical_coverage import TimeRange
from core.research.models.backtest_run_manifest import BacktestRunManifest
from core.research.models.research_catalog import ResearchArtifactKind
from core.research.reproducibility import (
    BACKTEST_RUN_MANIFEST_SCHEMA,
    backtest_run_manifest_bytes,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
    research_artifact_reference,
)
from core.runtime.dataset_context import DatasetContext


INDIA = timezone(timedelta(hours=5, minutes=30))
CREATED_AT = datetime(
    2026,
    9,
    27,
    10,
    30,
    tzinfo=INDIA,
)


def manifest() -> BacktestRunManifest:
    start = datetime(
        2026,
        9,
        25,
        9,
        15,
        tzinfo=INDIA,
    )

    return BacktestRunManifest(
        dataset_context=DatasetContext(
            "RELIANCE",
            "15m",
            "Asia/Kolkata",
        ),
        requested_range=TimeRange(
            start,
            start + timedelta(hours=1),
        ),
        dataset_fingerprint="sha256:" + "a" * 64,
        strategy_name="artifact-store-test",
        strategy_params={
            "fast": 5,
            "slow": 20,
        },
        initial_capital=100_000.0,
        effective_risk_per_trade_pct=1.0,
        execution_config=ExecutionConfig(
            slippage_pct=0.0,
            slippage_enabled=False,
            brokerage_enabled=False,
        ),
        economic_policy=BACKTEST_ECONOMIC_POLICY,
    )


def persist_example(store, payload, *, created_at=CREATED_AT):
    return store.persist_bytes(
        payload,
        artifact_kind=ResearchArtifactKind.BACKTEST_RESULT,
        schema_id="kanasu.artifact-test.v1",
        created_at=created_at,
    )


def test_persist_bytes_uses_content_identity_and_portable_reference(tmp_path):
    store = ContentAddressedResearchArtifactStore(
        tmp_path / "research_artifacts"
    )
    payload = b'{"artifact":"example"}'
    digest = hashlib.sha256(payload).hexdigest()

    artifact = persist_example(store, payload)

    assert artifact.artifact_id == f"sha256:{digest}"
    assert artifact.relative_path == (
        f"sha256/{digest[:2]}/{digest}.json"
    )
    assert "\\" not in artifact.relative_path
    assert artifact.byte_count == len(payload)
    assert research_artifact_reference(
        artifact.artifact_id
    ) == f"artifact:sha256:{digest}"
    assert store.load_bytes(artifact.artifact_id) == payload


def test_identical_bytes_reuse_one_physical_artifact(tmp_path):
    root = tmp_path / "research_artifacts"
    store = ContentAddressedResearchArtifactStore(root)
    payload = b"same exact bytes"

    first = persist_example(store, payload)
    second = persist_example(
        store,
        payload,
        created_at=CREATED_AT + timedelta(seconds=1),
    )

    assert second.artifact_id == first.artifact_id
    assert second.relative_path == first.relative_path
    assert list(root.rglob("*.json")) == [
        root.joinpath(*first.relative_path.split("/"))
    ]
    assert not list(root.rglob("*.tmp"))


def test_concurrent_identical_writes_publish_one_artifact(tmp_path):
    root = tmp_path / "research_artifacts"
    store = ContentAddressedResearchArtifactStore(root)
    payload = b"concurrent immutable bytes"

    def persist(_):
        return persist_example(store, payload)

    with ThreadPoolExecutor(max_workers=16) as executor:
        artifacts = list(
            executor.map(
                persist,
                range(64),
            )
        )

    assert len({
        artifact.artifact_id
        for artifact in artifacts
    }) == 1

    assert len(list(root.rglob("*.json"))) == 1
    assert list(root.rglob("*.tmp")) == []


def test_conflicting_existing_content_is_never_overwritten(tmp_path):
    root = tmp_path / "research_artifacts"
    store = ContentAddressedResearchArtifactStore(root)
    payload = b"original immutable bytes"

    artifact = persist_example(store, payload)
    path = root.joinpath(*artifact.relative_path.split("/"))

    path.write_bytes(b"conflicting bytes")

    with pytest.raises(
        RuntimeError,
        match="conflict",
    ):
        persist_example(store, payload)

    assert path.read_bytes() == b"conflicting bytes"


def test_load_rejects_corrupted_content(tmp_path):
    root = tmp_path / "research_artifacts"
    store = ContentAddressedResearchArtifactStore(root)

    artifact = persist_example(
        store,
        b"valid bytes",
    )
    path = root.joinpath(*artifact.relative_path.split("/"))
    path.write_bytes(b"corrupted")

    with pytest.raises(
        RuntimeError,
        match="does not match its identity",
    ):
        store.load_bytes(artifact.artifact_id)


def test_manifest_artifact_is_hash_of_existing_canonical_bytes(tmp_path):
    store = ContentAddressedResearchArtifactStore(
        tmp_path / "research_artifacts"
    )
    value = manifest()
    raw = backtest_run_manifest_bytes(value)

    artifact = store.persist_backtest_manifest(
        value,
        created_at=CREATED_AT,
    )

    assert artifact.artifact_kind is (
        ResearchArtifactKind.BACKTEST_RUN_MANIFEST
    )
    assert artifact.schema_id == BACKTEST_RUN_MANIFEST_SCHEMA
    assert artifact.artifact_id == (
        "sha256:" + hashlib.sha256(raw).hexdigest()
    )
    assert store.load_bytes(artifact.artifact_id) == raw


def test_artifact_identity_and_relative_path_ignore_machine_root(tmp_path):
    payload = b"portable artifact bytes"

    left = ContentAddressedResearchArtifactStore(
        tmp_path / "machine-a" / "artifacts"
    )
    right = ContentAddressedResearchArtifactStore(
        tmp_path / "machine-b" / "different-root"
    )

    left_artifact = persist_example(left, payload)
    right_artifact = persist_example(right, payload)

    assert left_artifact.artifact_id == right_artifact.artifact_id
    assert left_artifact.relative_path == right_artifact.relative_path


def test_invalid_metadata_is_rejected_before_file_publication(tmp_path):
    root = tmp_path / "research_artifacts"
    store = ContentAddressedResearchArtifactStore(root)

    with pytest.raises(ValueError, match="schema_id"):
        store.persist_bytes(
            b"must-not-be-published",
            artifact_kind=ResearchArtifactKind.BACKTEST_RESULT,
            schema_id="",
            created_at=CREATED_AT,
        )

    assert list(root.rglob("*.json")) == []
    assert list(root.rglob("*.tmp")) == []


def test_temporary_file_is_removed_when_publication_fails(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "research_artifacts"
    store = ContentAddressedResearchArtifactStore(root)

    def fail_link(*args, **kwargs):
        raise OSError("simulated publication failure")

    monkeypatch.setattr(os, "link", fail_link)

    with pytest.raises(
        OSError,
        match="simulated publication failure",
    ):
        persist_example(
            store,
            b"publication failure probe",
        )

    assert list(root.rglob("*.json")) == []
    assert list(root.rglob("*.tmp")) == []


def test_persist_bytes_rejects_mutable_byte_buffers(tmp_path):
    store = ContentAddressedResearchArtifactStore(
        tmp_path / "research_artifacts"
    )

    with pytest.raises(
        TypeError,
        match="exact bytes",
    ):
        store.persist_bytes(
            bytearray(b"mutable"),
            artifact_kind=ResearchArtifactKind.BACKTEST_RESULT,
            schema_id="kanasu.artifact-test.v1",
            created_at=CREATED_AT,
        )


@pytest.mark.parametrize(
    "artifact_id",
    [
        "",
        "sha256:ABC",
        "sha256:" + "g" * 64,
        "not-a-fingerprint",
    ],
)
def test_logical_artifact_reference_requires_valid_identity(artifact_id):
    with pytest.raises(ValueError, match="artifact_id"):
        research_artifact_reference(artifact_id)
