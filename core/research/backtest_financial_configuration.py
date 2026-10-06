"""Canonical financial identity for registered Backtest research.

This module freezes the complete set of existing RuntimeContext financial
settings that can affect M4 Backtest economics.  It defines identity only;
it does not implement or change any financial formula.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.config.backtest_economic_policy import (
    BACKTEST_ECONOMIC_POLICY,
)
from core.runtime.runtime_context import RuntimeContext


def effective_backtest_financial_configuration(
    runtime_context: RuntimeContext,
) -> dict[str, Any]:
    """Return the complete effective Backtest financial identity."""

    if not isinstance(runtime_context, RuntimeContext):
        raise TypeError(
            "runtime_context must be a RuntimeContext"
        )

    return {
        "risk_per_trade_pct": runtime_context.risk_per_trade_pct,
        "slippage_pct": runtime_context.execution_config.slippage_pct,
        "slippage_enabled": (
            runtime_context.execution_config.slippage_enabled
        ),
        "brokerage_enabled": (
            runtime_context.execution_config.brokerage_enabled
        ),
        **runtime_context.economic_policy.to_payload(),
    }


def default_backtest_financial_configuration() -> dict[str, Any]:
    """Return the canonical financial identity for default Backtest runtime."""

    return effective_backtest_financial_configuration(
        RuntimeContext()
    )

def resolve_registered_backtest_financial_configuration(
    declared: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve a registration declaration to one complete frozen identity."""

    if not isinstance(declared, Mapping):
        raise TypeError(
            "risk_economic_configuration must be a mapping"
        )

    defaults = default_backtest_financial_configuration()
    unknown = set(declared) - set(defaults)

    if unknown:
        raise ValueError(
            "risk_economic_configuration contains unknown "
            "financial fields: "
            + ", ".join(sorted(unknown))
        )

    resolved = dict(defaults)
    resolved.update(dict(declared))
    return resolved
