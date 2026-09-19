from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from core.backtest.backtest_engine import BacktestEngine
from core.backtest.performance_metrics import PerformanceMetrics
from core.config.backtest_economic_policy import (
    BACKTEST_ECONOMIC_POLICY,
    BACKTEST_ECONOMIC_POLICY_ID,
)
from core.config.execution_config import ExecutionConfig
from core.entities.candle import Candle
from core.execution.trade_execution_engine import TradeExecutionEngine
from core.market_data.historical_coverage import TimeRange
from core.research.reproducibility import (
    BACKTEST_CONFIG_V2_SCHEMA,
    BACKTEST_RUN_MANIFEST_SCHEMA,
    backtest_configuration_fingerprint_v2,
    backtest_run_manifest_bytes,
    build_backtest_run_manifest,
    dataset_fingerprint,
)
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.strategies.base_strategy import BaseStrategy
from core.strategies.signal import SignalType
from core.strategies.sma_crossover_strategy import SMACrossOverStrategy


INDIA = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
START = datetime(2026, 1, 5, 9, 15, tzinfo=INDIA)
CONTEXT = DatasetContext("TEST", "15m", "Asia/Kolkata")
REQUEST = TimeRange(START, START + timedelta(hours=1))


def reference_candles() -> list[Candle]:
    values = [
        (0, 100.0, 101.0, 99.0, 100.0, 1000.0),
        (15, 100.0, 106.0, 95.0, 105.0, 1100.0),
        (30, 105.0, 111.0, 104.0, 110.0, 1200.0),
        (45, 110.0, 112.0, 109.0, 111.0, 1300.0),
    ]
    return [
        Candle(
            timestamp=START + timedelta(minutes=minutes),
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
        )
        for minutes, open_price, high, low, close, volume in values
    ]


class ReferenceStrategy(BaseStrategy):
    def __init__(self, params=None):
        super().__init__(
            name="M4.6Reference",
            params=params or {"scenario": "four-bar-reference"},
        )
        self.rejection_midpoint = None

    def on_new_candle(self, series):
        if len(series) == 1:
            self.rejection_midpoint = 90.2
            return SignalType.BUY
        if len(series) == 3:
            return SignalType.SELL
        return None

    def reset(self) -> None:
        self.rejection_midpoint = None


class NoopStrategy(BaseStrategy):
    def __init__(self, params=None):
        super().__init__(name="Noop", params=params)

    def on_new_candle(self, series):
        return None

    def reset(self) -> None:
        pass


def run_reference(execution_config: ExecutionConfig):
    strategy = ReferenceStrategy()
    runtime_context = RuntimeContext(
        execution_config=execution_config,
        risk_per_trade_pct=1.0,
    )
    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=100_000.0,
        runtime_context=runtime_context,
        dataset_context=CONTEXT,
    )
    result = engine.run(reference_candles())
    return strategy, runtime_context, engine, result


def build_manifest(
    *,
    strategy=None,
    runtime_context=None,
    dataset_identity=None,
):
    selected_strategy = strategy or ReferenceStrategy()
    selected_runtime = runtime_context or RuntimeContext(
        execution_config=ExecutionConfig(
            slippage_pct=0.0,
            slippage_enabled=False,
            brokerage_enabled=False,
        ),
        risk_per_trade_pct=1.0,
    )
    identity = dataset_identity or dataset_fingerprint(
        CONTEXT,
        REQUEST,
        reference_candles(),
    )
    return build_backtest_run_manifest(
        CONTEXT,
        REQUEST,
        identity,
        selected_strategy,
        initial_capital=100_000.0,
        runtime_context=selected_runtime,
    )


def test_versioned_manifest_and_v2_identity_are_deterministic():
    manifest = build_manifest()

    assert BACKTEST_CONFIG_V2_SCHEMA == "kanasu.backtest-config.v2"
    assert BACKTEST_RUN_MANIFEST_SCHEMA == "kanasu.backtest-run-manifest.v1"
    assert BACKTEST_ECONOMIC_POLICY_ID == "kanasu.backtest-economics.v1"
    assert backtest_run_manifest_bytes(manifest) == (
        backtest_run_manifest_bytes(manifest)
    )
    assert backtest_configuration_fingerprint_v2(manifest) == (
        backtest_configuration_fingerprint_v2(manifest)
    )


def test_dataset_content_identity_is_linked_but_independent_of_config_v2():
    manifest = build_manifest()
    changed_dataset = replace(
        manifest,
        dataset_fingerprint="sha256:" + "0" * 64,
    )

    assert backtest_run_manifest_bytes(manifest) != (
        backtest_run_manifest_bytes(changed_dataset)
    )
    assert backtest_configuration_fingerprint_v2(manifest) == (
        backtest_configuration_fingerprint_v2(changed_dataset)
    )


