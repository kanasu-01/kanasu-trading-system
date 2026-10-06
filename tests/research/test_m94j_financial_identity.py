from dataclasses import replace

import pytest

from core.config.execution_config import ExecutionConfig
from core.research.backtest_financial_configuration import (
    default_backtest_financial_configuration,
    effective_backtest_financial_configuration,
    resolve_registered_backtest_financial_configuration,
)
from core.runtime.runtime_context import RuntimeContext


def test_partial_registration_resolves_to_complete_financial_identity():
    resolved = resolve_registered_backtest_financial_configuration(
        {"risk_per_trade_pct": 2.0}
    )

    expected = default_backtest_financial_configuration()
    expected["risk_per_trade_pct"] = 2.0

    assert resolved == expected
    assert set(resolved) == set(expected)


def test_unknown_registered_financial_field_fails_closed():
    with pytest.raises(
        ValueError,
        match="unknown financial fields",
    ):
        resolve_registered_backtest_financial_configuration(
            {
                "risk_per_trade_pct": 1.0,
                "invented_cost": 7,
            }
        )


def test_omitted_registered_slippage_is_frozen_and_runtime_drift_detected():
    registered = resolve_registered_backtest_financial_configuration(
        {"risk_per_trade_pct": 1.0}
    )

    runtime = RuntimeContext(
        execution_config=replace(
            ExecutionConfig(),
            slippage_pct=0.009,
        )
    )

    assert (
        effective_backtest_financial_configuration(runtime)
        != registered
    )


def test_identical_complete_effective_identity_matches_registration():
    runtime = RuntimeContext()

    registered = resolve_registered_backtest_financial_configuration(
        default_backtest_financial_configuration()
    )

    assert (
        effective_backtest_financial_configuration(runtime)
        == registered
    )

def test_claimed_input_complete_identity_accepts_and_runtime_drift_fails():
    from tests.research.test_m94d_claimed_trial_execution_inputs import (
        _inputs,
        _plan,
    )
    from core.research.claimed_trial_execution_inputs import (
        ClaimedTrialInputValidationError,
        validate_claimed_trial_execution_inputs,
    )

    complete = default_backtest_financial_configuration()

    validate_claimed_trial_execution_inputs(
        _plan(risk=complete),
        _inputs(risk=complete),
    )

    with pytest.raises(
        ClaimedTrialInputValidationError,
        match="complete registered Trial plan",
    ):
        validate_claimed_trial_execution_inputs(
            _plan(risk=complete),
            _inputs(
                risk=complete,
                runtime_risk=2.0,
            ),
        )


def test_historical_incomplete_registered_identity_fails_closed():
    from tests.research.test_m94d_claimed_trial_execution_inputs import (
        _inputs,
        _plan,
    )
    from core.research.claimed_trial_execution_inputs import (
        ClaimedTrialInputValidationError,
        validate_claimed_trial_execution_inputs,
    )

    incomplete = {
        "risk_per_trade_pct": 1.0,
    }

    with pytest.raises(
        ClaimedTrialInputValidationError,
        match="complete registered Trial plan",
    ):
        validate_claimed_trial_execution_inputs(
            _plan(risk=incomplete),
            _inputs(risk=incomplete),
        )

def test_default_financial_identity_is_default_runtime_identity():
    assert (
        default_backtest_financial_configuration()
        == effective_backtest_financial_configuration(
            RuntimeContext()
        )
    )
