from core.backtest.backtest_result import BacktestResult
from core.backtest.backtest_runner import print_performance_summary
from core.backtest.performance_metrics import PerformanceMetrics


def test_backtest_reporting_uses_result_aware_metrics(
    monkeypatch,
    capsys,
) -> None:
    backtest_result = BacktestResult(
        trades=[],
        bar_records=[],
        session_id="reporting-path",
    )
    received_results = []

    def summarize_backtest(result):
        received_results.append(result)
        return {
            "completed_trade_count": 0,
            "account_return_pct": 1.2345,
        }

    def legacy_summarize(_trades):
        raise AssertionError("Backtest reporting used legacy trade-only metrics")

    monkeypatch.setattr(
        PerformanceMetrics,
        "summarize_backtest",
        staticmethod(summarize_backtest),
    )
    monkeypatch.setattr(
        PerformanceMetrics,
        "summarize",
        staticmethod(legacy_summarize),
    )

    print_performance_summary(backtest_result)

    assert received_results == [backtest_result]
    assert capsys.readouterr().out == (
        "\n=== PERFORMANCE METRICS ===\n"
        "completed_trade_count: 0\n"
        "account_return_pct: 1.23\n"
    )
