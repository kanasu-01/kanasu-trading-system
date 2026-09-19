"""Immutable effective-input manifest for canonical Backtest research."""

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Any
import re

from core.config.backtest_economic_policy import BacktestEconomicPolicy
from core.config.execution_config import ExecutionConfig
from core.market_data.historical_coverage import TimeRange
from core.runtime.dataset_context import DatasetContext


_FINGERPRINT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


class _FrozenList(list):
    """List-shaped immutable container for canonical type stability."""

    __slots__ = ("_constructing",)

    @staticmethod
    def _immutable(*args, **kwargs):
        raise TypeError("manifest strategy parameters are immutable")

    def __new__(cls, values=()):
        instance = super().__new__(cls)
        list.__init__(instance, values)
        object.__setattr__(instance, "_constructing", True)
        return instance

    def __init__(self, values=()):
        if getattr(self, "_constructing", False):
            object.__delattr__(self, "_constructing")
            return
        self._immutable()

    __setattr__ = _immutable
    __delattr__ = _immutable
    __setitem__ = _immutable
    __delitem__ = _immutable
    append = _immutable
    clear = _immutable
    extend = _immutable
    insert = _immutable
    pop = _immutable
    remove = _immutable
    reverse = _immutable
    sort = _immutable
    __iadd__ = _immutable
    __imul__ = _immutable


def _freeze_strategy_value(value):
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise TypeError(
                "strategy parameter mappings require string keys"
            )

        return MappingProxyType(
            {
                key: _freeze_strategy_value(item)
                for key, item in value.items()
            }
        )

    if isinstance(value, list):
        return _FrozenList(
            _freeze_strategy_value(item)
            for item in value
        )

    if isinstance(value, tuple):
        return tuple(
            _freeze_strategy_value(item)
            for item in value
        )

    return value


@dataclass(frozen=True)
class BacktestRunManifest:
    dataset_context: DatasetContext
    requested_range: TimeRange
    dataset_fingerprint: str
    strategy_name: str
    strategy_params: Mapping[str, Any]
    initial_capital: float
    effective_risk_per_trade_pct: float
    execution_config: ExecutionConfig
    economic_policy: BacktestEconomicPolicy

    def __post_init__(self) -> None:
        if not isinstance(self.dataset_context, DatasetContext):
            raise TypeError("dataset_context must be a DatasetContext")
        if not isinstance(self.requested_range, TimeRange):
            raise TypeError("requested_range must be a TimeRange")
        if not _FINGERPRINT_PATTERN.fullmatch(self.dataset_fingerprint):
            raise ValueError(
                "dataset_fingerprint must use sha256:<64 lowercase hexadecimal>"
            )
        if not isinstance(self.strategy_name, str) or not self.strategy_name:
            raise ValueError("strategy_name must be a non-empty string")
        if not isinstance(self.strategy_params, Mapping):
            raise TypeError("strategy_params must be a mapping")
        if any(not isinstance(key, str) for key in self.strategy_params):
            raise TypeError("strategy_params keys must be strings")
        if not isfinite(self.initial_capital) or self.initial_capital <= 0:
            raise ValueError("initial_capital must be finite and positive")
        if (
            not isfinite(self.effective_risk_per_trade_pct)
            or self.effective_risk_per_trade_pct <= 0
        ):
            raise ValueError(
                "effective_risk_per_trade_pct must be finite and positive"
            )
        if not isinstance(self.execution_config, ExecutionConfig):
            raise TypeError("execution_config must be an ExecutionConfig")
        if not isinstance(self.economic_policy, BacktestEconomicPolicy):
            raise TypeError(
                "economic_policy must be a BacktestEconomicPolicy"
            )

        object.__setattr__(
            self,
            "strategy_params",
            _freeze_strategy_value(self.strategy_params),
        )
