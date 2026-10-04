"""Versioned durable reference joining dataset identity and provenance."""

from dataclasses import dataclass

from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange
from core.research.models.dataset import (
    DatasetIdentityV2,
    DatasetProvenance,
    PriceAdjustmentBasis,
    ProviderBindingProvenance,
)
from core.research.reproducibility import (
    canonical_bytes,
    decode_canonical_bytes,
)


DATASET_REFERENCE_SCHEMA_ID = "kanasu.dataset-reference.v1"


def _range_payload(value):
    return {
        "start": value.start,
        "end": value.end,
    }


def _candle_payload(candle):
    return {
        "timestamp": candle.timestamp,
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "volume": candle.volume,
    }


@dataclass(frozen=True)
class DatasetReference:
    """
    One durable successor dataset reference.

    Canonical dataset identity remains separate from acquisition
    provenance. This wrapper proves that both records describe the
    same dataset before they are serialized as research evidence.
    """

    identity: DatasetIdentityV2
    provenance: DatasetProvenance

    def __post_init__(self) -> None:
        if not isinstance(
            self.identity,
            DatasetIdentityV2,
        ):
            raise TypeError(
                "identity must be a DatasetIdentityV2"
            )

        if not isinstance(
            self.provenance,
            DatasetProvenance,
        ):
            raise TypeError(
                "provenance must be a DatasetProvenance"
            )

        comparisons = (
            (
                "dataset_id",
                self.identity.dataset_id,
                self.provenance.dataset_id,
            ),
            (
                "instrument_id",
                self.identity.instrument_id,
                self.provenance.instrument_id,
            ),
            (
                "requested_range",
                self.identity.requested_range,
                self.provenance.requested_range,
            ),
            (
                "timeframe",
                self.identity.timeframe,
                self.provenance.timeframe,
            ),
            (
                "timezone",
                self.identity.timezone,
                self.provenance.timezone,
            ),
            (
                "price_adjustment_basis",
                self.identity.price_adjustment_basis,
                self.provenance.price_adjustment_basis,
            ),
        )

        for field_name, identity_value, provenance_value in comparisons:
            if identity_value != provenance_value:
                raise ValueError(
                    "dataset identity/provenance mismatch: "
                    f"{field_name}"
                )


def dataset_reference_payload(
    reference: DatasetReference,
) -> dict:
    """Return the complete inspectable successor dataset reference."""

    if not isinstance(reference, DatasetReference):
        raise TypeError(
            "reference must be a DatasetReference"
        )

    identity = reference.identity
    provenance = reference.provenance

    return {
        "dataset": {
            "dataset_id": identity.dataset_id,
            "instrument_id": identity.instrument_id,
            "requested_range": _range_payload(
                identity.requested_range
            ),
            "timeframe": identity.timeframe,
            "timezone": identity.timezone,
            "price_adjustment_basis": (
                identity.price_adjustment_basis.value
            ),
            "candles": [
                _candle_payload(candle)
                for candle in identity.candles
            ],
        },
        "provenance": {
            "dataset_id": provenance.dataset_id,
            "instrument_id": provenance.instrument_id,
            "requested_range": _range_payload(
                provenance.requested_range
            ),
            "timeframe": provenance.timeframe,
            "timezone": provenance.timezone,
            "price_adjustment_basis": (
                provenance.price_adjustment_basis.value
            ),
            "source": provenance.source,
            "binding_segments": [
                {
                    "binding_id": segment.binding_id,
                    "provider": segment.provider,
                    "applied_range": _range_payload(
                        segment.applied_range
                    ),
                }
                for segment in provenance.binding_segments
            ],
            "coverage": [
                _range_payload(interval)
                for interval in provenance.coverage
            ],
            "coverage_status": (
                provenance.coverage_status.value
            ),
            "retrieved_at": provenance.retrieved_at,
            "as_of": provenance.as_of,
            "limitations": list(
                provenance.limitations
            ),
        },
    }


def dataset_reference_bytes(
    reference: DatasetReference,
) -> bytes:
    """Serialize one dataset reference under its independent schema."""

    return canonical_bytes(
        dataset_reference_payload(reference),
        schema=DATASET_REFERENCE_SCHEMA_ID,
    )



def _require_exact_mapping(
    value,
    *,
    field_name,
    keys,
):
    if (
        not isinstance(value, dict)
        or set(value) != set(keys)
    ):
        raise ValueError(
            f"{field_name} must contain exactly "
            + ", ".join(sorted(keys))
        )

    return value


def _decode_range(
    value,
    *,
    field_name,
):
    value = _require_exact_mapping(
        value,
        field_name=field_name,
        keys=("start", "end"),
    )

    return TimeRange(
        value["start"],
        value["end"],
    )


