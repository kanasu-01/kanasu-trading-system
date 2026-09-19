"""Deterministic v1 research identity contracts.

Canonicalization is deliberately strict: supported values are type tagged,
unsupported values fail, and timestamps retain their supplied representation.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
import hashlib
import json
import math
from typing import Any

from core.backtest.backtest_result import BacktestResult
from core.config.backtest_config import BacktestConfig
from core.config.execution_config import ExecutionConfig
from core.config.backtest_economic_policy import BacktestEconomicPolicy
from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.market_data.historical_coverage import TimeRange
from core.research.models.backtest_run_manifest import BacktestRunManifest
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.strategies.base_strategy import BaseStrategy


DATASET_SCHEMA = "kanasu.dataset.v1"
BACKTEST_CONFIG_SCHEMA = "kanasu.backtest-config.v1"
BACKTEST_CONFIG_V2_SCHEMA = "kanasu.backtest-config.v2"
BACKTEST_RUN_MANIFEST_SCHEMA = "kanasu.backtest-run-manifest.v1"
BACKTEST_RESULT_SCHEMA = "kanasu.backtest-result.v1"


def _canonical_value(value: Any) -> dict[str, Any]:
    if value is None:
        return {"type": "none"}

    if isinstance(value, bool):
        return {"type": "bool", "value": value}

    if isinstance(value, int):
        return {"type": "int", "value": str(value)}

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical float values must be finite")
        return {"type": "float", "value": value.hex()}

    if isinstance(value, str):
        return {"type": "str", "value": value}

    if isinstance(value, datetime):
        return {
            "type": "datetime",
            "value": value.isoformat(timespec="microseconds"),
        }

    if isinstance(value, list):
        return {
            "type": "list",
            "value": [_canonical_value(item) for item in value],
        }

    if isinstance(value, tuple):
        return {
            "type": "tuple",
            "value": [_canonical_value(item) for item in value],
        }

    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("canonical mappings require string keys")
        return {
            "type": "mapping",
            "value": [
                [key, _canonical_value(value[key])]
                for key in sorted(value)
            ],
        }

    raise TypeError(
        f"unsupported canonical value type: {type(value).__name__}"
    )


def canonical_bytes(value: Any, *, schema: str) -> bytes:
    """Return versioned, type-stable canonical UTF-8 JSON bytes."""

    if not isinstance(schema, str) or not schema:
        raise ValueError("canonical schema must be a non-empty string")

    tagged_payload = _canonical_value(
        {
            "schema": schema,
            "payload": value,
        }
    )
    return json.dumps(
        tagged_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_fingerprint(value: Any, *, schema: str) -> str:
    """Hash exact canonical bytes with a self-describing SHA-256 prefix."""

    digest = hashlib.sha256(canonical_bytes(value, schema=schema)).hexdigest()
    return f"sha256:{digest}"


def _context_payload(context: DatasetContext) -> dict[str, Any]:
    return {
        "symbol": context.symbol,
        "timeframe": context.timeframe,
        "timezone": context.timezone,
    }


def _range_payload(request: TimeRange) -> dict[str, datetime]:
    return {
        "start": request.start,
        "end": request.end,
    }


def _candle_payload(candle: Candle) -> dict[str, Any]:
    return {
        "timestamp": candle.timestamp,
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "volume": candle.volume,
    }


def dataset_fingerprint(
    context: DatasetContext,
    request: TimeRange,
    candles: Sequence[Candle],
) -> str:
    """Identify canonical ordered candles without sorting or timestamp repair."""

    candle_list = list(candles)
    if any(not isinstance(candle, Candle) for candle in candle_list):
        raise TypeError("dataset fingerprint requires Candle values")

    request_is_aware = request.start.utcoffset() is not None
    for candle in candle_list:
        if (candle.timestamp.utcoffset() is not None) != request_is_aware:
            raise ValueError(
                "request and candle timestamp timezone awareness must match"
            )

    # CandleSeries is the existing canonical sequence validation boundary.
    CandleSeries(candle_list)

    return canonical_fingerprint(
        {
            "dataset_context": _context_payload(context),
            "request": _range_payload(request),
            "candles": [_candle_payload(candle) for candle in candle_list],
        },
        schema=DATASET_SCHEMA,
    )


def backtest_configuration_fingerprint(
    context: DatasetContext,
    request: TimeRange,
    config: BacktestConfig,
    execution_config: ExecutionConfig,
    *,
    effective_risk_per_trade_pct: float,
) -> str:
    """Identify effective result-affecting Backtest configuration values."""

    return canonical_fingerprint(
        {
            "dataset_context": _context_payload(context),
            "request": _range_payload(request),
            "strategy_name": config.strategy_name,
            "strategy_params": config.strategy_params,
            "initial_capital": config.initial_capital,
            "effective_risk_per_trade_pct": effective_risk_per_trade_pct,
            "execution": {
                "slippage_pct": execution_config.slippage_pct,
                "slippage_enabled": execution_config.slippage_enabled,
                "brokerage_enabled": execution_config.brokerage_enabled,
            },
        },
        schema=BACKTEST_CONFIG_SCHEMA,
    )


def _execution_payload(execution_config: ExecutionConfig) -> dict[str, Any]:
    return {
        "slippage_pct": execution_config.slippage_pct,
        "slippage_enabled": execution_config.slippage_enabled,
        "brokerage_enabled": execution_config.brokerage_enabled,
    }


def _economic_policy_payload(
    policy: BacktestEconomicPolicy,
) -> dict[str, Any]:
    return policy.to_payload()


def build_backtest_run_manifest(
    context: DatasetContext,
    request: TimeRange,
    dataset_fingerprint_value: str,
    strategy: BaseStrategy,
    *,
    initial_capital: float,
    runtime_context: RuntimeContext,
) -> BacktestRunManifest:
    """Capture the effective inputs consumed by one canonical Backtest."""

    if not isinstance(strategy, BaseStrategy):
        raise TypeError("strategy must be a BaseStrategy")
    if not isinstance(runtime_context, RuntimeContext):
        raise TypeError("runtime_context must be a RuntimeContext")

    return BacktestRunManifest(
        dataset_context=context,
        requested_range=request,
        dataset_fingerprint=dataset_fingerprint_value,
        strategy_name=strategy.name,
        strategy_params=strategy.research_parameters(),
        initial_capital=initial_capital,
        effective_risk_per_trade_pct=runtime_context.risk_per_trade_pct,
        execution_config=runtime_context.execution_config,
        economic_policy=runtime_context.economic_policy,
    )


def backtest_run_manifest_payload(
    manifest: BacktestRunManifest,
) -> dict[str, Any]:
    """Return the complete versioned effective-input manifest payload."""

    if not isinstance(manifest, BacktestRunManifest):
        raise TypeError("manifest must be a BacktestRunManifest")

    return {
        "dataset_context": _context_payload(manifest.dataset_context),
        "request": _range_payload(manifest.requested_range),
        "dataset_fingerprint": manifest.dataset_fingerprint,
        "strategy_name": manifest.strategy_name,
        "strategy_params": manifest.strategy_params_payload(),
        "initial_capital": manifest.initial_capital,
        "effective_risk_per_trade_pct": manifest.effective_risk_per_trade_pct,
        "execution": _execution_payload(manifest.execution_config),
        "economic_policy": _economic_policy_payload(
            manifest.economic_policy
        ),
    }


def backtest_run_manifest_bytes(
    manifest: BacktestRunManifest,
) -> bytes:
    """Serialize the complete manifest with its independent schema."""

    return canonical_bytes(
        backtest_run_manifest_payload(manifest),
        schema=BACKTEST_RUN_MANIFEST_SCHEMA,
    )


def backtest_configuration_fingerprint_v2(
    manifest: BacktestRunManifest,
) -> str:
    """Identify all effective M4 Backtest result-affecting inputs."""

    payload = backtest_run_manifest_payload(manifest)
    payload.pop("dataset_fingerprint")

    return canonical_fingerprint(
        payload,
        schema=BACKTEST_CONFIG_V2_SCHEMA,
    )


def _trade_payload(trade) -> dict[str, Any]:
    return {
        "symbol": trade.symbol,
        "entry_time": trade.entry_time,
        "entry_price": trade.entry_price,
        "exit_time": trade.exit_time,
        "exit_price": trade.exit_price,
        "stop_price": trade.stop_price,
        "quantity": trade.quantity,
        "direction": trade.direction,
        "exit_reason": trade.exit_reason,
        "pnl": trade.pnl,
        "gross_pnl": trade.gross_pnl,
        "transaction_cost": trade.transaction_cost,
        "pnl_pct": trade.pnl_pct,
    }


def _bar_record_payload(record) -> dict[str, Any]:
    return {
        "timestamp": record.timestamp,
        "open": record.open,
        "high": record.high,
        "low": record.low,
        "close": record.close,
        "volume": record.volume,
        "strategy": record.strategy,
        "state": record.state,
        "signal": record.signal,
        "execution_event": record.execution_event,
        "execution_price": record.execution_price,
        "execution_quantity": record.execution_quantity,
        "decision_snapshot": record.decision_snapshot,
        "equity": record.equity,
        "cash": record.cash,
        "position_size": record.position_size,
        "drawdown": record.drawdown,
    }


def stable_backtest_result_fingerprint(result: BacktestResult) -> str:
    """Identify stable Backtest output while excluding execution session ID."""

    return canonical_fingerprint(
        {
            "trades": [_trade_payload(trade) for trade in result.trades],
            "bar_records": [
                _bar_record_payload(record) for record in result.bar_records
            ],
            "equity_curve": result.equity_curve,
        },
        schema=BACKTEST_RESULT_SCHEMA,
    )
