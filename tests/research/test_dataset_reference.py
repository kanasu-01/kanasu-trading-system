from datetime import datetime, timedelta, timezone

import pytest

from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange
from core.research.models.dataset import (
    DatasetIdentityV2,
    DatasetProvenance,
    PriceAdjustmentBasis,
    ProviderBindingProvenance,
)
from core.research.models.dataset_reference import (
    DATASET_REFERENCE_SCHEMA_ID,
    DatasetReference,
    dataset_reference_bytes,
    dataset_reference_payload,
    decode_dataset_reference_bytes,
)
from core.research.models.research_catalog import (
    ResearchArtifactKind,
)
from core.research.reproducibility import (
    canonical_bytes,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
)


INDIA = timezone(
    timedelta(hours=5, minutes=30)
)

START = datetime(
    2026,
    1,
    5,
    9,
    15,
    tzinfo=INDIA,
)

END = START + timedelta(minutes=30)

RETRIEVED_AT = datetime(
    2026,
    9,
    29,
    8,
    0,
    tzinfo=INDIA,
)


def candles():
    return [
        Candle(
            timestamp=START,
            open=100.0,
            high=102.0,
            low=99.0,
            close=101.0,
            volume=1000.0,
        ),
        Candle(
            timestamp=START + timedelta(minutes=15),
            open=101.0,
            high=103.0,
            low=100.0,
            close=102.0,
            volume=1200.0,
        ),
    ]


def identity():
    return DatasetIdentityV2(
        instrument_id="instrument:nse:eq:reliance",
        requested_range=TimeRange(
            START,
            END,
        ),
        timeframe="15m",
        timezone="Asia/Kolkata",
        price_adjustment_basis=(
            PriceAdjustmentBasis.UNKNOWN
        ),
        candles=candles(),
    )


def provenance(
    dataset,
    *,
    source="angelone",
    binding_id="angelone-reliance-a",
):
    return DatasetProvenance(
        dataset_id=dataset.dataset_id,
        instrument_id=dataset.instrument_id,
        requested_range=dataset.requested_range,
        timeframe=dataset.timeframe,
        timezone=dataset.timezone,
        price_adjustment_basis=(
            dataset.price_adjustment_basis
        ),
        source=source,
        binding_segments=(
            ProviderBindingProvenance(
                binding_id=binding_id,
                provider=source,
                applied_range=dataset.requested_range,
            ),
        ),
        coverage=(dataset.requested_range,),
        retrieved_at=RETRIEVED_AT,
        limitations=(
            "price adjustment basis is unknown",
        ),
    )


def reference(**provenance_changes):
    dataset = identity()

    return DatasetReference(
        identity=dataset,
        provenance=provenance(
            dataset,
            **provenance_changes,
        ),
    )


def test_dataset_reference_schema_is_independent_and_versioned():
    assert DATASET_REFERENCE_SCHEMA_ID == (
        "kanasu.dataset-reference.v1"
    )


def test_reference_requires_identity_and_provenance_to_match():
    first = identity()
    second = DatasetIdentityV2(
        instrument_id="instrument:nse:eq:other",
        requested_range=first.requested_range,
        timeframe=first.timeframe,
        timezone=first.timezone,
        price_adjustment_basis=(
            first.price_adjustment_basis
        ),
        candles=first.candles,
    )

    with pytest.raises(
        ValueError,
        match="dataset_id|instrument_id",
    ):
        DatasetReference(
            identity=first,
            provenance=provenance(second),
        )


def test_reference_bytes_are_deterministic():
    first = reference()
    second = reference()

    assert first.identity.dataset_id == (
        second.identity.dataset_id
    )

    assert dataset_reference_bytes(first) == (
        dataset_reference_bytes(second)
    )


def test_provenance_changes_artifact_bytes_not_dataset_identity():
    first = reference(
        source="angelone",
        binding_id="binding-a",
    )

    second = reference(
        source="alternate-provider",
        binding_id="binding-b",
    )

    assert first.identity.dataset_id == (
        second.identity.dataset_id
    )

    assert dataset_reference_bytes(first) != (
        dataset_reference_bytes(second)
    )


def test_reference_serialization_contains_exact_binding_subrange():
    value = dataset_reference_bytes(
        reference()
    )

    assert b"angelone-reliance-a" in value
    assert b"instrument:nse:eq:reliance" in value
    assert b"kanasu.dataset-reference.v1" in value


def test_artifact_store_persists_versioned_dataset_reference(
    tmp_path,
):
    value = reference()

    store = ContentAddressedResearchArtifactStore(
        tmp_path / "artifacts"
    )

    artifact = store.persist_dataset_reference(
        value,
        created_at=RETRIEVED_AT,
    )

    assert (
        artifact.artifact_kind
        is ResearchArtifactKind.DATASET_REFERENCE
    )

    assert artifact.schema_id == (
        DATASET_REFERENCE_SCHEMA_ID
    )

    assert store.load_bytes(
        artifact.artifact_id
    ) == dataset_reference_bytes(value)

    repeated = store.persist_dataset_reference(
        value,
        created_at=RETRIEVED_AT,
    )

    assert repeated == artifact



def test_dataset_reference_strict_decoder_round_trips():
    value = reference()

    assert decode_dataset_reference_bytes(
        dataset_reference_bytes(value)
    ) == value


def test_dataset_reference_strict_decoder_rejects_false_dataset_id():
    value = reference()
    payload = dataset_reference_payload(
        value
    )

    payload["dataset"]["dataset_id"] = (
        "sha256:" + ("0" * 64)
    )

    forged = canonical_bytes(
        payload,
        schema=DATASET_REFERENCE_SCHEMA_ID,
    )

    with pytest.raises(
        ValueError,
        match="dataset_id",
    ):
        decode_dataset_reference_bytes(
            forged
        )
