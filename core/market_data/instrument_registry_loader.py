"""Load the repository-controlled M9.8 canonical instrument registry."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from core.entities.instrument import Instrument
from core.market_data.instrument_registry import StaticInstrumentRegistry
from core.market_data.provider_instrument_binding import ProviderInstrumentBinding


INSTRUMENT_REGISTRY_CONFIG_SCHEMA = "kanasu.instrument-registry-config.v1"


def _optional_datetime(value, field_name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be an ISO datetime string or null")
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return parsed


def _require_exact_keys(value: dict, expected: set[str], field_name: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        raise ValueError(
            f"{field_name} has invalid fields; missing={missing}, extra={extra}"
        )


def load_instrument_registry(path: str | Path) -> StaticInstrumentRegistry:
    """Load exact canonical instruments/provider bindings from one JSON file."""

    registry_path = Path(path)
    try:
        raw = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(
            f"instrument registry could not be loaded: {registry_path}"
        ) from error

    if not isinstance(raw, dict):
        raise ValueError("instrument registry root must be an object")
    _require_exact_keys(
        raw,
        {"schema", "instruments", "provider_bindings"},
        "instrument registry",
    )
    if raw["schema"] != INSTRUMENT_REGISTRY_CONFIG_SCHEMA:
        raise ValueError("unsupported instrument registry schema")
    if not isinstance(raw["instruments"], list) or not raw["instruments"]:
        raise ValueError("instrument registry requires at least one instrument")
    if not isinstance(raw["provider_bindings"], list) or not raw["provider_bindings"]:
        raise ValueError("instrument registry requires at least one provider binding")

    instruments = []
    for index, item in enumerate(raw["instruments"]):
        if not isinstance(item, dict):
            raise ValueError(f"instruments[{index}] must be an object")
        _require_exact_keys(
            item,
            {
                "instrument_id",
                "symbol",
                "exchange",
                "segment",
                "tick_size",
                "lot_size",
                "effective_from",
                "effective_to",
            },
            f"instruments[{index}]",
        )
        instruments.append(
            Instrument(
                instrument_id=item["instrument_id"],
                symbol=item["symbol"],
                exchange=item["exchange"],
                segment=item["segment"],
                tick_size=item["tick_size"],
                lot_size=item["lot_size"],
                effective_from=_optional_datetime(
                    item["effective_from"],
                    f"instruments[{index}].effective_from",
                ),
                effective_to=_optional_datetime(
                    item["effective_to"],
                    f"instruments[{index}].effective_to",
                ),
            )
        )

    bindings = []
    for index, item in enumerate(raw["provider_bindings"]):
        if not isinstance(item, dict):
            raise ValueError(f"provider_bindings[{index}] must be an object")
        _require_exact_keys(
            item,
            {
                "binding_id",
                "instrument_id",
                "provider",
                "provider_instrument_id",
                "provider_exchange",
                "provider_segment",
                "provider_symbol",
                "effective_from",
                "effective_to",
            },
            f"provider_bindings[{index}]",
        )
        bindings.append(
            ProviderInstrumentBinding(
                binding_id=item["binding_id"],
                instrument_id=item["instrument_id"],
                provider=item["provider"],
                provider_instrument_id=item["provider_instrument_id"],
                provider_exchange=item["provider_exchange"],
                provider_segment=item["provider_segment"],
                provider_symbol=item["provider_symbol"],
                effective_from=_optional_datetime(
                    item["effective_from"],
                    f"provider_bindings[{index}].effective_from",
                ),
                effective_to=_optional_datetime(
                    item["effective_to"],
                    f"provider_bindings[{index}].effective_to",
                ),
            )
        )

    return StaticInstrumentRegistry(
        instruments=tuple(instruments),
        provider_bindings=tuple(bindings),
    )
