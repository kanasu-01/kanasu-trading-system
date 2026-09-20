from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.walk_forward.result import WalkForwardResult


def evaluate(
    *,
    metric_overrides=None,
    stitched_overrides=None,
):
    metrics = {
        "consistency_ratio": 0.75,
        "avg_account_return_pct": 1.0,
        "worst_equity_drawdown_pct": 10.0,
        "account_return_stability_score": 0.50,
    }
    stitched_metrics = {
        "stitched_total_return_pct": 4.0,
        "stitched_max_drawdown_pct": 12.0,
    }

    if metric_overrides:
        metrics.update(metric_overrides)

    if stitched_overrides:
        stitched_metrics.update(stitched_overrides)

    return WalkForwardResult._evaluate_verdict(
        metrics=metrics,
        stitched_metrics=stitched_metrics,
        min_consistency=0.60,
        max_drawdown_pct=20.0,
        min_stability_score=0.20,
    )


def test_account_valid_wfa_verdict_passes() -> None:
    assert evaluate() == "PASS"


@pytest.mark.parametrize(
    ("metric_overrides", "stitched_overrides"),
    [
        ({"consistency_ratio": 0.59}, None),
        ({"avg_account_return_pct": 0.0}, None),
        ({"worst_equity_drawdown_pct": 20.01}, None),
        (None, {"stitched_total_return_pct": 0.0}),
        (None, {"stitched_max_drawdown_pct": 20.01}),
        ({"account_return_stability_score": 0.19}, None),
    ],
)
def test_account_valid_wfa_verdict_rejects_failed_criteria(
    metric_overrides,
    stitched_overrides,
) -> None:
    assert (
        evaluate(
            metric_overrides=metric_overrides,
            stitched_overrides=stitched_overrides,
        )
        == "FAIL"
    )


def test_wfa_verdict_accepts_exact_non_return_boundaries() -> None:
    assert (
        evaluate(
            metric_overrides={
                "consistency_ratio": 0.60,
                "avg_account_return_pct": 0.01,
                "worst_equity_drawdown_pct": 20.0,
                "account_return_stability_score": 0.20,
            },
            stitched_overrides={
                "stitched_total_return_pct": 0.01,
                "stitched_max_drawdown_pct": 20.0,
            },
        )
        == "PASS"
    )


@pytest.mark.parametrize(
    ("metric_overrides", "stitched_overrides", "expected"),
    [
        (
            {"consistency_ratio": 0.5996},
            None,
            "FAIL",
        ),
        (
            {"avg_account_return_pct": 0.004},
            None,
            "PASS",
        ),
        (
            {"worst_equity_drawdown_pct": 20.004},
            None,
            "FAIL",
        ),
        (
            None,
            {"stitched_total_return_pct": 0.004},
            "PASS",
        ),
        (
            None,
            {"stitched_max_drawdown_pct": 20.004},
            "FAIL",
        ),
        (
            {"account_return_stability_score": 0.1996},
            None,
            "FAIL",
        ),
    ],
)
def test_wfa_verdict_uses_unrounded_threshold_values(
    metric_overrides,
    stitched_overrides,
    expected,
) -> None:
    assert (
        evaluate(
            metric_overrides=metric_overrides,
            stitched_overrides=stitched_overrides,
        )
        == expected
    )


START = datetime(2026, 1, 2, 9, 15)


def result_window(
    *,
    index=0,
    equities=(100.0, 101.0),
    account_return_pct=1.0,
    max_drawdown_pct=0.0,
    optimization_stability_score=1.0,
):
    base = START + timedelta(hours=index)

    return SimpleNamespace(
        window_index=index,
        optimization_stability_score=(
            optimization_stability_score
        ),
        test_metrics={
            "account_return_pct": account_return_pct,
            "max_equity_drawdown_pct": max_drawdown_pct,
        },
        backtest_result=SimpleNamespace(
            equity_curve=[
                (
                    base + timedelta(minutes=15 * point_index),
                    equity,
                )
                for point_index, equity in enumerate(equities)
            ]
        ),
    )


def test_exact_first_window_drawdown_boundary_remains_pass():
    result = WalkForwardResult.from_windows(
        [
            result_window(
                equities=(
                    100_000.0,
                    110_000.0,
                    88_000.0,
                    101_000.0,
                ),
                account_return_pct=1.0,
                max_drawdown_pct=20.0,
            )
        ]
    )

    assert result.stitched_equity_curve == [
        (START, 100_000.0),
        (
            START + timedelta(minutes=15),
            110_000.0,
        ),
        (
            START + timedelta(minutes=30),
            88_000.0,
        ),
        (
            START + timedelta(minutes=45),
            101_000.0,
        ),
    ]
    assert (
        result.stitched_equity_metrics[
            "stitched_max_drawdown_pct"
        ]
        == 20.0
    )
    assert result.verdict == "PASS"


