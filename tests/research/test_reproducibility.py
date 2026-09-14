from dataclasses import replace
from datetime import datetime, timedelta, timezone
import re

import pytest

from core.backtest.backtest_result import BacktestResult
from core.backtest.bar_record import BarRecord
from core.config.backtest_config import BacktestConfig
from core.config.execution_config import ExecutionConfig
from core.entities.candle import Candle
from core.entities.trade import Trade
from core.market_data.historical_coverage import TimeRange
from core.research.reproducibility import (
    BACKTEST_CONFIG_SCHEMA,
    BACKTEST_RESULT_SCHEMA,
    DATASET_SCHEMA,
    backtest_configuration_fingerprint,
    canonical_bytes,
    canonical_fingerprint,
    dataset_fingerprint,
    stable_backtest_result_fingerprint,
)
from core.runtime.dataset_context import DatasetContext


INDIA = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
START = datetime(2026, 1, 2, 9, 15, 0, 123456, tzinfo=INDIA)
CONTEXT = DatasetContext("RELIANCE", "15m", "Asia/Kolkata")
REQUEST = TimeRange(START, START + timedelta(minutes=45))
FINGERPRINT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def candles() -> list[Candle]:
    return [
        Candle(START, 100.0, 103.0, 99.0, 102.0, 1011.0),
        Candle(
            START + timedelta(minutes=15),
            102.0,
            106.0,
            101.0,
            105.0,
            1222.0,
        ),
        Candle(
            START + timedelta(minutes=30),
            105.0,
            108.0,
            104.0,
            107.0,
            1333.0,
        ),
    ]


def config(**changes) -> BacktestConfig:
    values = {
        "symbol": CONTEXT.symbol,
        "timeframe": CONTEXT.timeframe,
        "strategy_name": "deterministic",
        "start": REQUEST.start,
        "end": REQUEST.end,
        "initial_capital": 100_000.0,
        "enable_replay": False,
        "enable_visualization": False,
        "enable_exports": False,
        "strategy_params": {"slow": 20, "fast": 5},
        "timezone": CONTEXT.timezone,
    }
    values.update(changes)
    return BacktestConfig(**values)


def execution_config(**changes) -> ExecutionConfig:
    values = {
        "slippage_pct": 0.0007,
        "slippage_enabled": True,
        "brokerage_enabled": True,
    }
    values.update(changes)
    return ExecutionConfig(**values)


def result(
    *,
    session_id: str = "session-a",
    trade_pnl: float = 450.25,
    ending_cash: float = 100_450.25,
    snapshot=None,
) -> BacktestResult:
    trade = Trade(
        symbol="RELIANCE",
        entry_time=START,
        entry_price=100.25,
        exit_time=START + timedelta(minutes=30),
        exit_price=105.5,
        stop_price=98.0,
        quantity=100,
        direction="LONG",
        exit_reason="SIGNAL",
        pnl=trade_pnl,
        gross_pnl=525.0,
        transaction_cost=74.75,
        pnl_pct=0.0449,
    )
    records = [
        BarRecord(
            timestamp=START,
            open=100.0,
            high=103.0,
            low=99.0,
            close=102.0,
            volume=1011.0,
            strategy="deterministic",
            state="LONG",
            signal="BUY",
            execution_event="BUY",
            execution_price=100.25,
            execution_quantity=100,
            decision_snapshot=(
                {"fast": 101.5, "slow": 100.5}
                if snapshot is None
                else snapshot
            ),
            equity=100_175.0,
            cash=89_975.0,
            position_size=100.0,
            drawdown=0.0,
        ),
        BarRecord(
            timestamp=START + timedelta(minutes=30),
            open=105.0,
            high=108.0,
            low=104.0,
            close=107.0,
            volume=1333.0,
            strategy="deterministic",
            state="FLAT",
            signal="SELL",
            execution_event="SELL",
            execution_price=105.5,
            execution_quantity=100,
            decision_snapshot={"fast": 106.5, "slow": 104.0},
            equity=100_450.25,
            cash=ending_cash,
            position_size=0.0,
            drawdown=0.001,
        ),
    ]
    return BacktestResult([trade], records, session_id)


