from datetime import datetime, timezone

import pytest

from core.config.backtest_config import BacktestConfig
from core.market_data.historical_coverage import TimeRange
from core.research.claimed_trial_execution_inputs import (
    ClaimedTrialExecutionInputs,
    validate_claimed_trial_execution_inputs,
)
from core.research.models.dataset import PriceAdjustmentBasis
from core.research.models.registered_study import (
    EvidenceReusePolicy,
)
from core.research.registered_trial_execution_plan import (
    RegisteredTrialExecutionPlan,
)
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.strategies.base_strategy import BaseStrategy


UTC = timezone.utc
JAN = datetime(2020, 1, 1, tzinfo=UTC)
FEB = datetime(2020, 2, 1, tzinfo=UTC)


class FixtureStrategy(BaseStrategy):
    def __init__(self, params):
        super().__init__(
            "fixture_strategy",
            params=params,
        )

    def on_new_candle(self, series):
        return None

    def reset(self):
        return None


def _plan(
    *,
    risk=None,
    data_treatment=None,
):
    return RegisteredTrialExecutionPlan(
        trial_id="trial-fixture",
        study_revision_id="revision-fixture",
        instrument_id="NSE:A",
        strategy_procedure_id="fixture-procedure-v1",
        timeframe="1d",
        research_range=TimeRange(JAN, FEB),
        trial_range=TimeRange(JAN, FEB),
        timezone="UTC",
        initial_capital=1_000_000.0,
        risk_economic_configuration=(
            risk
            if risk is not None
            else {
                "risk_per_trade_pct": 1.0,
            }
        ),
        parameter_configuration={
            "fast": 5,
            "slow": 20,
        },
        data_treatment_basis=(
            data_treatment
            if data_treatment is not None
            else {
                "price_adjustment": "raw",
            }
        ),
        repository_revision="repo-fixture",
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
    )


def _inputs(
    *,
    params=None,
    risk=None,
    data_treatment=None,
    runtime_risk=1.0,
    price_basis=PriceAdjustmentBasis.RAW,
):
    resolved_params = (
        params
        if params is not None
        else {
            "fast": 5,
            "slow": 20,
        }
    )

    config = BacktestConfig(
        symbol="A",
        timeframe="1d",
        strategy_name="fixture_strategy",
        start=JAN,
        end=FEB,
        initial_capital=1_000_000.0,
        enable_replay=False,
        enable_visualization=False,
        enable_exports=False,
        strategy_params=dict(
            resolved_params
        ),
        timezone="UTC",
    )

    return ClaimedTrialExecutionInputs(
        strategy=FixtureStrategy(
            dict(resolved_params)
        ),
        config=config,
        runtime_context=RuntimeContext(
            risk_per_trade_pct=runtime_risk
        ),
        dataset_context=DatasetContext(
            symbol="A",
            timeframe="1d",
            timezone="UTC",
        ),
        provider="fixture-provider",
        price_adjustment_basis=(
            price_basis
        ),
        strategy_procedure_id=(
            "fixture-procedure-v1"
        ),
        risk_economic_configuration=(
            risk
            if risk is not None
            else {
                "risk_per_trade_pct": 1.0,
            }
        ),
        data_treatment_basis=(
            data_treatment
            if data_treatment is not None
            else {
                "price_adjustment": "raw",
            }
        ),
    )


def test_valid_explicit_execution_inputs_match_registered_plan():
    validate_claimed_trial_execution_inputs(
        _plan(),
        _inputs(),
    )


def test_rejects_parameter_drift_from_registered_trial_variant():
    with pytest.raises(
        ValueError,
        match="strategy parameters",
    ):
        validate_claimed_trial_execution_inputs(
            _plan(),
            _inputs(
                params={
                    "fast": 10,
                    "slow": 40,
                }
            ),
        )


def test_rejects_risk_economic_declaration_drift():
    with pytest.raises(
        ValueError,
        match="risk/economic declaration",
    ):
        validate_claimed_trial_execution_inputs(
            _plan(),
            _inputs(
                risk={
                    "risk_per_trade_pct": 2.0,
                }
            ),
        )



def test_rejects_data_treatment_declaration_drift():
    with pytest.raises(
        ValueError,
        match="data-treatment declaration",
    ):
        validate_claimed_trial_execution_inputs(
            _plan(),
            _inputs(
                data_treatment={
                    "price_adjustment": "adjusted",
                }
            ),
        )


def test_m94g1_rejects_matching_risk_declaration_when_runtime_risk_drifted():
    with pytest.raises(
        ValueError,
        match="risk|economic|runtime",
    ):
        validate_claimed_trial_execution_inputs(
            _plan(),
            _inputs(
                runtime_risk=2.0,
            ),
        )


def test_m94g1_rejects_matching_data_declaration_when_price_basis_drifted():
    with pytest.raises(
        ValueError,
        match="data|price|adjustment",
    ):
        validate_claimed_trial_execution_inputs(
            _plan(),
            _inputs(
                price_basis=(
                    PriceAdjustmentBasis.ADJUSTED
                ),
            ),
        )

def test_m94g1_rejects_unverifiable_risk_economic_semantics():
    declaration = {
        "risk_per_trade_pct": 1.0,
        "execution_policy": "fixture-v1",
    }

    with pytest.raises(
        ValueError,
        match="risk/economic.*unverifiable",
    ):
        validate_claimed_trial_execution_inputs(
            _plan(
                risk=declaration,
            ),
            _inputs(
                risk=declaration,
            ),
        )


def test_m94g1_rejects_unverifiable_data_treatment_semantics():
    declaration = {
        "price_adjustment": "raw",
        "corporate_actions": "explicit",
    }

    with pytest.raises(
        ValueError,
        match="data-treatment.*unverifiable",
    ):
        validate_claimed_trial_execution_inputs(
            _plan(
                data_treatment=declaration,
            ),
            _inputs(
                data_treatment=declaration,
            ),
        )