def test_scaled_window_drawdown_boundary_does_not_false_fail():
    first = result_window(
        index=0,
        equities=(100.0, 110.0),
        account_return_pct=1.0,
        max_drawdown_pct=0.0,
    )

    second = result_window(
        index=1,
        equities=(100.0, 80.0, 101.0),
        account_return_pct=1.0,
        max_drawdown_pct=20.0,
    )

    result = WalkForwardResult.from_windows(
        [first, second]
    )

    assert (
        result.stitched_equity_metrics[
            "stitched_max_drawdown_pct"
        ]
        == 20.0
    )
    assert result.verdict == "PASS"


def test_machine_noise_at_drawdown_threshold_does_not_false_fail():
    assert (
        evaluate(
            stitched_overrides={
                "stitched_max_drawdown_pct": (
                    20.00000000000001
                ),
            }
        )
        == "PASS"
    )


def test_genuinely_above_drawdown_threshold_still_fails():
    assert (
        evaluate(
            stitched_overrides={
                "stitched_max_drawdown_pct": 20.000001,
            }
        )
        == "FAIL"
    )


def test_tiny_positive_stitched_return_remains_positive():
    assert (
        evaluate(
            stitched_overrides={
                "stitched_total_return_pct": 1e-15,
            }
        )
        == "PASS"
    )


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        (
            "min_consistency",
            float("nan"),
            "min_consistency must be a finite number",
        ),
        (
            "min_consistency",
            float("inf"),
            "min_consistency must be a finite number",
        ),
        (
            "min_consistency",
            -0.01,
            "min_consistency must be >= 0.0",
        ),
        (
            "min_consistency",
            1.01,
            "min_consistency must be <= 1.0",
        ),
        (
            "min_stability_score",
            float("nan"),
            "min_stability_score must be a finite number",
        ),
        (
            "min_stability_score",
            -0.01,
            "min_stability_score must be >= 0.0",
        ),
        (
            "min_stability_score",
            1.01,
            "min_stability_score must be <= 1.0",
        ),
        (
            "max_drawdown_pct",
            float("nan"),
            "max_drawdown_pct must be a finite number",
        ),
        (
            "max_drawdown_pct",
            float("inf"),
            "max_drawdown_pct must be a finite number",
        ),
        (
            "max_drawdown_pct",
            -0.01,
            "max_drawdown_pct must be >= 0.0",
        ),
        (
            "min_consistency",
            True,
            "min_consistency must be a finite number",
        ),
        (
            "max_drawdown_pct",
            "20",
            "max_drawdown_pct must be a finite number",
        ),
    ],
)
def test_public_factory_rejects_invalid_verdict_thresholds(
    name,
    value,
    message,
):
    kwargs = {name: value}

    with pytest.raises(
        ValueError,
        match=message,
    ):
        WalkForwardResult.from_windows(
            [result_window()],
            **kwargs,
        )


def test_public_factory_accepts_valid_threshold_endpoints():
    result = WalkForwardResult.from_windows(
        [result_window()],
        min_consistency=0.0,
        max_drawdown_pct=0.0,
        min_stability_score=1.0,
    )

    assert result.verdict == "PASS"


@pytest.mark.parametrize(
    "score",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_result_rejects_non_finite_optimization_stability(
    score,
):
    with pytest.raises(
        ValueError,
        match="optimization stability must be finite",
    ):
        WalkForwardResult.from_windows(
            [
                result_window(
                    optimization_stability_score=score,
                )
            ]
        )


@pytest.mark.parametrize(
    ("thresholds", "message"),
    [
        (
            {
                "min_consistency": float("nan"),
                "max_drawdown_pct": 20.0,
                "min_stability_score": 0.20,
            },
            "min_consistency must be a finite number",
        ),
        (
            {
                "min_consistency": 0.60,
                "max_drawdown_pct": float("nan"),
                "min_stability_score": 0.20,
            },
            "max_drawdown_pct must be a finite number",
        ),
        (
            {
                "min_consistency": 0.60,
                "max_drawdown_pct": 20.0,
                "min_stability_score": float("nan"),
            },
            "min_stability_score must be a finite number",
        ),
    ],
)
def test_verdict_evaluator_rejects_invalid_thresholds(
    thresholds,
    message,
):
    metrics = {
        "consistency_ratio": 0.75,
        "avg_account_return_pct": 1.0,
        "worst_equity_drawdown_pct": 10.0,
        "account_return_stability_score": 0.50,
    }
    stitched_metrics = {
        "stitched_total_return_pct": 4.0,
        "stitched_max_drawdown_pct": 12.0,
    }

    with pytest.raises(
        ValueError,
        match=message,
    ):
        WalkForwardResult._evaluate_verdict(
            metrics=metrics,
            stitched_metrics=stitched_metrics,
            **thresholds,
        )
