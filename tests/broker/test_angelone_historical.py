from datetime import datetime

import pytest

from core.broker.angelone import AngelOneBroker
from core.broker.angelone_config import AngelOneConfig
from core.entities.candle import Candle


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
