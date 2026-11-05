"""Minimal candidate-bound M9.6 WFA evidence and qualification records."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isclose, isfinite
from numbers import Real
from types import SimpleNamespace
import re

from core.backtest.performance_metrics import PerformanceMetrics
from core.market_data.historical_coverage import TimeRange
from core.research.reproducibility import (
    canonical_bytes,
    canonical_fingerprint,
    decode_canonical_bytes,
)
from core.walk_forward.equity_stitcher import EquityStitcher
from core.walk_forward.metrics import WalkForwardMetrics
from core.walk_forward.optimizer import GridSearchOptimizer
from core.walk_forward.result import WalkForwardResult


_SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
CANDIDATE_WFA_RESULT_SCHEMA_ID = "kanasu.candidate-wfa-result.v1"
CANDIDATE_WFA_CONFIG_SCHEMA_ID = "kanasu.candidate-wfa-config.v1"
CANDIDATE_WFA_DECISION_SCHEMA_ID = "kanasu.candidate-wfa-decision.v1"
CANDIDATE_WFA_EVALUATOR_VERSION = "m9.6-v1"


class WfaEvidenceValidity(str, Enum):
    VALID = "VALID"
    INSUFFICIENT = "INSUFFICIENT"
    INVALID = "INVALID"


class WfaQualificationOutcome(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    REJECTED = "REJECTED"
    INSUFFICIENT = "INSUFFICIENT"
    INVALID = "INVALID"


def _require_nonempty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_fingerprint(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise ValueError(
            f"{field_name} must use sha256:<64 lowercase hexadecimal>"
        )


def _require_finite_tree(value, field_name: str) -> None:
    if type(value) is float and not isfinite(value):
        raise ValueError(f"{field_name} contains a non-finite float")
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{field_name} mapping keys must be strings")
            _require_finite_tree(item, f"{field_name}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _require_finite_tree(item, f"{field_name}[{index}]")


def _require_finite_number(value, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field_name} must be a finite number")
    numeric = float(value)
    if not isfinite(numeric):
        raise ValueError(f"{field_name} must be a finite number")
    return numeric


def _require_strictly_increasing_equity_curve(
    value,
    *,
    field_name: str,
) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field_name} must be a non-empty list")

    previous_timestamp = None
    for index, point in enumerate(value):
        if (
            not isinstance(point, tuple)
            or len(point) != 2
            or not isinstance(point[0], datetime)
        ):
            raise ValueError(
                f"{field_name} entries must be (datetime, equity) tuples"
            )
        _require_finite_number(
            point[1],
            f"{field_name}[{index}].equity",
        )
        if previous_timestamp is not None and point[0] <= previous_timestamp:
            raise ValueError(
                f"{field_name} timestamps must be strictly increasing"
            )
        previous_timestamp = point[0]


def _financial_equal(left, right) -> bool:
    return isclose(
        float(left),
        float(right),
        rel_tol=1e-12,
        abs_tol=1e-8,
    )


def _financial_exact_equal(left, right) -> bool:
    """Preserve exact stored float category boundaries such as zero/sign."""

    return float(left) == float(right)


def _validate_backtest_metrics(
    value,
    *,
    field_name: str,
    include_profitable: bool,
) -> None:
    expected_fields = (
        _TEST_METRIC_FIELDS
        if include_profitable
        else _BACKTEST_METRIC_FIELDS
    )
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise ValueError(f"{field_name} has an invalid metric field set")

    count_fields = (
        "completed_trade_count",
        "net_profitable_trade_count",
        "net_losing_trade_count",
        "net_breakeven_trade_count",
    )
    for name in count_fields:
        if type(value[name]) is not int or value[name] < 0:
            raise ValueError(f"{field_name}.{name} must be a non-negative integer")

    if (
        value["net_profitable_trade_count"]
        + value["net_losing_trade_count"]
        + value["net_breakeven_trade_count"]
        != value["completed_trade_count"]
    ):
        raise ValueError(f"{field_name} trade counts are inconsistent")

    for name in _BACKTEST_METRIC_FIELDS - set(count_fields):
        _require_finite_number(value[name], f"{field_name}.{name}")

    if value["max_equity_drawdown_pct"] < 0:
        raise ValueError(f"{field_name}.max_equity_drawdown_pct must be non-negative")

    completed = value["completed_trade_count"]
    profitable = value["net_profitable_trade_count"]
    losing = value["net_losing_trade_count"]

    expected_rate = (
        profitable / completed * 100
        if completed
        else 0.0
    )
    if not _financial_exact_equal(
        value["net_profitable_trade_rate_pct"],
        expected_rate,
    ):
        raise ValueError(
            f"{field_name}.net_profitable_trade_rate_pct "
            "does not match completed/profitable counts"
        )

    if value["completed_trade_transaction_cost_total"] < 0:
        raise ValueError(
            f"{field_name}.completed_trade_transaction_cost_total "
            "must be non-negative"
        )

    expected_mean_net = (
        value["net_realized_pnl"] / completed
        if completed
        else 0.0
    )
    if not _financial_exact_equal(
        value["mean_net_pnl_per_completed_trade"],
        expected_mean_net,
    ):
        raise ValueError(
            f"{field_name}.mean_net_pnl_per_completed_trade "
            "does not match net realized PnL / completed trades"
        )

    gross_realized = value["gross_realized_pnl"]
    net_realized = value["net_realized_pnl"]
    transaction_cost_total = value[
        "completed_trade_transaction_cost_total"
    ]
    if not _financial_equal(
        net_realized,
        gross_realized - transaction_cost_total,
    ):
        raise ValueError(
            f"{field_name}.net_realized_pnl must equal "
            "gross realized PnL minus completed-trade transaction costs"
        )
    if transaction_cost_total == 0.0:
        if not _financial_exact_equal(net_realized, gross_realized):
            raise ValueError(
                f"{field_name}.zero transaction cost requires exact "
                "gross/net realized PnL equality"
            )
    elif net_realized > gross_realized and not isclose(
        net_realized,
        gross_realized,
        rel_tol=1e-12,
        abs_tol=0.0,
    ):
        raise ValueError(
            f"{field_name}.net_realized_pnl cannot exceed gross_realized_pnl "
            "when transaction costs are non-negative"
        )

    if completed == 0:
        for name in (
            "gross_realized_pnl",
            "net_realized_pnl",
            "mean_positive_instrument_return_pct",
            "mean_negative_instrument_return_pct",
            "mean_instrument_return_pct",
            "completed_trade_transaction_cost_total",
        ):
            if not _financial_exact_equal(value[name], 0.0):
                raise ValueError(
                    f"{field_name}.{name} must be zero "
                    "when completed_trade_count is zero"
                )
    if value["mean_positive_instrument_return_pct"] < 0:
        raise ValueError(
            f"{field_name}.mean_positive_instrument_return_pct "
            "cannot be negative"
        )
    if value["mean_negative_instrument_return_pct"] > 0:
        raise ValueError(
            f"{field_name}.mean_negative_instrument_return_pct "
            "cannot be positive"
        )

    positive_instrument_mean = value[
        "mean_positive_instrument_return_pct"
    ]
    negative_instrument_mean = value[
        "mean_negative_instrument_return_pct"
    ]
    overall_instrument_mean = value[
        "mean_instrument_return_pct"
    ]
    if not (
        negative_instrument_mean
        <= overall_instrument_mean
        <= positive_instrument_mean
    ):
        raise ValueError(
            f"{field_name}.mean_instrument_return_pct must lie "
            "between the stored negative and positive instrument-return means"
        )

    net_realized = value["net_realized_pnl"]
    if profitable > 0 and losing == 0 and net_realized <= 0:
        raise ValueError(
            f"{field_name}.net_realized_pnl must be positive "
            "when completed trades contain winners and no losers"
        )
    if losing > 0 and profitable == 0 and net_realized >= 0:
        raise ValueError(
            f"{field_name}.net_realized_pnl must be negative "
            "when completed trades contain losers and no winners"
        )
    if profitable == 0 and losing == 0 and not _financial_exact_equal(
        net_realized,
        0.0,
    ):
        raise ValueError(
            f"{field_name}.net_realized_pnl must be zero "
            "when all completed trades are breakeven"
        )

    if include_profitable:
        if type(value["profitable"]) is not bool:
            raise ValueError(f"{field_name}.profitable must be a bool")
        if value["profitable"] != (value["account_return_pct"] > 0):
            raise ValueError(
                f"{field_name}.profitable does not match account_return_pct"
            )


def _validate_account_metrics_against_equity(
    metrics,
    equity_curve,
    *,
    initial_capital: float,
    field_name: str,
) -> None:
    _require_strictly_increasing_equity_curve(
        equity_curve,
        field_name=f"{field_name}.equity_curve",
    )
    equities = [
        _require_finite_number(
            point[1],
            f"{field_name}.equity_curve[{index}].equity",
        )
        for index, point in enumerate(equity_curve)
    ]
    if equities[0] <= 0:
        raise ValueError(
            f"{field_name} starting equity must be strictly positive"
        )
    if not _financial_exact_equal(equities[0], initial_capital):
        raise ValueError(
            f"{field_name} starting equity does not match initial_capital"
        )

    expected_pnl = equities[-1] - equities[0]
    expected_return = expected_pnl / equities[0] * 100
    expected_drawdown = PerformanceMetrics._max_equity_drawdown(
        equities
    )

    for metric_name, expected_value in (
        ("account_pnl", expected_pnl),
        ("account_return_pct", expected_return),
        ("max_equity_drawdown_pct", expected_drawdown),
    ):
        if not _financial_exact_equal(
            metrics[metric_name],
            expected_value,
        ):
            raise ValueError(
                f"{field_name}.{metric_name} does not match "
                "the persisted OOS equity curve"
            )


_RESULT_FIELDS = frozenset(
    {
        "study_revision_id",
        "trial_id",
        "candidate_revision_id",
        "historical_qualification_decision_id",
        "historical_experiment_spec_id",
        "source_dataset_reference_artifact_id",
        "source_dataset_id",
        "dataset_fingerprint",
        "requested_range",
        "instrument_id",
        "timeframe",
        "timezone",
        "strategy_procedure_id",
        "strategy_parameters",
        "initial_capital",
        "risk_economic_configuration",
        "data_treatment_basis",
        "wfa_configuration",
        "wfa_configuration_fingerprint",
        "resolved_prehistory_bars",
        "windows",
        "aggregated_metrics",
        "stitched_equity_curve",
        "stitched_equity_metrics",
        "verdict",
        "evaluator_repository_revision",
    }
)

_WINDOW_FIELDS = frozenset(
    {
        "window_index",
        "train_history",
        "train_scored",
        "test_history",
        "test_scored",
        "selected_params",
        "optimization_evaluations",
        "optimization_stability_score",
        "test_metrics",
        "trade_count",
        "oos_equity_curve",
    }
)

_BOUNDS_FIELDS = frozenset(
    {"count", "first_timestamp", "last_timestamp"}
)

_BACKTEST_METRIC_FIELDS = frozenset(
    {
        "completed_trade_count",
        "net_profitable_trade_count",
        "net_losing_trade_count",
        "net_breakeven_trade_count",
        "net_profitable_trade_rate_pct",
        "mean_positive_instrument_return_pct",
        "mean_negative_instrument_return_pct",
        "mean_instrument_return_pct",
        "gross_realized_pnl",
        "net_realized_pnl",
        "mean_net_pnl_per_completed_trade",
        "completed_trade_transaction_cost_total",
        "account_pnl",
        "account_return_pct",
        "max_equity_drawdown_pct",
    }
)

_TEST_METRIC_FIELDS = _BACKTEST_METRIC_FIELDS | {"profitable"}


def _validate_bounds(value, field_name: str) -> None:
    if not isinstance(value, dict) or set(value) != _BOUNDS_FIELDS:
        raise ValueError(f"{field_name} has an invalid field set")
    if type(value["count"]) is not int or value["count"] < 0:
        raise ValueError(f"{field_name}.count must be a non-negative integer")
    if value["count"] == 0:
        if (
            value["first_timestamp"] is not None
            or value["last_timestamp"] is not None
        ):
            raise ValueError(f"{field_name} empty bounds cannot carry timestamps")
        return
    for name in ("first_timestamp", "last_timestamp"):
        if not isinstance(value[name], datetime):
            raise TypeError(f"{field_name}.{name} must be a datetime")
    if value["first_timestamp"] > value["last_timestamp"]:
        raise ValueError(f"{field_name} timestamps are reversed")


def validate_candidate_wfa_result_payload(value) -> dict:
    if not isinstance(value, dict) or set(value) != _RESULT_FIELDS:
        raise ValueError("candidate WFA result has an invalid top-level field set")

    for field_name in (
        "study_revision_id",
        "trial_id",
        "candidate_revision_id",
        "historical_experiment_spec_id",
        "source_dataset_reference_artifact_id",
        "source_dataset_id",
        "dataset_fingerprint",
        "wfa_configuration_fingerprint",
    ):
        _require_fingerprint(value[field_name], field_name)

    for field_name in (
        "historical_qualification_decision_id",
        "instrument_id",
        "timeframe",
        "timezone",
        "strategy_procedure_id",
        "evaluator_repository_revision",
    ):
        _require_nonempty(value[field_name], field_name)

    requested_range = value["requested_range"]
    if (
        not isinstance(requested_range, dict)
        or set(requested_range) != {"start", "end"}
        or not isinstance(requested_range["start"], datetime)
        or not isinstance(requested_range["end"], datetime)
    ):
        raise ValueError("candidate WFA requested_range is invalid")
    TimeRange(
        requested_range["start"],
        requested_range["end"],
    )

    for field_name in (
        "strategy_parameters",
        "risk_economic_configuration",
        "data_treatment_basis",
        "wfa_configuration",
        "aggregated_metrics",
        "stitched_equity_metrics",
    ):
        if not isinstance(value[field_name], dict):
            raise TypeError(f"{field_name} must be a mapping")

    initial_capital = _require_finite_number(
        value["initial_capital"],
        "initial_capital",
    )
    if initial_capital <= 0:
        raise ValueError("initial_capital must be strictly positive")

    expected_configuration = wfa_window_configuration_payload(
        in_sample_bars=value["wfa_configuration"].get("in_sample_bars"),
        out_sample_bars=value["wfa_configuration"].get("out_sample_bars"),
        step_bars=value["wfa_configuration"].get("step_bars"),
        mode=value["wfa_configuration"].get("mode"),
    )
    if value["wfa_configuration"] != expected_configuration:
        raise ValueError("candidate WFA configuration has unexpected fields")
    if (
        wfa_window_configuration_fingerprint(**expected_configuration)
        != value["wfa_configuration_fingerprint"]
    ):
        raise ValueError("candidate WFA configuration fingerprint mismatch")

    if (
        type(value["resolved_prehistory_bars"]) is not int
        or value["resolved_prehistory_bars"] < 0
    ):
        raise ValueError(
            "resolved_prehistory_bars must be a non-negative integer"
        )
    if value["verdict"] not in {"PASS", "FAIL"}:
        raise ValueError("candidate WFA result verdict must be PASS or FAIL")

    windows = value["windows"]
    if not isinstance(windows, list) or not windows:
        raise ValueError("completed candidate WFA result requires windows")

    test_metrics = []
    optimization_stabilities = []
    scored_oos_bars = 0
    replay_windows = []

    for expected_index, window in enumerate(windows):
        if not isinstance(window, dict) or set(window) != _WINDOW_FIELDS:
            raise ValueError("candidate WFA window has an invalid field set")
        if window["window_index"] != expected_index:
            raise ValueError("candidate WFA window indexes must be contiguous")

        for name in (
            "train_history",
            "train_scored",
            "test_history",
            "test_scored",
        ):
            _validate_bounds(window[name], f"window.{name}")

        if (
            window["train_history"]["count"]
            != value["resolved_prehistory_bars"]
            or window["test_history"]["count"]
            != value["resolved_prehistory_bars"]
        ):
            raise ValueError(
                "candidate WFA history counts do not match resolved prehistory"
            )
        if (
            window["train_scored"]["count"]
            != expected_configuration["in_sample_bars"]
            or window["test_scored"]["count"]
            != expected_configuration["out_sample_bars"]
        ):
            raise ValueError(
                "candidate WFA scored counts do not match WFA configuration"
            )

        if (
            window["train_history"]["count"]
            and window["train_history"]["last_timestamp"]
            >= window["train_scored"]["first_timestamp"]
        ):
            raise ValueError("candidate WFA train history overlaps scored bars")
        if (
            window["test_history"]["count"]
            and window["test_history"]["last_timestamp"]
            >= window["test_scored"]["first_timestamp"]
        ):
            raise ValueError("candidate WFA test history overlaps scored bars")
        if (
            window["train_scored"]["last_timestamp"]
            >= window["test_scored"]["first_timestamp"]
        ):
            raise ValueError("candidate WFA train/test scored boundaries overlap")

        if not isinstance(window["selected_params"], dict):
            raise TypeError("window selected_params must be a mapping")
        if window["selected_params"] != value["strategy_parameters"]:
            raise ValueError(
                "window selected_params must equal fixed strategy parameters"
            )

        evaluations = window["optimization_evaluations"]
        if not isinstance(evaluations, list) or len(evaluations) != 1:
            raise ValueError(
                "fixed-strategy WFA requires one optimizer evaluation per window"
            )
        evaluation = evaluations[0]
        if (
            not isinstance(evaluation, dict)
            or set(evaluation) != {"params", "score", "metrics"}
            or evaluation["params"] != value["strategy_parameters"]
        ):
            raise ValueError("candidate WFA optimizer evidence is invalid")
        _validate_backtest_metrics(
            evaluation["metrics"],
            field_name="optimizer evaluation metrics",
            include_profitable=False,
        )

        evaluation_score = _require_finite_number(
            evaluation["score"],
            "optimizer evaluation score",
        )
        if GridSearchOptimizer._score(evaluation["metrics"]) != evaluation_score:
            raise ValueError(
                "candidate WFA optimizer score does not match existing M5 scoring"
            )

        stability = _require_finite_number(
            window["optimization_stability_score"],
            "optimization_stability_score",
        )
        if (
            WalkForwardMetrics.optimization_stability_score([evaluation_score])
            != stability
        ):
            raise ValueError(
                "candidate WFA optimizer stability does not match existing M5 evidence"
            )
        optimization_stabilities.append(stability)

        if type(window["trade_count"]) is not int or window["trade_count"] < 0:
            raise ValueError("window trade_count must be a non-negative integer")
        _validate_backtest_metrics(
            window["test_metrics"],
            field_name="window test_metrics",
            include_profitable=True,
        )
        if (
            window["trade_count"]
            != window["test_metrics"]["completed_trade_count"]
        ):
            raise ValueError(
                "window trade_count does not match completed_trade_count"
            )

        _require_strictly_increasing_equity_curve(
            window["oos_equity_curve"],
            field_name="window oos_equity_curve",
        )
        if (
            len(window["oos_equity_curve"])
            != window["test_scored"]["count"]
        ):
            raise ValueError(
                "window OOS equity count does not match scored OOS bars"
            )
        if (
            window["oos_equity_curve"][0][0]
            != window["test_scored"]["first_timestamp"]
            or window["oos_equity_curve"][-1][0]
            != window["test_scored"]["last_timestamp"]
        ):
            raise ValueError(
                "window OOS equity timestamps do not match scored OOS bounds"
            )

        _validate_account_metrics_against_equity(
            window["test_metrics"],
            window["oos_equity_curve"],
            initial_capital=initial_capital,
            field_name=f"window {window['window_index']} test_metrics",
        )

        test_metrics.append(window["test_metrics"])
        scored_oos_bars += window["test_scored"]["count"]
        replay_windows.append(
            SimpleNamespace(
                window_index=window["window_index"],
                backtest_result=SimpleNamespace(
                    equity_curve=window["oos_equity_curve"]
                ),
            )
        )

    expected_aggregated = WalkForwardMetrics.aggregate(test_metrics)
    expected_aggregated["avg_optimization_stability"] = round(
        sum(optimization_stabilities) / len(optimization_stabilities),
        4,
    )
    if value["aggregated_metrics"] != expected_aggregated:
        raise ValueError(
            "candidate WFA aggregated metrics do not match existing M5 aggregation"
        )

    _require_strictly_increasing_equity_curve(
        value["stitched_equity_curve"],
        field_name="stitched_equity_curve",
    )
    if len(value["stitched_equity_curve"]) != scored_oos_bars:
        raise ValueError(
            "stitched_equity_curve count does not match scored OOS bars"
        )

    (
        expected_stitched_curve,
        expected_exact_stitched_curve,
    ) = EquityStitcher.stitch_with_exact(replay_windows)
    if value["stitched_equity_curve"] != expected_stitched_curve:
        raise ValueError(
            "candidate WFA stitched equity does not match existing M5 stitching"
        )

    expected_stitched_metrics = (
        WalkForwardMetrics.compute_stitched_equity_metrics(
            expected_exact_stitched_curve
        )
    )
    if value["stitched_equity_metrics"] != expected_stitched_metrics:
        raise ValueError(
            "candidate WFA stitched metrics do not match existing M5 evidence"
        )

    verdict_defaults = WalkForwardResult.from_windows.__func__.__kwdefaults__
    expected_verdict = WalkForwardResult._evaluate_verdict(
        metrics=expected_aggregated,
        stitched_metrics=expected_stitched_metrics,
        min_consistency=verdict_defaults["min_consistency"],
        max_drawdown_pct=verdict_defaults["max_drawdown_pct"],
        min_stability_score=verdict_defaults["min_stability_score"],
    )
    if value["verdict"] != expected_verdict:
        raise ValueError(
            "candidate WFA verdict contradicts existing M5 PASS/FAIL rules"
        )

    _require_finite_tree(value, "candidate_wfa_result")
    return value


def wfa_window_configuration_payload(
    *,
    in_sample_bars: int,
    out_sample_bars: int,
    step_bars: int,
    mode: str,
) -> dict:
    for field_name, value in (
        ("in_sample_bars", in_sample_bars),
        ("out_sample_bars", out_sample_bars),
        ("step_bars", step_bars),
    ):
        if type(value) is not int or value <= 0:
            raise ValueError(f"{field_name} must be a positive integer")
    if mode not in {"rolling", "expanding"}:
        raise ValueError("mode must be rolling or expanding")
    return {
        "in_sample_bars": in_sample_bars,
        "out_sample_bars": out_sample_bars,
        "step_bars": step_bars,
        "mode": mode,
    }


def wfa_window_configuration_fingerprint(**kwargs) -> str:
    return canonical_fingerprint(
        wfa_window_configuration_payload(**kwargs),
        schema=CANDIDATE_WFA_CONFIG_SCHEMA_ID,
    )


def _sequence_bounds(values) -> dict:
    values = tuple(values)
    return {
        "count": len(values),
        "first_timestamp": (
            values[0].timestamp if values else None
        ),
        "last_timestamp": (
            values[-1].timestamp if values else None
        ),
    }


def _optimization_evaluations_payload(window_result) -> list[dict]:
    return [
        {
            "params": dict(evaluation.params),
            "score": evaluation.score,
            "metrics": dict(evaluation.metrics),
        }
        for evaluation in window_result.optimization_result.evaluations
    ]


def candidate_wfa_result_payload(
    *,
    study_revision_id: str,
    trial_id: str,
    candidate_revision_id: str,
    historical_qualification_decision_id: str,
    historical_experiment_spec_id: str,
    source_dataset_reference_artifact_id: str,
    source_dataset_id: str,
    dataset_fingerprint: str,
    requested_range: TimeRange,
    instrument_id: str,
    timeframe: str,
    timezone: str,
    strategy_procedure_id: str,
    strategy_parameters: Mapping,
    initial_capital: float,
    risk_economic_configuration: Mapping,
    data_treatment_basis: Mapping,
    wfa_configuration: Mapping,
    wfa_configuration_fingerprint: str,
    resolved_prehistory_bars: int,
    expected_windows,
    result,
    evaluator_repository_revision: str,
) -> dict:
    for field_name, value in (
        ("study_revision_id", study_revision_id),
        ("trial_id", trial_id),
        ("candidate_revision_id", candidate_revision_id),
        ("historical_experiment_spec_id", historical_experiment_spec_id),
        ("source_dataset_reference_artifact_id", source_dataset_reference_artifact_id),
        ("source_dataset_id", source_dataset_id),
        ("dataset_fingerprint", dataset_fingerprint),
        ("wfa_configuration_fingerprint", wfa_configuration_fingerprint),
    ):
        _require_fingerprint(value, field_name)

    for field_name, value in (
        ("historical_qualification_decision_id", historical_qualification_decision_id),
        ("instrument_id", instrument_id),
        ("timeframe", timeframe),
        ("timezone", timezone),
        ("strategy_procedure_id", strategy_procedure_id),
        ("evaluator_repository_revision", evaluator_repository_revision),
    ):
        _require_nonempty(value, field_name)

    if not isinstance(requested_range, TimeRange):
        raise TypeError("requested_range must be a TimeRange")
    if type(resolved_prehistory_bars) is not int or resolved_prehistory_bars < 0:
        raise ValueError("resolved_prehistory_bars must be a non-negative integer")

    expected_windows = tuple(expected_windows)
    result_windows = tuple(result.windows)
    if len(expected_windows) != len(result_windows):
        raise ValueError("expected and returned WFA window counts differ")

    windows = []
    for expected, returned in zip(expected_windows, result_windows):
        if expected.window_index != returned.window_index:
            raise ValueError("expected and returned WFA window indexes differ")
        windows.append(
            {
                "window_index": returned.window_index,
                "train_history": _sequence_bounds(expected.train_history_bars),
                "train_scored": _sequence_bounds(expected.train_bars),
                "test_history": _sequence_bounds(expected.test_history_bars),
                "test_scored": _sequence_bounds(expected.test_bars),
                "selected_params": dict(returned.best_params),
                "optimization_evaluations": _optimization_evaluations_payload(
                    returned
                ),
                "optimization_stability_score": (
                    returned.optimization_stability_score
                ),
                "test_metrics": dict(returned.test_metrics),
                "trade_count": returned.trade_count,
                "oos_equity_curve": list(
                    returned.backtest_result.equity_curve
                ),
            }
        )

    payload = {
        "study_revision_id": study_revision_id,
        "trial_id": trial_id,
        "candidate_revision_id": candidate_revision_id,
        "historical_qualification_decision_id": (
            historical_qualification_decision_id
        ),
        "historical_experiment_spec_id": historical_experiment_spec_id,
        "source_dataset_reference_artifact_id": (
            source_dataset_reference_artifact_id
        ),
        "source_dataset_id": source_dataset_id,
        "dataset_fingerprint": dataset_fingerprint,
        "requested_range": {
            "start": requested_range.start,
            "end": requested_range.end,
        },
        "instrument_id": instrument_id,
        "timeframe": timeframe,
        "timezone": timezone,
        "strategy_procedure_id": strategy_procedure_id,
        "strategy_parameters": dict(strategy_parameters),
        "initial_capital": initial_capital,
        "risk_economic_configuration": dict(risk_economic_configuration),
        "data_treatment_basis": dict(data_treatment_basis),
        "wfa_configuration": dict(wfa_configuration),
        "wfa_configuration_fingerprint": wfa_configuration_fingerprint,
        "resolved_prehistory_bars": resolved_prehistory_bars,
        "windows": windows,
        "aggregated_metrics": dict(result.aggregated_metrics),
        "stitched_equity_curve": list(result.stitched_equity_curve),
        "stitched_equity_metrics": dict(result.stitched_equity_metrics),
        "verdict": result.verdict,
        "evaluator_repository_revision": evaluator_repository_revision,
    }
    return validate_candidate_wfa_result_payload(payload)


def candidate_wfa_result_bytes(**kwargs) -> bytes:
    return canonical_bytes(
        candidate_wfa_result_payload(**kwargs),
        schema=CANDIDATE_WFA_RESULT_SCHEMA_ID,
    )


def decode_candidate_wfa_result_bytes(payload: bytes) -> dict:
    decoded = decode_canonical_bytes(
        payload,
        schema=CANDIDATE_WFA_RESULT_SCHEMA_ID,
    )
    return validate_candidate_wfa_result_payload(decoded)


@dataclass(frozen=True)
class CandidateWfaDecision:
    decision_id: str
    created_at: datetime
    evaluator_version: str
    study_revision_id: str
    trial_id: str
    candidate_revision_id: str
    historical_qualification_decision_id: str
    wfa_configuration_fingerprint: str
    evidence_validity: WfaEvidenceValidity
    outcome: WfaQualificationOutcome
    reason: str
    evaluator_repository_revision: str | None = None
    dataset_reference_artifact_id: str | None = None
    dataset_id: str | None = None
    dataset_fingerprint: str | None = None
    result_artifact_id: str | None = None
    wfa_verdict: str | None = None
    identity_schema: str = CANDIDATE_WFA_DECISION_SCHEMA_ID

    def __post_init__(self) -> None:
        for field_name in (
            "decision_id",
            "evaluator_version",
            "historical_qualification_decision_id",
            "reason",
        ):
            _require_nonempty(getattr(self, field_name), field_name)

        for field_name in (
            "study_revision_id",
            "trial_id",
            "candidate_revision_id",
            "wfa_configuration_fingerprint",
        ):
            _require_fingerprint(getattr(self, field_name), field_name)

        if not isinstance(self.created_at, datetime):
            raise TypeError("created_at must be a datetime")
        if self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        if not isinstance(self.evidence_validity, WfaEvidenceValidity):
            raise TypeError("evidence_validity must be a WfaEvidenceValidity")
        if not isinstance(self.outcome, WfaQualificationOutcome):
            raise TypeError("outcome must be a WfaQualificationOutcome")
        if self.identity_schema != CANDIDATE_WFA_DECISION_SCHEMA_ID:
            raise ValueError("unexpected CandidateWfaDecision schema")

        if self.evaluator_repository_revision is not None:
            _require_nonempty(
                self.evaluator_repository_revision,
                "evaluator_repository_revision",
            )

        dataset_values = (
            self.dataset_reference_artifact_id,
            self.dataset_id,
            self.dataset_fingerprint,
        )
        if any(value is not None for value in dataset_values):
            if any(value is None for value in dataset_values):
                raise ValueError(
                    "dataset reference, dataset_id and dataset_fingerprint "
                    "must be established together"
                )
            for field_name, value in zip(
                (
                    "dataset_reference_artifact_id",
                    "dataset_id",
                    "dataset_fingerprint",
                ),
                dataset_values,
            ):
                _require_fingerprint(value, field_name)

        if self.result_artifact_id is not None:
            _require_fingerprint(self.result_artifact_id, "result_artifact_id")
        if self.wfa_verdict is not None and self.wfa_verdict not in {"PASS", "FAIL"}:
            raise ValueError("wfa_verdict must be PASS, FAIL or None")

        if self.outcome is WfaQualificationOutcome.ELIGIBLE:
            if (
                self.evidence_validity is not WfaEvidenceValidity.VALID
                or self.wfa_verdict != "PASS"
                or self.result_artifact_id is None
            ):
                raise ValueError("ELIGIBLE requires VALID PASS evidence")
            self._require_complete_evidence_identity()
            return

        if self.outcome is WfaQualificationOutcome.REJECTED:
            if (
                self.evidence_validity is not WfaEvidenceValidity.VALID
                or self.wfa_verdict != "FAIL"
                or self.result_artifact_id is None
            ):
                raise ValueError("REJECTED requires VALID FAIL evidence")
            self._require_complete_evidence_identity()
            return

        if self.wfa_verdict is not None or self.result_artifact_id is not None:
            raise ValueError(
                "non-economic WFA outcome cannot fabricate verdict/result artifact"
            )

        if self.outcome is WfaQualificationOutcome.INSUFFICIENT:
            if self.evidence_validity is not WfaEvidenceValidity.INSUFFICIENT:
                raise ValueError("INSUFFICIENT requires INSUFFICIENT evidence")
            self._require_complete_evidence_identity()
            return

        if self.outcome is not WfaQualificationOutcome.INVALID:
            raise ValueError("unsupported WFA qualification outcome")
        if self.evidence_validity is not WfaEvidenceValidity.INVALID:
            raise ValueError("INVALID requires INVALID evidence")

    def _require_complete_evidence_identity(self) -> None:
        if self.evaluator_repository_revision is None:
            raise ValueError("completed/insufficient WFA requires evaluator revision")
        if self.dataset_reference_artifact_id is None:
            raise ValueError("completed/insufficient WFA requires dataset authority")
