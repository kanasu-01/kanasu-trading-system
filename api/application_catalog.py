"""Authoritative M8 application choices exposed through the API boundary."""

MARKETS = (
    {
        "id": "NSE",
        "name": "NSE",
    },
)

SYMBOLS = (
    {
        "symbol": "RELIANCE",
        "exchange": "NSE",
    },
)

TIMEFRAMES = (
    {
        "id": "5m",
        "label": "5 Minutes",
    },
    {
        "id": "15m",
        "label": "15 Minutes",
    },
)

STRATEGIES = (
    {
        "id": "sma_crossover",
        "name": "SMA Crossover",
    },
)

TIMEZONES = ("Asia/Kolkata",)

SUPPORTED_SYMBOLS = frozenset(
    item["symbol"] for item in SYMBOLS
)

SUPPORTED_TIMEFRAMES = frozenset(
    item["id"] for item in TIMEFRAMES
)

SUPPORTED_STRATEGIES = frozenset(
    item["id"] for item in STRATEGIES
)

SUPPORTED_TIMEZONES = frozenset(TIMEZONES)


def backtest_config_payload() -> dict:
    """Return a fresh Backtest configuration projection."""

    return {
        "markets": [dict(item) for item in MARKETS],
        "symbols": [dict(item) for item in SYMBOLS],
        "timeframes": [dict(item) for item in TIMEFRAMES],
        "strategies": [dict(item) for item in STRATEGIES],
        "timezones": list(TIMEZONES),
    }


def paper_trading_config_payload() -> dict:
    """Return a fresh Paper configuration projection."""

    return {
        "symbols": [dict(item) for item in SYMBOLS],
        "strategies": [dict(item) for item in STRATEGIES],
    }
