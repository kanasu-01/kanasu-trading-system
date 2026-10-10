"""Deterministic v1 research identity contracts.

Canonicalization is deliberately strict: supported values are type tagged,
unsupported values fail, and timestamps retain their supplied representation.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any

from core.backtest.backtest_result import BacktestResult
from core.config.backtest_config import BacktestConfig
from core.config.execution_config import ExecutionConfig
from core.config.backtest_economic_policy import BacktestEconomicPolicy
from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.market_data.historical_coverage import TimeRange
from core.research.models.backtest_run_manifest import BacktestRunManifest
from core.research.models.research_catalog import (
    ComputationKind,
    EXPERIMENT_SPEC_SCHEMA_ID,
)
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.strategies.base_strategy import BaseStrategy
from math import isfinite


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


def _decode_canonical_value(value: Any) -> Any:
    if not isinstance(value, dict):
        raise ValueError(
            "canonical tagged value must be an object"
        )

    type_name = value.get("type")

    if type_name == "none":
        if set(value) != {"type"}:
            raise ValueError(
                "canonical none value must contain only "
                "the 'type' field"
            )
        return None

    if set(value) != {"type", "value"}:
        raise ValueError(
            "canonical tagged value must contain exactly "
            "'type' and 'value'"
        )

    payload = value["value"]

    if type_name == "bool":
        if type(payload) is not bool:
            raise ValueError(
                "canonical bool value must contain a bool"
            )
        return payload

    if type_name == "int":
        if not isinstance(payload, str):
            raise ValueError(
                "canonical int value must contain a string"
            )
        try:
            return int(payload)
        except ValueError as error:
            raise ValueError(
                "canonical int payload is invalid"
            ) from error

    if type_name == "float":
        if not isinstance(payload, str):
            raise ValueError(
                "canonical float value must contain a string"
            )
        try:
            decoded = float.fromhex(payload)
        except ValueError as error:
            raise ValueError(
                "canonical float payload is invalid"
            ) from error
        if not math.isfinite(decoded):
            raise ValueError(
                "canonical float values must be finite"
            )
        return decoded

    if type_name == "str":
        if not isinstance(payload, str):
            raise ValueError(
                "canonical str value must contain a string"
            )
        return payload

    if type_name == "datetime":
        if not isinstance(payload, str):
            raise ValueError(
                "canonical datetime value must contain a string"
            )
        try:
            return datetime.fromisoformat(payload)
        except ValueError as error:
            raise ValueError(
                "canonical datetime payload is invalid"
            ) from error

    if type_name in {"list", "tuple"}:
        if not isinstance(payload, list):
            raise ValueError(
                "canonical sequence value must contain a list"
            )
        decoded = [
            _decode_canonical_value(item)
            for item in payload
        ]
        return (
            tuple(decoded)
            if type_name == "tuple"
            else decoded
        )

    if type_name == "mapping":
        if not isinstance(payload, list):
            raise ValueError(
                "canonical mapping value must contain a list"
            )

        decoded = {}
        previous_key = None

        for item in payload:
            if (
                not isinstance(item, list)
                or len(item) != 2
                or not isinstance(item[0], str)
            ):
                raise ValueError(
                    "canonical mapping entries must be "
                    "[string, tagged-value] pairs"
                )

            key, tagged_value = item

            if key in decoded:
                raise ValueError(
                    "canonical mapping keys must be unique"
                )

            if (
                previous_key is not None
                and key <= previous_key
            ):
                raise ValueError(
                    "canonical mapping keys must be "
                    "strictly sorted"
                )

            decoded[key] = _decode_canonical_value(
                tagged_value
            )
            previous_key = key

        return decoded

    raise ValueError(
        f"unsupported canonical tagged type: {type_name!r}"
    )


def decode_canonical_bytes(
    payload: bytes,
    *,
    schema: str,
) -> Any:
    """
    Strictly decode bytes produced by canonical_bytes().

    Decoding is accepted only when schema identity matches and the
    decoded value re-encodes to the exact original byte sequence.
    """

    if type(payload) is not bytes:
        raise TypeError(
            "canonical payload must be exact bytes"
        )

    if not isinstance(schema, str) or not schema:
        raise ValueError(
            "canonical schema must be a non-empty string"
        )

    try:
        tagged = json.loads(
            payload.decode("utf-8")
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise ValueError(
            "canonical payload is not valid UTF-8 JSON"
        ) from error

    decoded = _decode_canonical_value(tagged)

    if (
        not isinstance(decoded, dict)
        or set(decoded)
        != {"schema", "payload"}
    ):
        raise ValueError(
            "canonical document must contain exactly "
            "'schema' and 'payload'"
        )

    if decoded["schema"] != schema:
        raise ValueError(
            "canonical document schema does not match "
            "the required schema"
        )

    value = decoded["payload"]

    if canonical_bytes(
        value,
        schema=schema,
    ) != payload:
        raise ValueError(
            "canonical payload is not in the exact "
            "accepted canonical representation"
        )

    return value


def canonical_fingerprint(value: Any, *, schema: str) -> str:
    """Hash exact canonical bytes with a self-describing SHA-256 prefix."""

    digest = hashlib.sha256(canonical_bytes(value, schema=schema)).hexdigest()
    return f"sha256:{digest}"


_SHA256_FINGERPRINT_PATTERN = re.compile(
    r"^sha256:[0-9a-f]{64}$"
)


def experiment_spec_fingerprint(
    *,
    computation_kind: ComputationKind,
    manifest_artifact_id: str,
    dataset_fingerprint: str,
    configuration_fingerprint: str,
    repository_revision: str,
) -> str:
    """Identify one exact deterministic research computation definition."""

    if not isinstance(computation_kind, ComputationKind):
        raise TypeError(
            "computation_kind must be a ComputationKind"
        )

    for field_name, value in (
        ("manifest_artifact_id", manifest_artifact_id),
        ("dataset_fingerprint", dataset_fingerprint),
        ("configuration_fingerprint", configuration_fingerprint),
    ):
        if (
            not isinstance(value, str)
            or not _SHA256_FINGERPRINT_PATTERN.fullmatch(value)
        ):
            raise ValueError(
                f"{field_name} must use "
                "sha256:<64 lowercase hexadecimal>"
            )

    if (
        not isinstance(repository_revision, str)
        or not repository_revision
    ):
        raise ValueError(
            "repository_revision must be a non-empty string"
        )

    return canonical_fingerprint(
        {
            "computation_kind": computation_kind.value,
            "manifest_artifact_id": manifest_artifact_id,
            "dataset_fingerprint": dataset_fingerprint,
            "configuration_fingerprint": configuration_fingerprint,
            "repository_revision": repository_revision,
        },
        schema=EXPERIMENT_SPEC_SCHEMA_ID,
    )


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


def stable_backtest_result_payload(
    result: BacktestResult,
) -> dict[str, Any]:
    """Return the stable authoritative Backtest financial-result payload."""

    if not isinstance(result, BacktestResult):
        raise TypeError("result must be a BacktestResult")

    return {
        "trades": [
            _trade_payload(trade)
            for trade in result.trades
        ],
        "bar_records": [
            _bar_record_payload(record)
            for record in result.bar_records
        ],
        "equity_curve": result.equity_curve,
    }


def _stable_backtest_result_value(value: Any) -> Any:
    """Normalize runtime enum values without relaxing canonical_bytes."""

    if isinstance(value, Enum):
        return _stable_backtest_result_value(value.value)

    if isinstance(value, list):
        return [
            _stable_backtest_result_value(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return tuple(
            _stable_backtest_result_value(item)
            for item in value
        )

    if isinstance(value, Mapping):
        return {
            key: _stable_backtest_result_value(item)
            for key, item in value.items()
        }

    return value


def stable_backtest_result_bytes(
    result: BacktestResult,
) -> bytes:
    """Serialize the stable Backtest result with its canonical schema."""

    return canonical_bytes(
        _stable_backtest_result_value(
            stable_backtest_result_payload(result)
        ),
        schema=BACKTEST_RESULT_SCHEMA,
    )



_BACKTEST_RESULT_FIELDS = frozenset(
    {
        "trades",
        "bar_records",
        "equity_curve",
    }
)

_BACKTEST_TRADE_FIELDS = frozenset(
    {
        "symbol",
        "entry_time",
        "entry_price",
        "exit_time",
        "exit_price",
        "stop_price",
        "quantity",
        "direction",
        "exit_reason",
        "pnl",
        "gross_pnl",
        "transaction_cost",
        "pnl_pct",
    }
)

_BACKTEST_BAR_RECORD_FIELDS = frozenset(
    {
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "strategy",
        "state",
        "signal",
        "execution_event",
        "execution_price",
        "execution_quantity",
        "decision_snapshot",
        "equity",
        "cash",
        "position_size",
        "drawdown",
    }
)


def _require_result_mapping(
    value: Any,
    *,
    expected_fields: frozenset[str],
    label: str,
) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != expected_fields
    ):
        raise ValueError(
            f"{label} has an invalid canonical field set"
        )

    return value


def _require_result_string(
    value: Any,
    *,
    label: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(
            f"{label} must be a string"
        )

    return value


def _require_result_optional_string(
    value: Any,
    *,
    label: str,
) -> str | None:
    if value is None:
        return None

    return _require_result_string(
        value,
        label=label,
    )


def _require_result_datetime(
    value: Any,
    *,
    label: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(
            f"{label} must be a canonical datetime"
        )

    return value


def _require_result_finite_number(
    value: Any,
    *,
    label: str,
) -> int | float:
    if (
        isinstance(value, bool)
        or not isinstance(
            value,
            (int, float),
        )
        or not isfinite(value)
    ):
        raise ValueError(
            f"{label} must be a finite numeric value"
        )

    return value


def _require_result_integer(
    value: Any,
    *,
    label: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
    ):
        raise ValueError(
            f"{label} must be an integer"
        )

    return value


def validate_stable_backtest_result_payload(
    payload: Any,
) -> dict[str, Any]:
    """
    Validate the exact stable Backtest-result contract emitted by
    stable_backtest_result_payload.

    This is structural/semantic validation only. It does not recompute
    signals, fills, costs, positions, P&L or any Backtest economics.
    """

    result = _require_result_mapping(
        payload,
        expected_fields=_BACKTEST_RESULT_FIELDS,
        label="Backtest result payload",
    )

    trades = result["trades"]
    bar_records = result["bar_records"]
    equity_curve = result["equity_curve"]

    if not isinstance(trades, list):
        raise ValueError(
            "Backtest trades must be a list"
        )

    if not isinstance(bar_records, list):
        raise ValueError(
            "Backtest bar_records must be a list"
        )

    if not isinstance(equity_curve, list):
        raise ValueError(
            "Backtest equity_curve must be a list"
        )

    for index, raw_trade in enumerate(trades):
        trade = _require_result_mapping(
            raw_trade,
            expected_fields=_BACKTEST_TRADE_FIELDS,
            label=f"Backtest trade {index}",
        )

        _require_result_string(
            trade["symbol"],
            label=f"Backtest trade {index} symbol",
        )

        entry_time = _require_result_datetime(
            trade["entry_time"],
            label=f"Backtest trade {index} entry_time",
        )

        entry_price = _require_result_finite_number(
            trade["entry_price"],
            label=f"Backtest trade {index} entry_price",
        )

        if entry_price <= 0:
            raise ValueError(
                f"Backtest trade {index} entry_price "
                "must be positive"
            )

        exit_time = trade["exit_time"]

        if exit_time is not None:
            exit_time = _require_result_datetime(
                exit_time,
                label=f"Backtest trade {index} exit_time",
            )

            if exit_time < entry_time:
                raise ValueError(
                    f"Backtest trade {index} exit_time "
                    "cannot precede entry_time"
                )

        for field in (
            "exit_price",
            "stop_price",
            "pnl",
            "gross_pnl",
            "transaction_cost",
            "pnl_pct",
        ):
            _require_result_finite_number(
                trade[field],
                label=(
                    f"Backtest trade {index} {field}"
                ),
            )

        if (
            exit_time is not None
            and trade["exit_price"] <= 0
        ):
            raise ValueError(
                f"Backtest trade {index} exit_price "
                "must be positive for a closed trade"
            )

        if trade["stop_price"] < 0:
            raise ValueError(
                f"Backtest trade {index} stop_price "
                "cannot be negative"
            )

        _require_result_integer(
            trade["quantity"],
            label=f"Backtest trade {index} quantity",
        )

        if trade["quantity"] <= 0:
            raise ValueError(
                f"Backtest trade {index} quantity "
                "must be positive"
            )

        for field in (
            "direction",
            "exit_reason",
        ):
            _require_result_string(
                trade[field],
                label=(
                    f"Backtest trade {index} {field}"
                ),
            )

        if trade["direction"] != "LONG":
            raise ValueError(
                f"Backtest trade {index} direction "
                "must be LONG for long-only research"
            )

    bar_timestamps = []
    bar_equities = []

    previous_timestamp = None

    for index, raw_record in enumerate(
        bar_records
    ):
        record = _require_result_mapping(
            raw_record,
            expected_fields=_BACKTEST_BAR_RECORD_FIELDS,
            label=f"Backtest bar record {index}",
        )

        timestamp = _require_result_datetime(
            record["timestamp"],
            label=(
                f"Backtest bar record {index} timestamp"
            ),
        )

        if (
            previous_timestamp is not None
            and timestamp <= previous_timestamp
        ):
            raise ValueError(
                "Backtest bar timestamps must be "
                "strictly chronological"
            )

        previous_timestamp = timestamp
        bar_timestamps.append(timestamp)

        for field in (
            "open",
            "high",
            "low",
            "close",
            "volume",
            "equity",
            "cash",
            "position_size",
            "drawdown",
        ):
            _require_result_finite_number(
                record[field],
                label=(
                    f"Backtest bar record {index} "
                    f"{field}"
                ),
            )

        for field in (
            "open",
            "high",
            "low",
            "close",
        ):
            if record[field] <= 0:
                raise ValueError(
                    f"Backtest bar record {index} "
                    f"{field} must be positive"
                )

        if record["low"] > record["high"]:
            raise ValueError(
                f"Backtest bar record {index} "
                "low cannot exceed high"
            )

        if not (
            record["low"]
            <= record["open"]
            <= record["high"]
        ):
            raise ValueError(
                f"Backtest bar record {index} "
                "open must lie within the OHLC envelope"
            )

        if not (
            record["low"]
            <= record["close"]
            <= record["high"]
        ):
            raise ValueError(
                f"Backtest bar record {index} "
                "close must lie within the OHLC envelope"
            )

        if record["volume"] < 0:
            raise ValueError(
                f"Backtest bar record {index} "
                "volume cannot be negative"
            )

        if record["position_size"] < 0:
            raise ValueError(
                f"Backtest bar record {index} "
                "position_size cannot be negative "
                "for long-only research"
            )

        if record["drawdown"] > 0:
            raise ValueError(
                f"Backtest bar record {index} "
                "drawdown cannot be positive"
            )

        if (
            record["position_size"] == 0
            and record["equity"] != record["cash"]
        ):
            raise ValueError(
                f"Backtest bar record {index} "
                "zero position requires equity to equal cash"
            )

        if (
            record["position_size"] > 0
            and record["equity"] <= record["cash"]
        ):
            raise ValueError(
                f"Backtest bar record {index} "
                "positive position requires equity to exceed cash"
            )

        _require_result_string(
            record["strategy"],
            label=(
                f"Backtest bar record {index} strategy"
            ),
        )

        for field in (
            "state",
            "signal",
            "execution_event",
        ):
            _require_result_optional_string(
                record[field],
                label=(
                    f"Backtest bar record {index} "
                    f"{field}"
                ),
            )

        if record["execution_price"] is not None:
            execution_price = _require_result_finite_number(
                record["execution_price"],
                label=(
                    f"Backtest bar record {index} "
                    "execution_price"
                ),
            )

            if execution_price <= 0:
                raise ValueError(
                    f"Backtest bar record {index} "
                    "execution_price must be positive"
                )

        if (
            record["execution_quantity"]
            is not None
        ):
            _require_result_integer(
                record["execution_quantity"],
                label=(
                    f"Backtest bar record {index} "
                    "execution_quantity"
                ),
            )

            if record["execution_quantity"] <= 0:
                raise ValueError(
                    f"Backtest bar record {index} "
                    "execution_quantity must be positive"
                )

        if not isinstance(
            record["decision_snapshot"],
            dict,
        ):
            raise ValueError(
                f"Backtest bar record {index} "
                "decision_snapshot must be a mapping"
            )

        bar_equities.append(
            record["equity"]
        )

    if len(equity_curve) != len(
        bar_records
    ):
        raise ValueError(
            "Backtest equity_curve must correspond "
            "one-for-one with bar_records"
        )

    for index, point in enumerate(
        equity_curve
    ):
        if (
            not isinstance(point, tuple)
            or len(point) != 2
        ):
            raise ValueError(
                f"Backtest equity curve point {index} "
                "must be a canonical two-item tuple"
            )

        timestamp = _require_result_datetime(
            point[0],
            label=(
                f"Backtest equity curve point {index} "
                "timestamp"
            ),
        )

        equity = _require_result_finite_number(
            point[1],
            label=(
                f"Backtest equity curve point {index} "
                "equity"
            ),
        )

        if (
            timestamp != bar_timestamps[index]
            or equity != bar_equities[index]
        ):
            raise ValueError(
                "Backtest equity_curve does not match "
                "authoritative bar_records"
            )

    if not bar_records:
        if trades:
            raise ValueError(
                "Backtest trades require authoritative "
                "bar_records"
            )

        if equity_curve:
            raise ValueError(
                "Backtest equity_curve requires "
                "authoritative bar_records"
            )

    return result


def decode_stable_backtest_result_bytes(
    payload: bytes,
) -> dict[str, Any]:
    """
    Decode and strictly validate one canonical Backtest-result artifact.
    """

    decoded = decode_canonical_bytes(
        payload,
        schema=BACKTEST_RESULT_SCHEMA,
    )

    return validate_stable_backtest_result_payload(
        decoded
    )


def stable_backtest_result_fingerprint(
    result: BacktestResult,
) -> str:
    """Identify the exact canonical stable Backtest result bytes."""

    digest = hashlib.sha256(
        stable_backtest_result_bytes(result)
    ).hexdigest()

    return f"sha256:{digest}"
