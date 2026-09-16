from datetime import datetime, timedelta

import pytest

from core.entities.candle import Candle

from core.backtest.backtest_engine import (
    BacktestEngine,
)
from core.runtime.runtime_context import (
    RuntimeContext,
)
from core.runtime.dataset_context import (
    DatasetContext,
)
from core.strategies.base_strategy import BaseStrategy
from core.strategies.signal import SignalType

from core.strategies.sma_crossover_strategy import (
    SMACrossOverStrategy,
)
from core.execution.execution_feedback import ExecutionFeedback


def build_dummy_candles(count: int):

    candles = []

    base_time = datetime(2020, 1, 1)

    price = 100

    for i in range(count):

        if i % 20 < 10:
            price += 2
        else:
            price -= 2

        candles.append(
            Candle(
                timestamp=(base_time + timedelta(minutes=i)),
                open=price,
                high=price + 1,
                low=price - 1,
                close=price,
                volume=1000,
            )
        )

    return candles


class DeterministicRoundTripStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="DeterministicRoundTrip")
        self._candle_count = 0

    def on_new_candle(self, series):
        self._candle_count += 1

        if self._candle_count == 1:
            return SignalType.BUY

        if self._candle_count == 2:
            return SignalType.SELL

        return None

    def reset(self) -> None:
        self._candle_count = 0


class FeedbackSnapshotStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="FeedbackSnapshot")
        self._candle_count = 0
        self.feedback_received = False
        self.authoritative_position_lookup = None

    def on_new_candle(self, series):
        self._candle_count += 1
        return SignalType.BUY if self._candle_count == 1 else None

    def on_execution_feedback(self, feedback: ExecutionFeedback) -> None:
        assert self.authoritative_position_lookup is not None
        assert self.authoritative_position_lookup() is not None
        self.feedback_received = True

    def reset(self) -> None:
        self._candle_count = 0
        self.feedback_received = False

    def get_debug_state(self) -> dict:
        return {"feedback_received": self.feedback_received}


class FailingFeedbackStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="FailingFeedback")
        self._candle_count = 0

    def on_new_candle(self, series):
        self._candle_count += 1
        return SignalType.BUY if self._candle_count == 1 else None

    def on_execution_feedback(self, feedback: ExecutionFeedback) -> None:
        raise RuntimeError("feedback handler failed")

    def reset(self) -> None:
        self._candle_count = 0


def test_dataset_context_represents_symbol_and_optional_timeframe():
    dataset_context = DatasetContext(
        symbol="RELIANCE",
        timeframe="15m",
    )

    assert dataset_context.symbol == "RELIANCE"
    assert dataset_context.timeframe == "15m"

    symbol_only_context = DatasetContext(symbol="TEST")

    assert symbol_only_context.symbol == "TEST"
    assert symbol_only_context.timeframe is None


def test_backtest_engine_executes_successfully():

    candles = build_dummy_candles(500)

    strategy = SMACrossOverStrategy(
        params={
            "fast_period": 10,
            "slow_period": 30,
        }
    )

    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=100000,
        runtime_context=RuntimeContext(),
        dataset_context=DatasetContext(symbol="Test"),
    )

    result = engine.run(candles)

    assert result is not None

    assert result.session_id is not None

    assert result.bar_records is not None

    assert len(result.bar_records) > 0


def test_backtest_reports_authoritative_execution_portfolio_state():
    candles = build_dummy_candles(3)
    engine = BacktestEngine(
        strategy=DeterministicRoundTripStrategy(),
        initial_capital=100000,
        runtime_context=RuntimeContext(),
        dataset_context=DatasetContext(symbol="TEST"),
    )

    result = engine.run(candles)

    assert len(result.trades) == 1
    assert [record.execution_event for record in result.bar_records] == [
        None,
        "BUY",
        "SELL",
    ]

    final_record = result.bar_records[-1]
    authoritative_state = engine.execution_engine.portfolio_manager.snapshot()

    assert final_record.cash == authoritative_state.cash
    assert final_record.equity == authoritative_state.equity
    assert final_record.position_size == authoritative_state.position_size
    assert final_record.drawdown == authoritative_state.drawdown


def test_backtest_delivers_feedback_after_portfolio_transition_before_snapshot():
    strategy = FeedbackSnapshotStrategy()
    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=100000,
        runtime_context=RuntimeContext(),
        dataset_context=DatasetContext(symbol="TEST"),
    )
    strategy.authoritative_position_lookup = lambda: (
        engine.execution_engine.get_runtime_position("TEST")
    )

    result = engine.run(build_dummy_candles(2))

    assert strategy.feedback_received is True
    assert result.bar_records[1].decision_snapshot == {
        "feedback_received": True,
    }


def test_feedback_handler_failure_aborts_backtest():
    engine = BacktestEngine(
        strategy=FailingFeedbackStrategy(),
        initial_capital=100000,
        runtime_context=RuntimeContext(),
        dataset_context=DatasetContext(symbol="TEST"),
    )

    with pytest.raises(RuntimeError, match="feedback handler failed"):
        engine.run(build_dummy_candles(2))
