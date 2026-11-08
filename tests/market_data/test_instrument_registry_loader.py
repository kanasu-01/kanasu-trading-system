import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.market_data.historical_coverage import TimeRange
from core.market_data.instrument_registry import InstrumentRegistryError
from core.market_data.instrument_registry_loader import load_instrument_registry
from core.market_data.provider_instrument_binding import ProviderBindingResolutionError


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


def test_repository_bootstrap_bindings_start_at_verified_master_observation():
    repo_root = Path(__file__).resolve().parents[2]
    registry = load_instrument_registry(repo_root / "config" / "instrument_registry.json")
    observed_at = datetime.fromisoformat("2026-11-08T12:31:00.275890+00:00")

    for instrument_id in (
        "NSE-EQ-HDFCBANK",
        "NSE-EQ-INFY",
        "NSE-EQ-RELIANCE",
        "NSE-EQ-SBIN",
        "NSE-EQ-TCS",
    ):
        binding = registry.bindings_for(
            instrument_id=instrument_id,
            provider="angelone",
        )[0]
        assert binding.effective_from == observed_at
        assert binding.effective_to is None

        with pytest.raises(
            ProviderBindingResolutionError,
            match="coverage has a gap",
        ):
            registry.resolve_bindings(
                instrument_id=instrument_id,
                provider="angelone",
                request=TimeRange(
                    start=datetime(2026, 11, 8, 12, 30, tzinfo=timezone.utc),
                    end=datetime(2026, 11, 8, 12, 31, tzinfo=timezone.utc),
                ),
            )


def test_repository_bootstrap_snapshot_matches_registry_bindings():
    repo_root = Path(__file__).resolve().parents[2]
    snapshot = json.loads(
        (
            repo_root
            / "config"
            / "provider_snapshots"
            / "angelone_nse_eq_starter_2026-11-08.json"
        ).read_text(encoding="utf-8")
    )
    registry = load_instrument_registry(repo_root / "config" / "instrument_registry.json")

    assert snapshot["source_url"].endswith("OpenAPIScripMaster.json")
    assert snapshot["full_master_sha256"] == "92c425bd56f4edd48fe3f8aa859be39cbf472d8a64e821cc4322029568e81437"
    assert snapshot["full_master_record_count"] == 161793
    assert snapshot["observed_at"] == "2026-11-08T12:31:00.275890+00:00"

    by_symbol = {
        instrument.symbol: registry.bindings_for(
            instrument_id=instrument.instrument_id,
            provider="angelone",
        )[0]
        for instrument in registry.instruments
    }
    for provider_symbol, row in snapshot["selected_rows"].items():
        runtime_symbol = row["name"]
        binding = by_symbol[runtime_symbol]
        assert provider_symbol == f"{runtime_symbol}-EQ"
        assert binding.provider_instrument_id == str(row["token"])
        assert binding.provider_exchange == row["exch_seg"]
        assert binding.provider_symbol == runtime_symbol