def test_canonical_bytes_and_fingerprint_are_repeatable_and_formatted():
    value = {"name": "Kanasu", "values": [None, True, 7, 1.5]}

    first = canonical_bytes(value, schema="kanasu.test.v1")
    second = canonical_bytes(value, schema="kanasu.test.v1")
    fingerprint = canonical_fingerprint(value, schema="kanasu.test.v1")

    assert first == second
    assert b'"0x1.8000000000000p+0"' in first
    assert FINGERPRINT_PATTERN.fullmatch(fingerprint)


def test_canonical_mapping_order_does_not_affect_identity():
    left = {"alpha": 1, "beta": {"x": 2, "y": 3}}
    right = {"beta": {"y": 3, "x": 2}, "alpha": 1}

    assert canonical_bytes(left, schema="kanasu.test.v1") == canonical_bytes(
        right,
        schema="kanasu.test.v1",
    )


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (1, 1.0),
        ([1, 2], (1, 2)),
        (None, "None"),
        (None, False),
        ("None", False),
    ],
)
def test_canonical_serialization_preserves_type_distinctions(left, right):
    assert canonical_bytes(left, schema="kanasu.test.v1") != canonical_bytes(
        right,
        schema="kanasu.test.v1",
    )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_canonical_serialization_rejects_non_finite_floats(value):
    with pytest.raises(ValueError, match="finite"):
        canonical_bytes(value, schema="kanasu.test.v1")


def test_canonical_serialization_rejects_unsupported_values_and_key_types():
    with pytest.raises(TypeError, match="unsupported canonical value"):
        canonical_bytes(object(), schema="kanasu.test.v1")
    with pytest.raises(TypeError, match="string keys"):
        canonical_bytes({1: "value"}, schema="kanasu.test.v1")


def test_datetime_serialization_preserves_microseconds_and_offset():
    encoded = canonical_bytes(START, schema="kanasu.test.v1")

    assert START.isoformat(timespec="microseconds").encode() in encoded
    assert b"+05:30" in encoded


def test_schema_domains_separate_otherwise_identical_payloads():
    value = {"value": 1}

    fingerprints = {
        canonical_fingerprint(value, schema=DATASET_SCHEMA),
        canonical_fingerprint(value, schema=BACKTEST_CONFIG_SCHEMA),
        canonical_fingerprint(value, schema=BACKTEST_RESULT_SCHEMA),
    }

    assert len(fingerprints) == 3


def test_equivalent_canonical_datasets_have_the_same_fingerprint():
    provider_fresh = candles()
    durable_local = [replace(candle) for candle in provider_fresh]

    assert dataset_fingerprint(CONTEXT, REQUEST, provider_fresh) == (
        dataset_fingerprint(CONTEXT, REQUEST, durable_local)
    )


@pytest.mark.parametrize(
    "changed",
    [
        lambda: (replace(CONTEXT, symbol="TCS"), REQUEST, candles()),
        lambda: (
            CONTEXT,
            TimeRange(REQUEST.start, REQUEST.end + timedelta(minutes=15)),
            candles(),
        ),
        lambda: (
            CONTEXT,
            REQUEST,
            [replace(candles()[0], close=101.0), *candles()[1:]],
        ),
    ],
)
def test_dataset_identity_changes_with_context_request_or_candle(changed):
    changed_context, changed_request, changed_candles = changed()

    assert dataset_fingerprint(CONTEXT, REQUEST, candles()) != (
        dataset_fingerprint(
            changed_context,
            changed_request,
            changed_candles,
        )
    )


