from datetime import datetime, timedelta, timezone

import pytest

from core.entities.candle import Candle
from core.market_data.historical_feed import HistoricalFeed


START = datetime(2026, 1, 2, 9, 15)


def candle_after(
    minutes: int,
    *,
    tzinfo=None,
    open_price: float = 100.0,
    high: float = 102.0,
    low: float = 99.0,
    close: float = 101.0,
    volume: float = 1000.0,
) -> Candle:
    timestamp = (START + timedelta(minutes=minutes)).replace(tzinfo=tzinfo)
    return Candle(
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


class FakeHistoricalBroker:
    def __init__(self, chunks: list[list[Candle]]):
        self.chunks = chunks
        self.requests = []

    def get_historical_limits(self) -> dict:
        return {"15m": 1}

    def get_historical_candles(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        self.requests.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "start": start,
                "end": end,
            }
        )
        return list(self.chunks[len(self.requests) - 1])


def collect_chunks(
    chunks: list[list[Candle]],
) -> tuple[list[Candle], FakeHistoricalBroker]:
    broker = FakeHistoricalBroker(chunks)
    feed = HistoricalFeed(broker=broker, request_delay_sec=0)
    request_start = datetime(2026, 1, 1)

    result = list(
        feed.stream(
            symbol="RELIANCE",
            timeframe="15m",
            start=request_start,
            end=request_start + timedelta(days=len(chunks)),
        )
    )
    return result, broker


def test_empty_and_single_chunk_stream_unchanged():
    empty_result, _ = collect_chunks([[]])
    candles = [candle_after(0), candle_after(15), candle_after(30)]
    single_chunk_result, _ = collect_chunks([candles])

    assert empty_result == []
    assert single_chunk_result == candles


def test_multiple_non_overlapping_chunks_stream_every_candle_once():
    expected = [
        candle_after(0),
        candle_after(15),
        candle_after(30),
        candle_after(45),
    ]

    result, _ = collect_chunks([expected[:2], expected[2:]])

    assert result == expected


def test_same_chunk_duplicate_is_rejected():
    chunk = [
        candle_after(0),
        candle_after(15),
        candle_after(15),
        candle_after(30),
    ]

    with pytest.raises(ValueError, match="duplicate|chunk"):
        collect_chunks([chunk])


def test_one_candle_exact_overlap_is_skipped():
    expected = [
        candle_after(0),
        candle_after(15),
        candle_after(30),
        candle_after(45),
    ]

    result, _ = collect_chunks([expected[:3], expected[2:]])

    assert result == expected


def test_out_of_order_exact_overlap_within_later_chunk_is_rejected():
    first_chunk = [candle_after(0), candle_after(15), candle_after(30)]
    second_chunk = [candle_after(30), candle_after(15), candle_after(45)]

    with pytest.raises(
        ValueError,
        match="chronological|out-of-order|older|chunk",
    ):
        collect_chunks([first_chunk, second_chunk])


def test_multi_candle_exact_overlap_is_skipped():
    expected = [candle_after(minutes) for minutes in range(0, 91, 15)]
    first_chunk = expected[:5]
    second_chunk = expected[1:]

    result, _ = collect_chunks([first_chunk, second_chunk])

    assert result == expected


def test_twenty_candle_exact_overlap_is_skipped():
    overlapping = [candle_after(index * 15) for index in range(20)]
    new_candles = [candle_after(300), candle_after(315)]

    result, _ = collect_chunks(
        [overlapping, overlapping + new_candles]
    )

    assert result == overlapping + new_candles


def test_fully_repeated_chunk_is_skipped():
    first_chunk = [candle_after(0), candle_after(15), candle_after(30)]
    final_chunk = [candle_after(45), candle_after(60)]

    result, _ = collect_chunks(
        [first_chunk, list(first_chunk), final_chunk]
    )

    assert result == first_chunk + final_chunk


def test_conflicting_candle_inside_overlap_is_rejected():
    first_chunk = [
        candle_after(0),
        candle_after(15),
        candle_after(30),
        candle_after(45),
    ]
    second_chunk = [
        candle_after(15),
        candle_after(30, close=100.0),
        candle_after(45),
        candle_after(60),
    ]

    with pytest.raises(ValueError, match="conflict"):
        collect_chunks([first_chunk, second_chunk])


def test_same_timestamp_with_different_full_candle_is_rejected():
    original = candle_after(30, close=101.0)
    conflicting = candle_after(30, close=100.0)

    with pytest.raises(ValueError, match="conflict"):
        collect_chunks([[original], [conflicting]])


def test_never_seen_delayed_candle_is_rejected_as_out_of_order():
    first_chunk = [candle_after(0), candle_after(15), candle_after(45)]
    second_chunk = [candle_after(15), candle_after(30), candle_after(60)]

    with pytest.raises(
        ValueError,
        match="delayed|out-of-order|chronological|older|overlap",
    ):
        collect_chunks([first_chunk, second_chunk])


@pytest.mark.parametrize(
    ("latest_timezone", "incoming_timezone"),
    [
        pytest.param(None, timezone.utc, id="naive-then-aware"),
        pytest.param(timezone.utc, None, id="aware-then-naive"),
    ],
)
def test_mixed_timezone_awareness_is_rejected(
    latest_timezone,
    incoming_timezone,
):
    latest = candle_after(0, tzinfo=latest_timezone)
    incoming = candle_after(15, tzinfo=incoming_timezone)

    with pytest.raises(ValueError, match="timezone"):
        collect_chunks([[latest], [incoming]])


def test_adjacent_requests_share_the_chunk_boundary():
    _, broker = collect_chunks([[candle_after(0)], [candle_after(15)]])

    assert broker.requests[0]["end"] == broker.requests[1]["start"]


def test_never_seen_older_candle_is_not_silently_sorted():
    out_of_order_chunk = [candle_after(15), candle_after(0)]

    with pytest.raises(
        ValueError,
        match="delayed|out-of-order|chronological|older|overlap",
    ):
        collect_chunks([out_of_order_chunk])
