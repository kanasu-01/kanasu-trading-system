from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

import pytest

from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange
from core.research.models.dataset import (
    DATASET_ACQUISITION_STREAM_SCHEMA_ID,
    DATASET_V2_SCHEMA_ID,
    DatasetAcquisitionStreamIdentity,
    DatasetCoverageStatus,
    DatasetIdentityV2,
    DatasetProvenance,
    PriceAdjustmentBasis,
    ProviderBindingProvenance,
)
from core.research.reproducibility import DATASET_SCHEMA


INDIA = timezone(timedelta(hours=5, minutes=30))
START = datetime(
    2026,
    1,
    5,
    9,
    15,
    tzinfo=INDIA,
)
REQUEST = TimeRange(
    START,
    START + timedelta(hours=1),
)


def candle(
    minutes: int,
    *,
    close: float = 100.5,
) -> Candle:
    timestamp = START + timedelta(minutes=minutes)

    return Candle(
        timestamp=timestamp,
        open=100.0,
        high=max(110.0, close),
        low=min(90.0, close),
        close=close,
        volume=1000.0 + minutes,
    )


def candles():
    return [
        candle(0),
        candle(15, close=101.0),
        candle(30, close=102.0),
        candle(45, close=103.0),
    ]


def identity(**changes) -> DatasetIdentityV2:
    values = {
        "instrument_id": "NSE-EQ-RELIANCE",
        "requested_range": REQUEST,
        "timeframe": "15m",
        "timezone": "Asia/Kolkata",
        "price_adjustment_basis": (
            PriceAdjustmentBasis.UNKNOWN
        ),
        "candles": candles(),
    }
    values.update(changes)
    return DatasetIdentityV2(**values)


def segment(
    start_minutes: int,
    end_minutes: int,
    *,
    binding_id: str = "angelone-reliance-v1",
    provider: str = "ANGELONE",
) -> ProviderBindingProvenance:
    return ProviderBindingProvenance(
        binding_id=binding_id,
        provider=provider,
        applied_range=TimeRange(
            START + timedelta(minutes=start_minutes),
            START + timedelta(minutes=end_minutes),
        ),
    )


def provenance(**changes) -> DatasetProvenance:
    values = {
        "dataset_id": identity().dataset_id,
        "instrument_id": "NSE-EQ-RELIANCE",
        "requested_range": REQUEST,
        "timeframe": "15m",
        "timezone": "Asia/Kolkata",
        "price_adjustment_basis": (
            PriceAdjustmentBasis.UNKNOWN
        ),
        "source": "ANGELONE",
        "binding_segments": (
            segment(0, 60),
        ),
        "coverage": (
            REQUEST,
        ),
        "retrieved_at": datetime(
            2026,
            1,
            6,
            10,
            0,
            tzinfo=INDIA,
        ),
        "as_of": datetime(
            2026,
            1,
            6,
            9,
            59,
            tzinfo=INDIA,
        ),
    }
    values.update(changes)
    return DatasetProvenance(**values)


def stream(**changes) -> DatasetAcquisitionStreamIdentity:
    values = {
        "instrument_id": "NSE-EQ-RELIANCE",
        "provider": "ANGELONE",
        "binding_id": "angelone-reliance-v1",
        "timeframe": "15m",
        "timezone": "Asia/Kolkata",
        "price_adjustment_basis": (
            PriceAdjustmentBasis.UNKNOWN
        ),
    }
    values.update(changes)
    return DatasetAcquisitionStreamIdentity(**values)


def test_successor_schema_does_not_redefine_dataset_v1():
    assert DATASET_SCHEMA == "kanasu.dataset.v1"
    assert DATASET_V2_SCHEMA_ID == "kanasu.dataset.v2"
    assert DATASET_V2_SCHEMA_ID != DATASET_SCHEMA


def test_acquisition_stream_has_independent_versioned_schema():
    assert DATASET_ACQUISITION_STREAM_SCHEMA_ID == (
        "kanasu.dataset-acquisition-stream.v1"
    )


def test_price_adjustment_basis_meanings_are_exact():
    assert [
        value.value
        for value in PriceAdjustmentBasis
    ] == [
        "RAW",
        "ADJUSTED",
        "UNKNOWN",
    ]


def test_dataset_identity_is_deterministic():
    first = identity()
    second = identity()

    assert first.dataset_id == second.dataset_id
    assert first.dataset_id.startswith("sha256:")


def test_dataset_identity_normalizes_candles_to_tuple():
    value = identity()

    assert isinstance(value.candles, tuple)
    assert value.candles == tuple(candles())


