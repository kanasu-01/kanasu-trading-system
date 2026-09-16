from datetime import datetime, timedelta

import pytest

from core.backtest.backtest_engine import BacktestEngine
from core.backtest.pending_intent import PendingIntent
from core.config.execution_config import ExecutionConfig
from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.execution.execution_feedback import (
    ExecutionFeedback,
    ExecutionFeedbackType,
    ExecutionRejectionReason,
)
from core.execution.trade_execution_engine import TradeExecutionEngine
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.strategies.base_strategy import BaseStrategy
from core.strategies.signal import SignalType


START = datetime(2026, 1, 2, 9, 15)


def candle(
    index: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> Candle:
    return Candle(
        timestamp=START + timedelta(minutes=15 * index),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1000,
    )


def runtime_context(
    *,
    slippage_pct: float = 0.0,
    slippage_enabled: bool = False,
    brokerage_enabled: bool = False,
) -> RuntimeContext:
    return RuntimeContext(
        execution_config=ExecutionConfig(
            slippage_pct=slippage_pct,
            slippage_enabled=slippage_enabled,
            brokerage_enabled=brokerage_enabled,
        )
    )


class SequencedStrategy(BaseStrategy):
    def __init__(self, signals: dict[int, SignalType], midpoint: float | None = None):
        super().__init__(name="Sequenced")
        self.signals = signals
        self.initial_midpoint = midpoint
        self.rejection_midpoint = midpoint
        self.feedback: list[ExecutionFeedback] = []

    def on_new_candle(self, series: CandleSeries) -> SignalType | None:
        return self.signals.get(len(series))

    def on_execution_feedback(self, feedback: ExecutionFeedback) -> None:
        self.feedback.append(feedback)

    def reset(self) -> None:
        self.rejection_midpoint = self.initial_midpoint
        self.feedback = []


def engine(strategy: BaseStrategy | None = None, **execution_options):
    return TradeExecutionEngine(
        strategy=strategy or SequencedStrategy({}),
        account_capital=100000,
        session_id="m4.3-timing",
        runtime_context=runtime_context(**execution_options),
    )


def intent(
    signal: SignalType,
    *,
    decision_close: float = 100.0,
    rejection_midpoint: float | None = None,
) -> PendingIntent:
    return PendingIntent(
        signal=signal,
        decision_timestamp=START,
        decision_close=decision_close,
        rejection_midpoint=rejection_midpoint,
    )


def process_backtest(
    execution_engine: TradeExecutionEngine,
    *,
    pending_intent: PendingIntent | None,
    candle: Candle,
    execution_index: int,
    symbol: str,
) -> tuple[ExecutionFeedback, ...]:
    return execution_engine.process_backtest_candle(
        pending_signal=pending_intent.signal if pending_intent else None,
        decision_close=pending_intent.decision_close if pending_intent else None,
        rejection_midpoint=(
            pending_intent.rejection_midpoint if pending_intent else None
        ),
        candle=candle,
        execution_index=execution_index,
        symbol=symbol,
    )


def test_backtest_queues_completed_bar_signals_for_following_open() -> None:
    strategy = SequencedStrategy({1: SignalType.BUY, 2: SignalType.SELL})
    candles = [
        candle(0, open_price=99, high=101, low=99, close=100),
        candle(1, open_price=105, high=107, low=104, close=106),
        candle(2, open_price=110, high=112, low=109, close=111),
    ]
    backtest = BacktestEngine(
        strategy=strategy,
        initial_capital=100000,
        runtime_context=runtime_context(),
        dataset_context=DatasetContext(symbol="TEST"),
    )

    result = backtest.run(candles)

    assert [record.signal for record in result.bar_records] == ["BUY", "SELL", None]
    assert [record.execution_event for record in result.bar_records] == [
        None,
        "BUY",
        "SELL",
    ]
    assert result.bar_records[1].execution_price == 105
    assert result.bar_records[2].execution_price == 110
    assert result.trades[0].entry_time == candles[1].timestamp
    assert result.trades[0].exit_time == candles[2].timestamp
    assert result.trades[0].entry_price == 105
    assert result.trades[0].exit_price == 110


def test_queued_entry_uses_decision_close_stop_and_applies_slippage_once() -> None:
    execution_engine = engine(slippage_pct=0.01, slippage_enabled=True)
    entry_candle = candle(1, open_price=110, high=120, low=100, close=115)

    feedback = process_backtest(
        execution_engine,
        pending_intent=intent(SignalType.BUY, decision_close=100),
        candle=entry_candle,
        execution_index=1,
        symbol="TEST",
    )

    position = execution_engine.get_runtime_position("TEST")
    assert position is not None
    assert position.entry_price == 110 * 1.01
    assert position.stop_price == 98
    assert position.entry_index == 1
    assert feedback[0].fill_price == position.entry_price


def test_invalid_stop_against_post_slippage_fill_is_rejected() -> None:
    execution_engine = engine()

    feedback = process_backtest(
        execution_engine,
        pending_intent=intent(
            SignalType.BUY,
            decision_close=100,
            rejection_midpoint=101,
        ),
        candle=candle(1, open_price=100, high=102, low=99, close=101),
        execution_index=1,
        symbol="TEST",
    )

    assert execution_engine.get_runtime_position("TEST") is None
    assert feedback[0].event_type is ExecutionFeedbackType.ENTRY_REJECTED
    assert feedback[0].rejection_reason is ExecutionRejectionReason.INVALID_ENTRY


def test_backtest_snapshots_rejection_midpoint_at_decision_time() -> None:
    strategy = SequencedStrategy({1: SignalType.BUY}, midpoint=95)
    backtest = BacktestEngine(
        strategy=strategy,
        initial_capital=100000,
        runtime_context=runtime_context(),
        dataset_context=DatasetContext(symbol="TEST"),
    )
    candles = [
        candle(0, open_price=100, high=102, low=99, close=101),
        candle(1, open_price=100, high=103, low=96, close=102),
    ]

    def changing_stream():
        yield candles[0]
        strategy.rejection_midpoint = 200
        yield candles[1]

    backtest.run_stream(changing_stream())

    position = backtest.execution_engine.get_runtime_position("TEST")
    assert position is not None
    assert position.stop_price == pytest.approx(94.8)


def test_backtest_buy_and_sell_slippage_each_apply_once() -> None:
    execution_engine = engine(slippage_pct=0.01, slippage_enabled=True)
    process_backtest(
        execution_engine,
        pending_intent=intent(SignalType.BUY),
        candle=candle(1, open_price=110, high=113, low=100, close=112),
        execution_index=1,
        symbol="TEST",
    )

    feedback = process_backtest(
        execution_engine,
        pending_intent=intent(SignalType.SELL, decision_close=112),
        candle=candle(2, open_price=120, high=122, low=119, close=121),
        execution_index=2,
        symbol="TEST",
    )

    trade = execution_engine.completed_trades[0]
    assert trade.entry_price == 110 * 1.01
    assert trade.exit_price == 120 * 0.99
    assert feedback[0].fill_price == 120 * 0.99


def test_existing_position_stop_priority_and_reference_prices() -> None:
    ordinary = engine()
    process_backtest(
        ordinary,
        pending_intent=intent(SignalType.BUY),
        candle=candle(1, open_price=100, high=103, low=99, close=102),
        execution_index=1,
        symbol="TEST",
    )
    ordinary_feedback = process_backtest(
        ordinary,
        pending_intent=None,
        candle=candle(2, open_price=101, high=102, low=97, close=99),
        execution_index=2,
        symbol="TEST",
    )
    assert ordinary_feedback[0].event_type is ExecutionFeedbackType.PROTECTIVE_EXIT
    assert ordinary_feedback[0].fill_price == 98

    gap = engine(slippage_pct=0.01, slippage_enabled=True)
    process_backtest(
        gap,
        pending_intent=intent(SignalType.BUY),
        candle=candle(1, open_price=100, high=103, low=99, close=102),
        execution_index=1,
        symbol="TEST",
    )
    gap_feedback = process_backtest(
        gap,
        pending_intent=intent(SignalType.SELL, decision_close=102),
        candle=candle(2, open_price=95, high=100, low=94, close=99),
        execution_index=2,
        symbol="TEST",
    )
    assert [event.event_type for event in gap_feedback] == [
        ExecutionFeedbackType.PROTECTIVE_EXIT
    ]
    assert gap_feedback[0].fill_price == 95 * 0.99
    assert gap.completed_trades[0].exit_reason == "STOP_LOSS"


def test_next_open_entry_can_stop_later_on_same_candle_in_event_order() -> None:
    execution_engine = engine()

    feedback = process_backtest(
        execution_engine,
        pending_intent=intent(SignalType.BUY),
        candle=candle(1, open_price=100, high=102, low=97, close=99),
        execution_index=1,
        symbol="TEST",
    )

    assert [event.event_type for event in feedback] == [
        ExecutionFeedbackType.ENTRY_ACCEPTED,
        ExecutionFeedbackType.PROTECTIVE_EXIT,
    ]
    assert execution_engine.get_runtime_position("TEST") is None
    assert execution_engine.last_execution_event == "STOP_EXIT"
    assert execution_engine.last_execution_price == 98
    assert execution_engine.last_execution_quantity == feedback[-1].quantity


def test_final_signal_remains_unfilled_and_open_position_is_not_liquidated() -> None:
    final_signal_strategy = SequencedStrategy({1: SignalType.BUY})
    single_bar = BacktestEngine(
        strategy=final_signal_strategy,
        initial_capital=100000,
        runtime_context=runtime_context(),
        dataset_context=DatasetContext(symbol="TEST"),
    )
    single_result = single_bar.run(
        [candle(0, open_price=100, high=102, low=99, close=101)]
    )
    assert single_result.trades == []
    assert single_bar.execution_engine.get_runtime_position("TEST") is None
    assert single_result.bar_records[0].execution_event is None

    open_strategy = SequencedStrategy({1: SignalType.BUY, 2: SignalType.SELL})
    open_backtest = BacktestEngine(
        strategy=open_strategy,
        initial_capital=100000,
        runtime_context=runtime_context(),
        dataset_context=DatasetContext(symbol="TEST"),
    )
    open_result = open_backtest.run(
        [
            candle(0, open_price=100, high=102, low=99, close=100),
            candle(1, open_price=100, high=111, low=99, close=110),
        ]
    )
    position = open_backtest.execution_engine.get_runtime_position("TEST")
    assert position is not None
    assert open_result.trades == []
    assert open_result.bar_records[-1].signal == "SELL"
    assert open_result.bar_records[-1].execution_event == "BUY"
    assert open_result.bar_records[-1].equity == 102000


def test_open_time_exit_does_not_use_current_close_for_peak_equity() -> None:
    strategy = SequencedStrategy({1: SignalType.BUY, 2: SignalType.SELL})
    backtest = BacktestEngine(
        strategy=strategy,
        initial_capital=100000,
        runtime_context=runtime_context(),
        dataset_context=DatasetContext(symbol="TEST"),
    )

    result = backtest.run(
        [
            candle(0, open_price=100, high=101, low=99, close=100),
            candle(1, open_price=100, high=101, low=99, close=100),
            candle(2, open_price=90, high=200, low=89, close=200),
        ]
    )

    final_state = backtest.execution_engine.portfolio_manager.snapshot()
    assert result.trades[0].exit_price == 90
    assert final_state.peak_equity == 100000
    assert final_state.equity == 98000
    assert final_state.drawdown == -0.02


def test_pending_state_contradictions_remain_explicit() -> None:
    execution_engine = engine()

    with pytest.raises(RuntimeError, match="SELL.*FLAT"):
        process_backtest(
            execution_engine,
            pending_intent=intent(SignalType.SELL),
            candle=candle(1, open_price=100, high=101, low=99, close=100),
            execution_index=1,
            symbol="TEST",
        )

    process_backtest(
        execution_engine,
        pending_intent=intent(SignalType.BUY),
        candle=candle(1, open_price=100, high=103, low=99, close=102),
        execution_index=1,
        symbol="TEST",
    )
    with pytest.raises(RuntimeError, match="BUY.*LONG"):
        process_backtest(
            execution_engine,
            pending_intent=intent(SignalType.BUY),
            candle=candle(2, open_price=102, high=104, low=101, close=103),
            execution_index=2,
            symbol="TEST",
        )


def test_legacy_on_signal_remains_immediate_for_non_backtest_callers() -> None:
    execution_engine = engine()
    current = candle(0, open_price=90, high=101, low=89, close=100)

    execution_engine.on_signal(
        signal=SignalType.BUY,
        candle=current,
        series=CandleSeries([current]),
        symbol="TEST",
    )

    position = execution_engine.get_runtime_position("TEST")
    assert position is not None
    assert position.entry_price == current.close
