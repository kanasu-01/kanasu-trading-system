"""Versioned fixed economics for canonical Backtest execution."""

from dataclasses import dataclass
from math import isfinite


BACKTEST_ECONOMIC_POLICY_ID = "kanasu.backtest-economics.v1"


@dataclass(frozen=True)
class BacktestEconomicPolicy:
    """Fixed M4 Backtest economics shared by execution and research identity."""

    policy_id: str = BACKTEST_ECONOMIC_POLICY_ID
    max_position_pct: float = 20.0
    max_daily_loss_pct: float = 3.0
    max_weekly_loss_pct: float = 6.0
    max_total_risk_pct: float = 5.0
    max_open_trades: int = 5
    stop_buffer_pct: float = 0.2
    stop_min_tick: float = 0.05
    fallback_long_stop_multiplier: float = 0.98
    brokerage_rate: float = 0.0003
    brokerage_cap: float = 20.0
    tax_rate: float = 0.0005
    cost_rounding_digits: int = 2

    def __post_init__(self) -> None:
        if not isinstance(self.policy_id, str) or not self.policy_id:
            raise ValueError("policy_id must be a non-empty string")

        positive = {
            "max_position_pct": self.max_position_pct,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_weekly_loss_pct": self.max_weekly_loss_pct,
            "max_total_risk_pct": self.max_total_risk_pct,
            "stop_min_tick": self.stop_min_tick,
        }
        for name, value in positive.items():
            if not isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")

        if not isfinite(self.stop_buffer_pct) or self.stop_buffer_pct < 0:
            raise ValueError(
                "stop_buffer_pct must be finite and non-negative"
            )

        if (
            not isfinite(self.fallback_long_stop_multiplier)
            or not 0 < self.fallback_long_stop_multiplier < 1
        ):
            raise ValueError(
                "fallback_long_stop_multiplier must be finite and between 0 and 1"
            )

        non_negative = {
            "brokerage_rate": self.brokerage_rate,
            "brokerage_cap": self.brokerage_cap,
            "tax_rate": self.tax_rate,
        }
        for name, value in non_negative.items():
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")

        if (
            isinstance(self.max_open_trades, bool)
            or not isinstance(self.max_open_trades, int)
            or self.max_open_trades < 1
        ):
            raise ValueError("max_open_trades must be a positive integer")

        if (
            isinstance(self.cost_rounding_digits, bool)
            or not isinstance(self.cost_rounding_digits, int)
            or self.cost_rounding_digits < 0
        ):
            raise ValueError(
                "cost_rounding_digits must be a non-negative integer"
            )

    def to_payload(self) -> dict:
        """Return the canonical research-identity representation."""

        return {
            "policy_id": self.policy_id,
            "max_position_pct": self.max_position_pct,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_weekly_loss_pct": self.max_weekly_loss_pct,
            "max_total_risk_pct": self.max_total_risk_pct,
            "max_open_trades": self.max_open_trades,
            "stop_buffer_pct": self.stop_buffer_pct,
            "stop_min_tick": self.stop_min_tick,
            "fallback_long_stop_multiplier": (
                self.fallback_long_stop_multiplier
            ),
            "brokerage_rate": self.brokerage_rate,
            "brokerage_cap": self.brokerage_cap,
            "tax_rate": self.tax_rate,
            "cost_rounding_digits": self.cost_rounding_digits,
        }


BACKTEST_ECONOMIC_POLICY = BacktestEconomicPolicy()
