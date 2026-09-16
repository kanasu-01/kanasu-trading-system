from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta

import pytest

from core.config.execution_config import ExecutionConfig
from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.execution.execution_feedback import (
    ExecutionFeedback,
    ExecutionFeedbackType,
    ExecutionPositionState,
    ExecutionRejectionReason,
)
from core.execution.trade_execution_engine import TradeExecutionEngine
from core.runtime.runtime_context import RuntimeContext
from core.strategies.base_strategy import BaseStrategy
from core.strategies.signal import SignalType
from core.strategies.sma_crossover_strategy import SMACrossOverStrategy
from core.strategies.strategy_runner import StrategyRunner


def candle(minute: int, *, close: float, low: float | None = None) -> Candle:
    return Candle(
        timestamp=datetime(2026, 1, 2, 9, 15) + timedelta(minutes=minute),
        open=close,
        high=close + 1,
        low=close - 1 if low is None else low,
        close=close,
        volume=1000,
    )


def engine(strategy: BaseStrategy | None = None) -> TradeExecutionEngine:
    return TradeExecutionEngine(
        strategy=strategy or SMACrossOverStrategy(),
        account_capital=100000,
        session_id="execution-feedback",
        runtime_context=RuntimeContext(
            execution_config=ExecutionConfig(
                slippage_enabled=False,
                brokerage_enabled=False,
            )
        ),
    )


def test_execution_feedback_is_immutable() -> None:
    feedback = ExecutionFeedback(
        event_type=ExecutionFeedbackType.ENTRY_ACCEPTED,
        symbol="TEST",
        timestamp=datetime(2026, 1, 2, 9, 15),
        position_state=ExecutionPositionState.LONG,
        fill_price=100.0,
        quantity=10,
    )

    with pytest.raises(FrozenInstanceError):
        feedback.quantity = 11  # type: ignore[misc]


def test_accepted_entry_and_strategy_exit_report_authoritative_outcomes() -> None:
    execution_engine = engine()
    series = CandleSeries([])

    entry_feedback = execution_engine.on_signal(
        signal=SignalType.BUY,
        candle=candle(0, close=100),
        series=series,
        symbol="TEST",
    )

    position = execution_engine.get_runtime_position("TEST")
    assert position is not None
    assert entry_feedback == (
        ExecutionFeedback(
            event_type=ExecutionFeedbackType.ENTRY_ACCEPTED,
            symbol="TEST",
            timestamp=datetime(2026, 1, 2, 9, 15),
            position_state=ExecutionPositionState.LONG,
            fill_price=position.entry_price,
            quantity=position.quantity,
        ),
    )

    exit_feedback = execution_engine.on_signal(
        signal=SignalType.SELL,
        candle=candle(15, close=110),
        series=series,
        symbol="TEST",
    )

    assert execution_engine.get_runtime_position("TEST") is None
    assert exit_feedback == (
        ExecutionFeedback(
            event_type=ExecutionFeedbackType.STRATEGY_EXIT,
            symbol="TEST",
            timestamp=datetime(2026, 1, 2, 9, 30),
            position_state=ExecutionPositionState.FLAT,
            fill_price=110,
            quantity=position.quantity,
        ),
    )
    assert len(execution_engine.completed_trades) == 1


@pytest.mark.parametrize(
    ("configure_rejection", "expected_reason"),
    [
        (
            lambda execution_engine, monkeypatch: monkeypatch.setattr(
                execution_engine.drawdown_manager,
                "can_trade",
                lambda: False,
            ),
            ExecutionRejectionReason.DRAWDOWN_LIMIT,
        ),
        (
            lambda execution_engine, monkeypatch: (
                setattr(execution_engine.strategy, "rejection_midpoint", 100.0),
                monkeypatch.setattr(
                    execution_engine.stop_manager,
                    "compute_long_stop",
                    lambda _midpoint: None,
                ),
            ),
            ExecutionRejectionReason.INVALID_ENTRY,
        ),
        (
            lambda execution_engine, monkeypatch: monkeypatch.setattr(
                execution_engine.risk_manager,
                "calculate_position_size",
                lambda **_kwargs: None,
            ),
            ExecutionRejectionReason.INVALID_QUANTITY,
        ),
        (
            lambda execution_engine, monkeypatch: monkeypatch.setattr(
                execution_engine.portfolio_risk_manager,
                "can_open_new_trade",
                lambda **_kwargs: False,
            ),
            ExecutionRejectionReason.PORTFOLIO_RISK_LIMIT,
        ),
    ],
)
def test_rejected_entry_reports_machine_readable_reason(
    monkeypatch,
    configure_rejection,
    expected_reason: ExecutionRejectionReason,
) -> None:
    execution_engine = engine()
    configure_rejection(execution_engine, monkeypatch)

    feedback = execution_engine.on_signal(
        signal=SignalType.BUY,
        candle=candle(0, close=100),
        series=CandleSeries([]),
        symbol="TEST",
    )

    assert execution_engine.get_runtime_position("TEST") is None
    assert feedback == (
        ExecutionFeedback(
            event_type=ExecutionFeedbackType.ENTRY_REJECTED,
            symbol="TEST",
            timestamp=datetime(2026, 1, 2, 9, 15),
            position_state=ExecutionPositionState.FLAT,
            rejection_reason=expected_reason,
        ),
    )


