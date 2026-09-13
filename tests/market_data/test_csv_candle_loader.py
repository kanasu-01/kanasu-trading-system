from datetime import datetime

from core.data_loaders.csv_candle_loader import (
    load_candles_from_csv as load_legacy_csv,
)
from core.market_data.csv_candle_loader import (
    load_candles_from_csv as load_market_data_csv,
)


def test_csv_loader_import_paths_have_basic_parity(tmp_path):
    csv_path = tmp_path / "candles.csv"
    csv_path.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2026-01-02 09:15:00,100,101,99,100.5,1000\n"
        "2026-01-02 09:16:00,100.5,102,100,101.5,1200\n",
        encoding="utf-8",
    )

    legacy_result = load_legacy_csv(str(csv_path))
    market_data_result = load_market_data_csv(str(csv_path))

    assert len(legacy_result) == len(market_data_result) == 2
    assert legacy_result == market_data_result
    assert [candle.timestamp for candle in legacy_result] == [
        datetime(2026, 1, 2, 9, 15),
        datetime(2026, 1, 2, 9, 16),
    ]
    assert [
        (
            candle.open,
            candle.high,
            candle.low,
            candle.close,
            candle.volume,
        )
        for candle in legacy_result
    ] == [
        (100.0, 101.0, 99.0, 100.5, 1000.0),
        (100.5, 102.0, 100.0, 101.5, 1200.0),
    ]


def test_csv_loader_import_paths_support_fractional_iso_timestamp(tmp_path):
    csv_path = tmp_path / "fractional_timestamp.csv"
    csv_path.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2026-01-02T09:15:00.123456,100,101,99,100.5,1000\n",
        encoding="utf-8",
    )

    market_data_result = load_market_data_csv(str(csv_path))
    legacy_result = load_legacy_csv(str(csv_path))

    assert legacy_result == market_data_result
    assert legacy_result == [market_data_result[0]]
    assert legacy_result[0].timestamp == datetime(2026, 1, 2, 9, 15, 0, 123456)
