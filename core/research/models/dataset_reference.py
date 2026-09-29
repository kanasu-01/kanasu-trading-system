"""Versioned durable reference joining dataset identity and provenance."""

from dataclasses import dataclass

from core.research.models.dataset import (
    DatasetIdentityV2,
    DatasetProvenance,
)
from core.research.reproducibility import canonical_bytes


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
