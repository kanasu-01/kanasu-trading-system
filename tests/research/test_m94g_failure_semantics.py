import pytest

import core.runtime.backtest_runtime as backtest_runtime
from core.research.backtest_research_orchestrator import (
    BacktestResearchOrchestrator,
)
from core.runtime.backtest_runtime import (
    DeterministicBacktestComputationError,
    TransientBacktestOperationalError,
)


class _Config:
    initial_capital = 100000.0


class _FailingEngine:
    error = RuntimeError("unconfigured")

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def run_stream(self, candles):
        raise self.error


def _execute_with_fake_engine(monkeypatch, error):
    _FailingEngine.error = error
    monkeypatch.setattr(
        backtest_runtime,
        "BacktestEngine",
        _FailingEngine,
    )

    return backtest_runtime.execute_backtest_candles(
        candles=[],
        strategy=object(),
        config=_Config(),
        runtime_context=object(),
        dataset_context=object(),
    )


def test_production_backtest_adapter_types_deterministic_compute_failure(
    monkeypatch,
):
    original = RuntimeError("deterministic engine failure")

    with pytest.raises(
        DeterministicBacktestComputationError,
    ) as captured:
        _execute_with_fake_engine(
            monkeypatch,
            original,
        )

    assert captured.value.original_error is original
    assert str(captured.value) == "deterministic engine failure"


def test_production_backtest_adapter_types_operational_io_failure(
    monkeypatch,
):
    original = OSError("journal unavailable")

    with pytest.raises(
        TransientBacktestOperationalError,
    ) as captured:
        _execute_with_fake_engine(
            monkeypatch,
            original,
        )

    assert captured.value.original_error is original
    assert str(captured.value) == "journal unavailable"


@pytest.mark.parametrize(
    ("error", "expected"),
    (
        (
            DeterministicBacktestComputationError(
                RuntimeError("compute")
            ),
            "deterministic_compute_failure",
        ),
        (
            TransientBacktestOperationalError(
                OSError("io")
            ),
            "transient_operational_failure",
        ),
        (
            RuntimeError("unclassified"),
            "unknown_failure",
        ),
    ),
)
def test_orchestrator_semantic_failure_classification(
    error,
    expected,
):
    assert (
        BacktestResearchOrchestrator
        ._semantic_failure_classification(error)
        == expected
    )


def test_orchestrator_semantic_failure_message_uses_original_error():
    error = DeterministicBacktestComputationError(
        RuntimeError("authoritative compute failed")
    )

    assert (
        BacktestResearchOrchestrator
        ._semantic_failure_message(error)
        == "authoritative compute failed"
    )