@pytest.mark.parametrize(
    "changed",
    [
        lambda value: replace(
            value,
            instrument_id="NSE-EQ-TCS",
        ),
        lambda value: replace(
            value,
            requested_range=TimeRange(
                REQUEST.start,
                REQUEST.end - timedelta(minutes=15),
            ),
            candles=tuple(candles()[:-1]),
        ),
        lambda value: replace(
            value,
            timeframe="5m",
        ),
        lambda value: replace(
            value,
            timezone="UTC",
        ),
        lambda value: replace(
            value,
            price_adjustment_basis=(
                PriceAdjustmentBasis.RAW
            ),
        ),
        lambda value: replace(
            value,
            candles=(
                candle(0, close=104.0),
                *candles()[1:],
            ),
        ),
    ],
)
def test_dataset_identity_changes_with_canonical_content(
    changed,
):
    original = identity()
    different = changed(original)

    assert (
        original.dataset_id
        != different.dataset_id
    )


def test_unknown_adjustment_state_is_not_raw():
    unknown = identity(
        price_adjustment_basis=(
            PriceAdjustmentBasis.UNKNOWN
        )
    )
    raw = identity(
        price_adjustment_basis=(
            PriceAdjustmentBasis.RAW
        )
    )

    assert unknown.dataset_id != raw.dataset_id


def test_unknown_adjustment_state_is_not_adjusted():
    unknown = identity(
        price_adjustment_basis=(
            PriceAdjustmentBasis.UNKNOWN
        )
    )
    adjusted = identity(
        price_adjustment_basis=(
            PriceAdjustmentBasis.ADJUSTED
        )
    )

    assert unknown.dataset_id != adjusted.dataset_id


def test_dataset_identity_is_immutable():
    value = identity()

    with pytest.raises(FrozenInstanceError):
        value.instrument_id = "NSE-EQ-TCS"


def test_dataset_identity_rejects_duplicate_candles():
    duplicate = candle(0)

    with pytest.raises(
        ValueError,
        match="duplicate",
    ):
        identity(
            candles=(
                duplicate,
                duplicate,
            )
        )


def test_dataset_identity_rejects_nonchronological_candles():
    with pytest.raises(
        ValueError,
        match="chronological",
    ):
        identity(
            candles=(
                candle(15),
                candle(0),
            )
        )


def test_dataset_identity_rejects_candle_outside_request():
    with pytest.raises(
        ValueError,
        match="requested_range",
    ):
        identity(
            candles=(
                candle(0),
                candle(60),
            )
        )


def test_dataset_identity_rejects_awareness_mismatch():
    naive_request = TimeRange(
        REQUEST.start.replace(tzinfo=None),
        REQUEST.end.replace(tzinfo=None),
    )

    with pytest.raises(
        ValueError,
        match="timezone awareness",
    ):
        identity(
            requested_range=naive_request,
        )


def test_empty_confirmed_dataset_can_have_identity():
    value = identity(
        candles=(),
    )

    assert value.candles == ()
    assert value.dataset_id.startswith("sha256:")


def test_provider_provenance_is_outside_canonical_identity():
    canonical = identity()

    first = provenance(
        dataset_id=canonical.dataset_id,
        source="ANGELONE",
        binding_segments=(
            segment(
                0,
                60,
                binding_id="angelone-binding",
                provider="ANGELONE",
            ),
        ),
    )
    second = provenance(
        dataset_id=canonical.dataset_id,
        source="SECOND_SOURCE",
        binding_segments=(
            segment(
                0,
                60,
                binding_id="second-binding",
                provider="SECOND_SOURCE",
            ),
        ),
    )

    assert first.source != second.source
    assert (
        first.binding_segments
        != second.binding_segments
    )

    assert first.dataset_id == canonical.dataset_id
    assert second.dataset_id == canonical.dataset_id
    assert canonical.dataset_id == identity().dataset_id


def test_provenance_links_to_canonical_dataset_identity():
    canonical = identity()
    evidence = provenance(
        dataset_id=canonical.dataset_id,
    )

    assert evidence.dataset_id == canonical.dataset_id


def test_provenance_rejects_invalid_dataset_identity():
    with pytest.raises(
        ValueError,
        match="sha256",
    ):
        provenance(
            dataset_id="not-a-dataset-fingerprint",
        )


