from datetime import datetime

from core.broker.angelone import AngelOneBroker
from core.broker.angelone_config import AngelOneConfig
from core.market_data.historical_feed import HistoricalFeed


def main():
    # 1️⃣ Create AngelOne config
    angelone_config = AngelOneConfig(
        api_key="YOUR_API_KEY",
        client_code="YOUR_CLIENT_CODE",
        password="YOUR_PASSWORD",
        totp="YOUR_TOTP",
        exchange="NSE",
        symbol_token_map={
            "RELIANCE": "2885",   # example token
        },
    )

    # 2️⃣ Create broker (historical API ENABLED)
    broker = AngelOneBroker(
        config=angelone_config,
        paper_mode=True,
        enable_historical_api=True,
    )

    # 3️⃣ Login
    broker.login()

    # 4️⃣ Create HistoricalFeed (unchanged code)
    feed = HistoricalFeed(broker)

    # 5️⃣ Load historical candles
    candles = feed.load(
        symbol="RELIANCE",
        timeframe="15m",
        start=datetime(2023, 1, 2),
        end=datetime(2023, 1, 10),
    )

    # 6️⃣ Basic validation prints
    print("Total candles:", len(candles))
    print("First candle:", candles[0])
    print("Last candle:", candles[-1])


if __name__ == "__main__":
    main()