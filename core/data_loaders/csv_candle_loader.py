from core.entities.candle import Candle
from core.market_data.csv_candle_loader import (
    load_candles_from_csv as canonical_load_candles_from_csv,
)


def load_candles_from_csv(file_path: str) -> list[Candle]:
    """Load candles through the canonical market-data CSV loader."""

    return canonical_load_candles_from_csv(file_path)