def test_provenance_retains_exact_binding_subranges():
    value = provenance(
        binding_segments=(
            segment(
                30,
                60,
                binding_id="binding-b",
            ),
            segment(
                0,
                30,
                binding_id="binding-a",
            ),
        )
    )

    assert [
        item.binding_id
        for item in value.binding_segments
    ] == [
        "binding-a",
        "binding-b",
    ]

    assert [
        item.applied_range
        for item in value.binding_segments
    ] == [
        TimeRange(
            START,
            START + timedelta(minutes=30),
        ),
        TimeRange(
            START + timedelta(minutes=30),
            START + timedelta(minutes=60),
        ),
    ]


def test_provenance_rejects_overlapping_binding_segments():
    with pytest.raises(
        ValueError,
        match="must not overlap",
    ):
        provenance(
            binding_segments=(
                segment(0, 40),
                segment(
                    30,
                    60,
                    binding_id="binding-b",
                ),
            )
        )


def test_provenance_rejects_binding_outside_request():
    outside = ProviderBindingProvenance(
        binding_id="binding-before",
        provider="ANGELONE",
        applied_range=TimeRange(
            START - timedelta(minutes=15),
            START + timedelta(minutes=15),
        ),
    )

    with pytest.raises(
        ValueError,
        match="contained",
    ):
        provenance(
            binding_segments=(outside,),
        )


def test_provenance_rejects_binding_awareness_mismatch():
    naive_segment = ProviderBindingProvenance(
        binding_id="naive-binding",
        provider="ANGELONE",
        applied_range=TimeRange(
            REQUEST.start.replace(tzinfo=None),
            REQUEST.end.replace(tzinfo=None),
        ),
    )

    with pytest.raises(
        ValueError,
        match="timezone awareness",
    ):
        provenance(
            binding_segments=(naive_segment,),
        )


def test_complete_coverage_is_derived_from_evidence():
    assert (
        provenance().coverage_status
        is DatasetCoverageStatus.COMPLETE
    )


def test_partial_coverage_is_derived_from_evidence():
    value = provenance(
        coverage=(
            TimeRange(
                START,
                START + timedelta(minutes=30),
            ),
        )
    )

    assert (
        value.coverage_status
        is DatasetCoverageStatus.PARTIAL
    )


def test_absent_coverage_evidence_remains_unknown():
    value = provenance(
        coverage=(),
    )

    assert (
        value.coverage_status
        is DatasetCoverageStatus.UNKNOWN
    )


def test_confirmed_empty_content_can_still_have_complete_coverage():
    canonical = identity(
        candles=(),
    )
    evidence = provenance(
        coverage=(REQUEST,),
    )

    assert canonical.candles == ()
    assert (
        evidence.coverage_status
        is DatasetCoverageStatus.COMPLETE
    )


def test_provenance_rejects_coverage_outside_request():
    outside = TimeRange(
        START,
        REQUEST.end + timedelta(minutes=15),
    )

    with pytest.raises(
        ValueError,
        match="contained",
    ):
        provenance(
            coverage=(outside,),
        )


@pytest.mark.parametrize(
    "field",
    [
        "retrieved_at",
        "as_of",
    ],
)
def test_provenance_retrieval_times_must_be_aware(
    field,
):
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        provenance(
            **{
                field: datetime(
                    2026,
                    1,
                    6,
                    10,
                    0,
                )
            }
        )


def test_provenance_limitations_are_immutable_and_deterministic():
    value = provenance(
        limitations=(
            "unknown corporate-action history",
            "provider retention policy",
        )
    )

    assert value.limitations == (
        "provider retention policy",
        "unknown corporate-action history",
    )


def test_provenance_rejects_duplicate_limitations():
    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        provenance(
            limitations=(
                "unknown adjustment history",
                "unknown adjustment history",
            )
        )


def test_acquisition_stream_identity_is_deterministic():
    first = stream()
    second = stream()

    assert first.stream_id == second.stream_id
    assert first.stream_id.startswith("sha256:")


@pytest.mark.parametrize(
    "changed",
    [
        {
            "provider": "SECOND_SOURCE",
        },
        {
            "binding_id": "angelone-reliance-v2",
        },
        {
            "price_adjustment_basis": (
                PriceAdjustmentBasis.RAW
            ),
        },
        {
            "instrument_id": "NSE-EQ-TCS",
        },
        {
            "timeframe": "5m",
        },
        {
            "timezone": "UTC",
        },
    ],
)
def test_incompatible_acquisition_streams_have_distinct_identity(
    changed,
):
    assert (
        stream().stream_id
        != stream(**changed).stream_id
    )


def test_acquisition_stream_identity_is_immutable():
    value = stream()

    with pytest.raises(FrozenInstanceError):
        value.binding_id = "different"
