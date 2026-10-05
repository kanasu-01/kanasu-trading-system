"""Explicit application/core inputs for one claimed registered Trial.

BEHAVIOR IMPACT: ADDED
PRIMARY BEHAVIOR IDS: RESEARCH-RULE-014, RESEARCH-RULE-015
PRESERVED BEHAVIOR IDS: RESEARCH-RULE-010, RESEARCH-RULE-011

M9.4 does not infer strategy procedure mappings, provider mappings or
risk/economic translation from naming conventions. Application/core
composition supplies those concrete inputs explicitly and this module
verifies every registered field that can be checked independently.
"""

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from core.config.backtest_config import BacktestConfig
from core.research.models.dataset import PriceAdjustmentBasis
from core.research.registered_trial_execution_plan import (
    RegisteredTrialExecutionPlan,
)
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.strategies.base_strategy import BaseStrategy
from core.strategies.strategy_factory import (
    get_research_procedure_strategy_class,
    get_strategy_class,
)


class ClaimedTrialInputValidationError(ValueError):
    """Authoritative registered Trial inputs are invalid or inconsistent."""


@dataclass(frozen=True)
class ClaimedTrialExecutionInputs:
    strategy: BaseStrategy
    config: BacktestConfig
    runtime_context: RuntimeContext
    dataset_context: DatasetContext
    provider: str
    price_adjustment_basis: PriceAdjustmentBasis
    strategy_procedure_id: str
    risk_economic_configuration: Mapping[str, Any]
    data_treatment_basis: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(
            self.strategy,
            BaseStrategy,
        ):
            raise TypeError(
                "strategy must be a BaseStrategy"
            )

        if not isinstance(
            self.config,
            BacktestConfig,
        ):
            raise TypeError(
                "config must be a BacktestConfig"
            )

        if not isinstance(
            self.runtime_context,
            RuntimeContext,
        ):
            raise TypeError(
                "runtime_context must be a RuntimeContext"
            )

        if not isinstance(
            self.dataset_context,
            DatasetContext,
        ):
            raise TypeError(
                "dataset_context must be a DatasetContext"
            )

        for field_name, value in (
            ("provider", self.provider),
            (
                "strategy_procedure_id",
                self.strategy_procedure_id,
            ),
        ):
            if (
                not isinstance(value, str)
                or not value
            ):
                raise ValueError(
                    f"{field_name} must be a non-empty string"
                )

        if not isinstance(
            self.price_adjustment_basis,
            PriceAdjustmentBasis,
        ):
            raise TypeError(
                "price_adjustment_basis must be "
                "a PriceAdjustmentBasis"
            )

        for field_name, value in (
            (
                "risk_economic_configuration",
                self.risk_economic_configuration,
            ),
            (
                "data_treatment_basis",
                self.data_treatment_basis,
            ),
        ):
            if not isinstance(
                value,
                Mapping,
            ):
                raise TypeError(
                    f"{field_name} must be a mapping"
                )

            object.__setattr__(
                self,
                field_name,
                MappingProxyType(
                    dict(value)
                ),
            )


TrialExecutionInputResolver = Callable[
    [RegisteredTrialExecutionPlan],
    ClaimedTrialExecutionInputs,
]


def snapshot_claimed_trial_execution_inputs(
    inputs: ClaimedTrialExecutionInputs,
) -> ClaimedTrialExecutionInputs:
    """Return an isolated registered-execution value set."""

    if not isinstance(
        inputs,
        ClaimedTrialExecutionInputs,
    ):
        raise TypeError(
            "inputs must be ClaimedTrialExecutionInputs"
        )

    try:
        return ClaimedTrialExecutionInputs(
            strategy=deepcopy(inputs.strategy),
            config=deepcopy(inputs.config),
            runtime_context=deepcopy(
                inputs.runtime_context
            ),
            dataset_context=deepcopy(
                inputs.dataset_context
            ),
            provider=inputs.provider,
            price_adjustment_basis=(
                inputs.price_adjustment_basis
            ),
            strategy_procedure_id=(
                inputs.strategy_procedure_id
            ),
            risk_economic_configuration=dict(
                inputs.risk_economic_configuration
            ),
            data_treatment_basis=dict(
                inputs.data_treatment_basis
            ),
        )
    except Exception as error:
        raise ClaimedTrialInputValidationError(
            "resolved registered Trial inputs cannot be "
            "isolated for authoritative execution"
        ) from error