def test_strategy_parameter_mapping_order_does_not_change_v2_identity():
    left = build_manifest(
        strategy=NoopStrategy(params={"fast": 5, "slow": 20})
    )
    right = build_manifest(
        strategy=NoopStrategy(params={"slow": 20, "fast": 5})
    )

    assert backtest_configuration_fingerprint_v2(left) == (
        backtest_configuration_fingerprint_v2(right)
    )


def test_resolved_sma_defaults_are_manifested_as_effective_parameters():
    manifest = build_manifest(strategy=SMACrossOverStrategy())

    assert dict(manifest.strategy_params) == {
        "fast_period": 20,
        "slow_period": 50,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("policy_id", "kanasu.backtest-economics.test"),
        ("max_position_pct", 25.0),
        ("max_daily_loss_pct", 4.0),
        ("max_weekly_loss_pct", 7.0),
        ("max_total_risk_pct", 6.0),
        ("max_open_trades", 6),
        ("stop_buffer_pct", 0.25),
        ("stop_min_tick", 0.1),
        ("fallback_long_stop_multiplier", 0.97),
        ("brokerage_rate", 0.0004),
        ("brokerage_cap", 25.0),
        ("tax_rate", 0.0006),
        ("cost_rounding_digits", 3),
    ],
)
def test_each_policy_field_changes_v2_identity(field, value):
    manifest = build_manifest()
    changed_policy = replace(
        manifest.economic_policy,
        **{field: value},
    )
    changed = replace(manifest, economic_policy=changed_policy)

    assert backtest_configuration_fingerprint_v2(manifest) != (
        backtest_configuration_fingerprint_v2(changed)
    )


@pytest.mark.parametrize(
    "execution_config",
    [
        ExecutionConfig(
            slippage_pct=0.001,
            slippage_enabled=False,
            brokerage_enabled=False,
        ),
        ExecutionConfig(
            slippage_pct=0.0,
            slippage_enabled=True,
            brokerage_enabled=False,
        ),
        ExecutionConfig(
            slippage_pct=0.0,
            slippage_enabled=False,
            brokerage_enabled=True,
        ),
    ],
)
def test_each_effective_execution_setting_changes_v2_identity(execution_config):
    baseline = build_manifest()
    changed = build_manifest(
        runtime_context=RuntimeContext(
            execution_config=execution_config,
            risk_per_trade_pct=1.0,
        )
    )

    assert backtest_configuration_fingerprint_v2(baseline) != (
        backtest_configuration_fingerprint_v2(changed)
    )


def test_effective_risk_and_initial_capital_change_v2_identity():
    baseline = build_manifest()
    changed_risk = build_manifest(
        runtime_context=RuntimeContext(
            execution_config=baseline.execution_config,
            risk_per_trade_pct=2.0,
        )
    )
    changed_capital = replace(baseline, initial_capital=125_000.0)

    assert backtest_configuration_fingerprint_v2(baseline) != (
        backtest_configuration_fingerprint_v2(changed_risk)
    )
    assert backtest_configuration_fingerprint_v2(baseline) != (
        backtest_configuration_fingerprint_v2(changed_capital)
    )


def test_shared_policy_constructs_execution_components_from_same_values():
    policy = replace(
        BACKTEST_ECONOMIC_POLICY,
        max_position_pct=25.0,
        max_daily_loss_pct=4.0,
        max_weekly_loss_pct=7.0,
        max_total_risk_pct=6.0,
        max_open_trades=6,
        stop_buffer_pct=0.25,
        stop_min_tick=0.1,
        brokerage_rate=0.0004,
        brokerage_cap=25.0,
        tax_rate=0.0006,
        cost_rounding_digits=3,
    )
    engine = TradeExecutionEngine(
        strategy=NoopStrategy(),
        account_capital=100_000.0,
        session_id="m4.6-policy",
        runtime_context=RuntimeContext(economic_policy=policy),
        economic_policy=policy,
    )

    assert engine.risk_manager.max_position_pct == 25.0
    assert engine.drawdown_manager.max_daily_loss_pct == 4.0
    assert engine.drawdown_manager.max_weekly_loss_pct == 7.0
    assert engine.portfolio_risk_manager.max_total_risk_pct == 6.0
    assert engine.portfolio_risk_manager.max_open_trades == 6
    assert engine.stop_manager.buffer_pct == 0.25
    assert engine.stop_manager.min_tick == 0.1
    assert engine.brokerage_model.brokerage_rate == 0.0004
    assert engine.brokerage_model.brokerage_cap == 25.0
    assert engine.brokerage_model.tax_rate == 0.0006
    assert engine.brokerage_model.rounding_digits == 3