def _decode_candle(value):
    value = _require_exact_mapping(
        value,
        field_name="dataset candle",
        keys=(
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ),
    )

    return Candle(
        timestamp=value["timestamp"],
        open=value["open"],
        high=value["high"],
        low=value["low"],
        close=value["close"],
        volume=value["volume"],
    )


def decode_dataset_reference_bytes(
    payload: bytes,
) -> DatasetReference:
    """
    Strictly decode and semantically re-validate one durable
    successor DatasetReference.
    """

    decoded = decode_canonical_bytes(
        payload,
        schema=DATASET_REFERENCE_SCHEMA_ID,
    )

    decoded = _require_exact_mapping(
        decoded,
        field_name="dataset reference",
        keys=("dataset", "provenance"),
    )

    dataset = _require_exact_mapping(
        decoded["dataset"],
        field_name="dataset identity",
        keys=(
            "dataset_id",
            "instrument_id",
            "requested_range",
            "timeframe",
            "timezone",
            "price_adjustment_basis",
            "candles",
        ),
    )

    if not isinstance(
        dataset["candles"],
        list,
    ):
        raise ValueError(
            "dataset identity candles must be a list"
        )

    try:
        dataset_price_basis = PriceAdjustmentBasis(
            dataset["price_adjustment_basis"]
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            "dataset identity price_adjustment_basis "
            "is unsupported"
        ) from error

    identity = DatasetIdentityV2(
        instrument_id=dataset["instrument_id"],
        requested_range=_decode_range(
            dataset["requested_range"],
            field_name="dataset requested_range",
        ),
        timeframe=dataset["timeframe"],
        timezone=dataset["timezone"],
        price_adjustment_basis=(
            dataset_price_basis
        ),
        candles=[
            _decode_candle(value)
            for value in dataset["candles"]
        ],
    )

    if identity.dataset_id != dataset["dataset_id"]:
        raise ValueError(
            "dataset reference dataset_id does not "
            "match canonical DatasetIdentityV2"
        )

    provenance = _require_exact_mapping(
        decoded["provenance"],
        field_name="dataset provenance",
        keys=(
            "dataset_id",
            "instrument_id",
            "requested_range",
            "timeframe",
            "timezone",
            "price_adjustment_basis",
            "source",
            "binding_segments",
            "coverage",
            "coverage_status",
            "retrieved_at",
            "as_of",
            "limitations",
        ),
    )

    if not isinstance(
        provenance["binding_segments"],
        list,
    ):
        raise ValueError(
            "dataset provenance binding_segments "
            "must be a list"
        )

    if not isinstance(
        provenance["coverage"],
        list,
    ):
        raise ValueError(
            "dataset provenance coverage must be a list"
        )

    if not isinstance(
        provenance["limitations"],
        list,
    ):
        raise ValueError(
            "dataset provenance limitations must be a list"
        )

    try:
        provenance_price_basis = (
            PriceAdjustmentBasis(
                provenance[
                    "price_adjustment_basis"
                ]
            )
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            "dataset provenance price_adjustment_basis "
            "is unsupported"
        ) from error

    binding_segments = []

    for value in provenance["binding_segments"]:
        value = _require_exact_mapping(
            value,
            field_name="provider binding provenance",
            keys=(
                "binding_id",
                "provider",
                "applied_range",
            ),
        )

        binding_segments.append(
            ProviderBindingProvenance(
                binding_id=value["binding_id"],
                provider=value["provider"],
                applied_range=_decode_range(
                    value["applied_range"],
                    field_name=(
                        "provider binding applied_range"
                    ),
                ),
            )
        )

    reconstructed_provenance = DatasetProvenance(
        dataset_id=provenance["dataset_id"],
        instrument_id=provenance["instrument_id"],
        requested_range=_decode_range(
            provenance["requested_range"],
            field_name="provenance requested_range",
        ),
        timeframe=provenance["timeframe"],
        timezone=provenance["timezone"],
        price_adjustment_basis=(
            provenance_price_basis
        ),
        source=provenance["source"],
        binding_segments=binding_segments,
        coverage=[
            _decode_range(
                value,
                field_name="provenance coverage interval",
            )
            for value in provenance["coverage"]
        ],
        retrieved_at=provenance["retrieved_at"],
        as_of=provenance["as_of"],
        limitations=provenance["limitations"],
    )

    if (
        reconstructed_provenance
        .coverage_status
        .value
        != provenance["coverage_status"]
    ):
        raise ValueError(
            "dataset provenance coverage_status does not "
            "match reconstructed coverage"
        )

    return DatasetReference(
        identity=identity,
        provenance=reconstructed_provenance,
    )