def test_protective_exit_feedback_follows_authoritative_close() -> None:
    execution_engine = engine()
    series = CandleSeries([])
    entry_feedback = execution_engine.on_signal(
        signal=SignalType.BUY,
        candle=candle(0, close=100),
        series=series,
        symbol="TEST",
    )
    quantity = entry_feedback[0].quantity

    feedback = execution_engine.on_signal(
        signal=None,
        candle=candle(15, close=99, low=97),
        series=series,
        symbol="TEST",
    )

    assert execution_engine.get_runtime_position("TEST") is None
    assert feedback == (
        ExecutionFeedback(
            event_type=ExecutionFeedbackType.PROTECTIVE_EXIT,
            symbol="TEST",
            timestamp=datetime(2026, 1, 2, 9, 30),
            position_state=ExecutionPositionState.FLAT,
            fill_price=98,
            quantity=quantity,
        ),
    )


def test_contradictory_signal_and_portfolio_state_fail_explicitly() -> None:
    execution_engine = engine()
    series = CandleSeries([])

    with pytest.raises(RuntimeError, match="SELL.*FLAT"):
        execution_engine.on_signal(
            signal=SignalType.SELL,
            candle=candle(0, close=100),
            series=series,
            symbol="TEST",
        )

    execution_engine.on_signal(
        signal=SignalType.BUY,
        candle=candle(15, close=100),
        series=series,
        symbol="TEST",
    )

    with pytest.raises(RuntimeError, match="BUY.*LONG"):
        execution_engine.on_signal(
            signal=SignalType.BUY,
            candle=candle(30, close=101),
            series=series,
            symbol="TEST",
        )


class RecordingStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(name="Recording")
        self.feedback: list[ExecutionFeedback] = []

    def on_new_candle(self, series: CandleSeries) -> SignalType | None:
        return None

    def on_execution_feedback(self, feedback: ExecutionFeedback) -> None:
        self.feedback.append(feedback)

    def reset(self) -> None:
        self.feedback = []


class DefaultHookStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(name="DefaultHook")

    def on_new_candle(self, series: CandleSeries) -> SignalType | None:
        return None

    def reset(self) -> None:
        pass


def test_strategy_runner_delivers_multiple_feedback_events_in_order() -> None:
    strategy = RecordingStrategy()
    runner = StrategyRunner(strategy)
    events = (
        ExecutionFeedback(
            event_type=ExecutionFeedbackType.ENTRY_ACCEPTED,
            symbol="TEST",
            timestamp=datetime(2026, 1, 2, 9, 15),
            position_state=ExecutionPositionState.LONG,
            fill_price=100,
            quantity=10,
        ),
        ExecutionFeedback(
            event_type=ExecutionFeedbackType.PROTECTIVE_EXIT,
            symbol="TEST",
            timestamp=datetime(2026, 1, 2, 9, 15),
            position_state=ExecutionPositionState.FLAT,
            fill_price=98,
            quantity=10,
        ),
    )

    runner.deliver_execution_feedback(events)

    assert strategy.feedback == list(events)


def test_base_strategy_default_feedback_hook_is_compatible() -> None:
    runner = StrategyRunner(DefaultHookStrategy())
    runner.deliver_execution_feedback(
        (
            ExecutionFeedback(
                event_type=ExecutionFeedbackType.ENTRY_REJECTED,
                symbol="TEST",
                timestamp=datetime(2026, 1, 2, 9, 15),
                position_state=ExecutionPositionState.FLAT,
                rejection_reason=ExecutionRejectionReason.DRAWDOWN_LIMIT,
            ),
        )
    )


def test_sma_position_state_changes_from_feedback_not_signal_intent() -> None:
    strategy = SMACrossOverStrategy(params={"fast_period": 1, "slow_period": 2})
    series = CandleSeries([candle(0, close=100), candle(15, close=110)])

    assert strategy.on_new_candle(series) == SignalType.BUY
    assert strategy.position_open is False

    strategy.on_execution_feedback(
        ExecutionFeedback(
            event_type=ExecutionFeedbackType.ENTRY_ACCEPTED,
            symbol="TEST",
            timestamp=datetime(2026, 1, 2, 9, 30),
            position_state=ExecutionPositionState.LONG,
            fill_price=110,
            quantity=10,
        )
    )
    assert strategy.position_open is True

    series.append(candle(30, close=90))
    assert strategy.on_new_candle(series) == SignalType.SELL
    assert strategy.position_open is True

    strategy.on_execution_feedback(
        ExecutionFeedback(
            event_type=ExecutionFeedbackType.STRATEGY_EXIT,
            symbol="TEST",
            timestamp=datetime(2026, 1, 2, 9, 45),
            position_state=ExecutionPositionState.FLAT,
            fill_price=90,
            quantity=10,
        )
    )
    assert strategy.position_open is False


def test_sma_rejected_and_protective_feedback_leave_strategy_flat() -> None:
    strategy = SMACrossOverStrategy(params={"fast_period": 1, "slow_period": 2})

    strategy.on_execution_feedback(
        ExecutionFeedback(
            event_type=ExecutionFeedbackType.ENTRY_REJECTED,
            symbol="TEST",
            timestamp=datetime(2026, 1, 2, 9, 15),
            position_state=ExecutionPositionState.FLAT,
            rejection_reason=ExecutionRejectionReason.INVALID_QUANTITY,
        )
    )
    assert strategy.position_open is False

    strategy.position_open = True
    strategy.on_execution_feedback(
        ExecutionFeedback(
            event_type=ExecutionFeedbackType.PROTECTIVE_EXIT,
            symbol="TEST",
            timestamp=datetime(2026, 1, 2, 9, 30),
            position_state=ExecutionPositionState.FLAT,
            fill_price=98,
            quantity=10,
        )
    )
    assert strategy.position_open is False
