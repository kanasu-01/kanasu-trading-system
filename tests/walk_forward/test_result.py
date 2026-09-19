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