def validate_claimed_trial_execution_inputs(
    plan: RegisteredTrialExecutionPlan,
    inputs: ClaimedTrialExecutionInputs,
) -> None:
    """Fail closed when concrete execution inputs drift from registration."""

    if not isinstance(
        plan,
        RegisteredTrialExecutionPlan,
    ):
        raise TypeError(
            "plan must be a RegisteredTrialExecutionPlan"
        )

    if not isinstance(
        inputs,
        ClaimedTrialExecutionInputs,
    ):
        raise TypeError(
            "inputs must be ClaimedTrialExecutionInputs"
        )

    if (
        inputs.strategy_procedure_id
        != plan.strategy_procedure_id
    ):
        raise ClaimedTrialInputValidationError(
            "resolved strategy procedure does not match "
            "the registered Trial plan"
        )

    try:
        expected_strategy_class = (
            get_research_procedure_strategy_class(
                plan.strategy_procedure_id
            )
        )
    except (TypeError, ValueError) as error:
        raise ClaimedTrialInputValidationError(
            "registered strategy procedure identity "
            "is invalid"
        ) from error

    if expected_strategy_class is None:
        raise ClaimedTrialInputValidationError(
            "registered strategy procedure is unverifiable "
            "from canonical executable authority"
        )

    try:
        configured_strategy_class = (
            get_strategy_class(
                inputs.config
            )
        )
    except (TypeError, ValueError) as error:
        raise ClaimedTrialInputValidationError(
            "Backtest strategy configuration cannot prove "
            "the registered procedure"
        ) from error

    if (
        configured_strategy_class
        is not expected_strategy_class
    ):
        raise ClaimedTrialInputValidationError(
            "Backtest strategy configuration does not match "
            "the registered procedure"
        )

    if type(inputs.strategy) is not expected_strategy_class:
        raise ClaimedTrialInputValidationError(
            "executable strategy implementation does not match "
            "the registered procedure"
        )

    if inputs.config.timeframe != plan.timeframe:
        raise ClaimedTrialInputValidationError(
            "resolved Backtest timeframe does not match "
            "the registered Trial plan"
        )

    if (
        inputs.config.start
        != plan.trial_range.start
        or inputs.config.end
        != plan.trial_range.end
    ):
        raise ClaimedTrialInputValidationError(
            "resolved Backtest range does not match "
            "the Trial membership episode"
        )

    if (
        float(inputs.config.initial_capital)
        != float(plan.initial_capital)
    ):
        raise ClaimedTrialInputValidationError(
            "resolved initial capital does not match "
            "the registered Trial plan"
        )

    if inputs.config.timezone != plan.timezone:
        raise ClaimedTrialInputValidationError(
            "resolved Backtest timezone does not match "
            "the registered Trial plan"
        )

    if (
        inputs.dataset_context.timeframe
        != plan.timeframe
        or inputs.dataset_context.timezone
        != plan.timezone
    ):
        raise ClaimedTrialInputValidationError(
            "resolved DatasetContext does not match "
            "the registered timeframe/timezone"
        )

    if (
        inputs.config.symbol
        != inputs.dataset_context.symbol
    ):
        raise ClaimedTrialInputValidationError(
            "BacktestConfig and DatasetContext symbols "
            "must agree"
        )

    registered_parameters = dict(
        plan.parameter_configuration
    )

    if (
        dict(inputs.config.strategy_params)
        != registered_parameters
    ):
        raise ClaimedTrialInputValidationError(
            "resolved Backtest strategy parameters do not "
            "match the registered Trial variant"
        )

    if (
        inputs.strategy.research_parameters()
        != registered_parameters
    ):
        raise ClaimedTrialInputValidationError(
            "resolved strategy effective parameters do not "
            "match the registered Trial variant"
        )

    registered_risk_economic = dict(
        plan.risk_economic_configuration
    )

    if (
        dict(
            inputs.risk_economic_configuration
        )
        != registered_risk_economic
    ):
        raise ClaimedTrialInputValidationError(
            "resolved risk/economic declaration does not "
            "match the registered Trial plan"
        )

    executable_risk_economic = {
        "risk_per_trade_pct": (
            inputs.runtime_context.risk_per_trade_pct
        ),
        "slippage_pct": (
            inputs.runtime_context
            .execution_config
            .slippage_pct
        ),
        "slippage_enabled": (
            inputs.runtime_context
            .execution_config
            .slippage_enabled
        ),
        "brokerage_enabled": (
            inputs.runtime_context
            .execution_config
            .brokerage_enabled
        ),
        **inputs.runtime_context.economic_policy.to_payload(),
    }

    for field_name, registered_value in (
        registered_risk_economic.items()
    ):
        if field_name not in executable_risk_economic:
            raise ClaimedTrialInputValidationError(
                "registered risk/economic declaration "
                f"is unverifiable from executable inputs: {field_name}"
            )

        if (
            executable_risk_economic[field_name]
            != registered_value
        ):
            raise ClaimedTrialInputValidationError(
                "resolved executable risk/economic setting "
                "does not match the registered Trial plan: "
                f"{field_name}"
            )

    registered_data_treatment = dict(
        plan.data_treatment_basis
    )

    if (
        dict(
            inputs.data_treatment_basis
        )
        != registered_data_treatment
    ):
        raise ClaimedTrialInputValidationError(
            "resolved data-treatment declaration does not "
            "match the registered Trial plan"
        )

    executable_data_treatment = {
        "price_adjustment": (
            inputs.price_adjustment_basis.value.lower()
        ),
    }

    for field_name, registered_value in (
        registered_data_treatment.items()
    ):
        if field_name not in executable_data_treatment:
            raise ClaimedTrialInputValidationError(
                "registered data-treatment declaration "
                f"is unverifiable from executable inputs: {field_name}"
            )

        if (
            executable_data_treatment[field_name]
            != registered_value
        ):
            raise ClaimedTrialInputValidationError(
                "resolved executable data-treatment setting "
                "does not match the registered Trial plan: "
                f"{field_name}"
            )