def test_primary_zero_friction_reference_matches_hand_calculation():
    _, _, _, result = run_reference(
        ExecutionConfig(
            slippage_pct=0.0,
            slippage_enabled=False,
            brokerage_enabled=False,
        )
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_price == 100.0
    assert trade.exit_price == 110.0
    assert trade.stop_price == 90.0
    assert trade.quantity == 100
    assert trade.gross_pnl == 1_000.0
    assert trade.transaction_cost == 0.0
    assert trade.pnl == 1_000.0
    assert trade.pnl_pct == pytest.approx(10.0)

    assert [record.cash for record in result.bar_records] == pytest.approx(
        [100_000.0, 90_000.0, 90_000.0, 101_000.0]
    )
    assert [record.equity for record in result.bar_records] == pytest.approx(
        [100_000.0, 100_500.0, 101_000.0, 101_000.0]
    )
    assert [record.position_size for record in result.bar_records] == [
        0,
        100,
        100,
        0,
    ]

    summary = PerformanceMetrics.summarize_backtest(result)
    assert summary["gross_realized_pnl"] == 1_000.0
    assert summary["net_realized_pnl"] == 1_000.0
    assert summary["account_pnl"] == 1_000.0
    assert summary["account_return_pct"] == pytest.approx(1.0)
    assert summary["max_equity_drawdown_pct"] == 0.0


def test_enabled_slippage_and_brokerage_reference_matches_hand_calculation():
    _, _, _, result = run_reference(
        ExecutionConfig(
            slippage_pct=0.001,
            slippage_enabled=True,
            brokerage_enabled=True,
        )
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_price == pytest.approx(100.1)
    assert trade.exit_price == pytest.approx(109.89)
    assert trade.stop_price == 90.0
    assert trade.quantity == 99
    assert trade.gross_pnl == pytest.approx(969.21)
    assert trade.transaction_cost == pytest.approx(16.63)
    assert trade.pnl == pytest.approx(952.58)

    assert [record.cash for record in result.bar_records] == pytest.approx(
        [100_000.0, 90_082.17, 90_082.17, 100_952.58]
    )
    assert [record.equity for record in result.bar_records] == pytest.approx(
        [100_000.0, 100_477.17, 100_972.17, 100_952.58]
    )

    summary = PerformanceMetrics.summarize_backtest(result)
    assert summary["gross_realized_pnl"] == pytest.approx(969.21)
    assert summary["net_realized_pnl"] == pytest.approx(952.58)
    assert summary["completed_trade_transaction_cost_total"] == pytest.approx(
        16.63
    )
    assert summary["account_pnl"] == pytest.approx(952.58)
    assert summary["account_return_pct"] == pytest.approx(0.95258)
    assert summary["max_equity_drawdown_pct"] == pytest.approx(
        0.019401385550094158
    )

def test_manifest_strategy_parameters_are_deeply_immutable():
    source = {
        "nested": {
            "levels": [1, 2],
            "pair": (3, 4),
        }
    }
    manifest = build_manifest(
        strategy=NoopStrategy(params=source)
    )

    source["nested"]["levels"].append(99)

    assert list(
        manifest.strategy_params["nested"]["levels"]
    ) == [1, 2]

    assert (
        manifest.strategy_params["nested"]["pair"]
        == (3, 4)
    )

    with pytest.raises(TypeError, match="immutable"):
        manifest.strategy_params["nested"]["levels"].append(5)

    with pytest.raises(TypeError):
        manifest.strategy_params["nested"]["extra"] = 6


def test_shared_execution_path_does_not_implicitly_consume_backtest_policy():
    custom_policy = replace(
        BACKTEST_ECONOMIC_POLICY,
        max_position_pct=25.0,
        max_daily_loss_pct=4.0,
        brokerage_rate=0.0004,
    )

    engine = TradeExecutionEngine(
        strategy=NoopStrategy(),
        account_capital=100_000.0,
        session_id="non-backtest-policy-isolation",
        runtime_context=RuntimeContext(
            economic_policy=custom_policy
        ),
    )

    assert engine.economic_policy is None
    assert engine.risk_manager.max_position_pct == 20.0
    assert engine.drawdown_manager.max_daily_loss_pct == 3.0
    assert engine.brokerage_model.brokerage_rate == pytest.approx(
        0.0003
    )


def test_backtest_engine_explicitly_binds_runtime_economic_policy():
    custom_policy = replace(
        BACKTEST_ECONOMIC_POLICY,
        max_position_pct=25.0,
    )

    runtime_context = RuntimeContext(
        execution_config=ExecutionConfig(
            slippage_enabled=False,
            brokerage_enabled=False,
        ),
        economic_policy=custom_policy,
    )

    engine = BacktestEngine(
        strategy=NoopStrategy(),
        initial_capital=100_000.0,
        runtime_context=runtime_context,
        dataset_context=CONTEXT,
    )

    assert (
        engine.execution_engine.economic_policy
        is custom_policy
    )
    assert (
        engine.execution_engine.risk_manager.max_position_pct
        == 25.0
    )
