from datetime import datetime, timedelta, timezone

import pytest

from core.broker.angelone import AngelOneBroker
from core.broker.angelone_config import AngelOneConfig
from core.entities.candle import Candle
from core.market_data.provider_instrument_binding import (
    ProviderBindingResolutionError,
    ProviderInstrumentBinding,
)


START = datetime(2026, 1, 2, 9, 15)
END = datetime(2026, 1, 2, 10, 15)


class FakeSmartAPI:
    def __init__(self, outcome):
        self.outcome = outcome
        self.requests = []

    def getCandleData(self, request):
        self.requests.append(request)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def broker_with_api_outcome(outcome) -> tuple[AngelOneBroker, FakeSmartAPI]:
    broker = AngelOneBroker(
        AngelOneConfig(
            api_key="api-key",
            client_id="client-id",
            client_pin="pin",
            symbol_token_map={"RELIANCE": "2885"},
        ),
        enable_historical_api=True,
    )
    api = FakeSmartAPI(outcome)
    broker._logged_in = True
    broker._api = api
    return broker, api


def fetch(broker: AngelOneBroker) -> list[Candle]:
    return broker.get_historical_candles(
        symbol="RELIANCE",
        timeframe="15m",
        start=START,
        end=END,
    )


def test_valid_empty_historical_response_returns_empty_list():
    broker, _ = broker_with_api_outcome({"data": []})

    assert fetch(broker) == []


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(None, id="response-is-not-dict"),
        pytest.param({}, id="missing-data"),
    ],
)
def test_missing_or_non_mapping_response_remains_an_error(response):
    broker, _ = broker_with_api_outcome(response)

    with pytest.raises(RuntimeError, match="response|data"):
        fetch(broker)


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(None, id="none"),
        pytest.param("not-a-collection", id="string"),
        pytest.param({}, id="mapping"),
        pytest.param(42, id="number"),
    ],
)
def test_invalid_historical_data_shape_remains_a_clear_error(data):
    broker, _ = broker_with_api_outcome({"data": data})

    with pytest.raises(RuntimeError, match="data"):
        fetch(broker)


def test_historical_api_exception_remains_an_error():
    broker, _ = broker_with_api_outcome(RuntimeError("provider unavailable"))

    with pytest.raises(RuntimeError, match="historical data request failed"):
        fetch(broker)


def test_malformed_historical_row_remains_an_error():
    broker, _ = broker_with_api_outcome({"data": [["not-a-timestamp"]]})

    with pytest.raises((ValueError, IndexError, TypeError)):
        fetch(broker)


def test_non_empty_historical_response_preserves_candle_parsing():
    response = {
        "data": [
            [
                "2026-01-02T09:15:00+05:30",
                "100",
                "101",
                "99",
                "100.5",
                "1000",
            ]
        ]
    }
    broker, api = broker_with_api_outcome(response)

    result = fetch(broker)

    assert result == [
        Candle(
            timestamp=datetime.fromisoformat(
                "2026-01-02T09:15:00+05:30"
            ),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1000.0,
        )
    ]
    assert api.requests == [
        {
            "exchange": "NSE",
            "symboltoken": "2885",
            "interval": "FIFTEEN_MINUTE",
            "fromdate": "2026-01-02 09:15",
            "todate": "2026-01-02 10:15",
        }
    ]


def test_aware_non_ist_bounds_are_converted_to_india_wall_time():
    broker, api = broker_with_api_outcome({"data": []})

    start = datetime(
        2026,
        1,
        2,
        3,
        45,
        tzinfo=timezone.utc,
    )
    end = datetime(
        2026,
        1,
        2,
        4,
        45,
        tzinfo=timezone.utc,
    )

    broker.get_historical_candles(
        symbol="RELIANCE",
        timeframe="15m",
        start=start,
        end=end,
    )

    assert api.requests == [
        {
            "exchange": "NSE",
            "symboltoken": "2885",
            "interval": "FIFTEEN_MINUTE",
            "fromdate": "2026-01-02 09:15",
            "todate": "2026-01-02 10:15",
        }
    ]



def provider_binding(
    *,
    provider: str = "angelone",
    provider_instrument_id: str = "9999",
    provider_exchange: str | None = "BSE",
    effective_from: datetime | None = None,
    effective_to: datetime | None = None,
) -> ProviderInstrumentBinding:
    return ProviderInstrumentBinding(
        binding_id="angelone-reliance-explicit",
        instrument_id="instrument:nse:eq:reliance",
        provider=provider,
        provider_instrument_id=provider_instrument_id,
        provider_exchange=provider_exchange,
        provider_segment="CASH",
        provider_symbol="RELIANCE-EQ",
        effective_from=effective_from,
        effective_to=effective_to,
    )


def test_explicit_provider_binding_drives_token_and_exchange():
    broker, api = broker_with_api_outcome({"data": []})

    # Deliberately make the legacy configuration unusable.
    broker.config.symbol_token_map = None
    broker.config.exchange = "LEGACY"

    broker.get_historical_candles(
        symbol="RELIANCE",
        timeframe="15m",
        start=START,
        end=END,
        provider_binding=provider_binding(),
    )

    assert api.requests == [
        {
            "exchange": "BSE",
            "symboltoken": "9999",
            "interval": "FIFTEEN_MINUTE",
            "fromdate": "2026-01-02 09:15",
            "todate": "2026-01-02 10:15",
        }
    ]


def test_explicit_provider_binding_rejects_non_angelone_provider():
    broker, api = broker_with_api_outcome({"data": []})

    with pytest.raises(ValueError, match="AngelOne"):
        broker.get_historical_candles(
            symbol="RELIANCE",
            timeframe="15m",
            start=START,
            end=END,
            provider_binding=provider_binding(
                provider="other-provider",
            ),
        )

    assert api.requests == []


def test_explicit_provider_binding_requires_exchange():
    broker, api = broker_with_api_outcome({"data": []})

    with pytest.raises(ValueError, match="provider_exchange"):
        broker.get_historical_candles(
            symbol="RELIANCE",
            timeframe="15m",
            start=START,
            end=END,
            provider_binding=provider_binding(
                provider_exchange=None,
            ),
        )

    assert api.requests == []


def test_explicit_provider_binding_must_cover_requested_range():
    broker, api = broker_with_api_outcome({"data": []})

    with pytest.raises(
        ProviderBindingResolutionError,
        match="gap",
    ):
        broker.get_historical_candles(
            symbol="RELIANCE",
            timeframe="15m",
            start=START,
            end=END,
            provider_binding=provider_binding(
                effective_from=START + timedelta(minutes=15),
            ),
        )

    assert api.requests == []