@pytest.mark.parametrize(
    "invalid_candles",
    [
        lambda: [candles()[0], candles()[0]],
        lambda: [candles()[1], candles()[0]],
    ],
)
def test_dataset_fingerprint_rejects_noncanonical_candle_order(invalid_candles):
    with pytest.raises(ValueError, match="duplicate|chronological"):
        dataset_fingerprint(CONTEXT, REQUEST, invalid_candles())


def test_dataset_fingerprint_rejects_request_candle_awareness_mismatch():
    naive_request = TimeRange(
        REQUEST.start.replace(tzinfo=None),
        REQUEST.end.replace(tzinfo=None),
    )

    with pytest.raises(ValueError, match="timezone awareness"):
        dataset_fingerprint(CONTEXT, naive_request, candles())


def test_source_provenance_is_outside_dataset_identity():
    provider_backed = dataset_fingerprint(CONTEXT, REQUEST, candles())
    local_only = dataset_fingerprint(CONTEXT, REQUEST, candles())

    assert provider_backed == local_only


def configuration_identity(
    *,
    selected_config=None,
    selected_execution=None,
    risk=0.01,
) -> str:
    return backtest_configuration_fingerprint(
        CONTEXT,
        REQUEST,
        config() if selected_config is None else selected_config,
        execution_config() if selected_execution is None else selected_execution,
        effective_risk_per_trade_pct=risk,
    )


def test_strategy_parameter_mapping_order_does_not_affect_configuration():
    left = config(strategy_params={"fast": 5, "slow": 20})
    right = config(strategy_params={"slow": 20, "fast": 5})

    assert configuration_identity(selected_config=left) == (
        configuration_identity(selected_config=right)
    )


@pytest.mark.parametrize(
    "changed_fingerprint",
    [
        lambda: configuration_identity(
            selected_config=config(strategy_name="other")
        ),
        lambda: configuration_identity(
            selected_config=config(strategy_params={"fast": 8, "slow": 20})
        ),
        lambda: configuration_identity(
            selected_config=config(initial_capital=125_000.0)
        ),
        lambda: configuration_identity(risk=0.015),
        lambda: configuration_identity(
            selected_execution=execution_config(slippage_pct=0.001)
        ),
        lambda: configuration_identity(
            selected_execution=execution_config(slippage_enabled=False)
        ),
        lambda: configuration_identity(
            selected_execution=execution_config(brokerage_enabled=False)
        ),
    ],
)
def test_result_affecting_configuration_changes_identity(changed_fingerprint):
    assert configuration_identity() != changed_fingerprint()


def test_presentation_controls_do_not_affect_configuration_identity():
    presentation_changed = config(
        enable_replay=True,
        enable_visualization=True,
        enable_exports=True,
    )

    assert configuration_identity() == configuration_identity(
        selected_config=presentation_changed
    )


def test_session_id_is_excluded_from_stable_result_identity():
    assert stable_backtest_result_fingerprint(result(session_id="fresh")) == (
        stable_backtest_result_fingerprint(result(session_id="warm"))
    )


def test_trade_field_change_changes_stable_result_identity():
    assert stable_backtest_result_fingerprint(result()) != (
        stable_backtest_result_fingerprint(result(trade_pnl=451.25))
    )


def test_bar_account_state_change_changes_stable_result_identity():
    assert stable_backtest_result_fingerprint(result()) != (
        stable_backtest_result_fingerprint(result(ending_cash=100_451.25))
    )


def test_decision_snapshot_mapping_order_does_not_affect_result_identity():
    left = result(snapshot={"fast": 101.5, "slow": 100.5})
    right = result(snapshot={"slow": 100.5, "fast": 101.5})

    assert stable_backtest_result_fingerprint(left) == (
        stable_backtest_result_fingerprint(right)
    )


def test_unsupported_decision_snapshot_value_is_rejected():
    with pytest.raises(TypeError, match="unsupported canonical value"):
        stable_backtest_result_fingerprint(result(snapshot={"bad": object()}))
