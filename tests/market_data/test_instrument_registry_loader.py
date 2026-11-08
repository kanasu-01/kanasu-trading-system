import json
from datetime import datetime, timezone

import pytest

from core.market_data.instrument_registry import InstrumentRegistryError
from core.market_data.instrument_registry_loader import load_instrument_registry


def payload():
    return {
        "schema": "kanasu.instrument-registry-config.v1",
        "instruments": [
            {
                "instrument_id": "NSE-EQ-RELIANCE",
                "symbol": "RELIANCE",
                "exchange": "NSE",
                "segment": "EQ",
                "tick_size": 0.05,
                "lot_size": 1,
                "effective_from": None,
                "effective_to": None,
            },
            {
                "instrument_id": "NSE-EQ-TCS",
                "symbol": "TCS",
                "exchange": "NSE",
                "segment": "EQ",
                "tick_size": 0.05,
                "lot_size": 1,
                "effective_from": None,
                "effective_to": None,
            },
        ],
        "provider_bindings": [
            {
                "binding_id": "angelone-nse-eq-reliance-v1",
                "instrument_id": "NSE-EQ-RELIANCE",
                "provider": "angelone",
                "provider_instrument_id": "2885",
                "provider_exchange": "NSE",
                "provider_segment": "nse_cm",
                "provider_symbol": "RELIANCE",
                "effective_from": None,
                "effective_to": None,
            },
            {
                "binding_id": "angelone-nse-eq-tcs-v1",
                "instrument_id": "NSE-EQ-TCS",
                "provider": "angelone",
                "provider_instrument_id": "11536",
                "provider_exchange": "NSE",
                "provider_segment": "nse_cm",
                "provider_symbol": "TCS",
                "effective_from": None,
                "effective_to": None,
            },
        ],
    }


def test_loader_builds_generic_multi_instrument_existing_registry_contract(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(payload()), encoding="utf-8")

    registry = load_instrument_registry(path)

    observed_at = datetime(2026, 1, 5, tzinfo=timezone.utc)
    assert registry.resolve_symbol(
        symbol="RELIANCE",
        exchange="NSE",
        at=observed_at,
    ).instrument_id == "NSE-EQ-RELIANCE"
    assert registry.resolve_symbol(
        symbol="TCS",
        exchange="NSE",
        at=observed_at,
    ).instrument_id == "NSE-EQ-TCS"
    binding = registry.bindings_for(
        instrument_id="NSE-EQ-TCS",
        provider="angelone",
    )[0]
    assert binding.provider_instrument_id == "11536"
    assert binding.provider_symbol == "TCS"


def test_loader_rejects_unknown_fields_instead_of_guessing(tmp_path):
    value = payload()
    value["instruments"][0]["guessed_token"] = "999"
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid fields"):
        load_instrument_registry(path)


def test_registry_unknown_symbol_fails_closed(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(payload()), encoding="utf-8")
    registry = load_instrument_registry(path)

    with pytest.raises(InstrumentRegistryError):
        registry.resolve_symbol(
            symbol="UNKNOWN",
            exchange="NSE",
            at=datetime(2026, 1, 5, tzinfo=timezone.utc),
        )
