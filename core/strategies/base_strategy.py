from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from core.entities.candle_series import CandleSeries


class BaseStrategy(ABC):
    """
    Base class for all trading strategies.
    Supports parameterized behavior.
    """

    def __init__(self, name: str, params: Optional[Dict[str, Any]] = None):
        self.name = name
        self.params = params or {}

    def get_param(self, key: str, default: Any = None) -> Any:
        """
        Safely get a parameter value.
        """
        return self.params.get(key, default)

    @abstractmethod
    def on_new_candle(
        self,
        series: CandleSeries
    ) -> Optional[str]:
        """
        Called whenever a new candle is available.

        Returns:
            - "BUY"
            - "SELL"
            - None
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """
        Resets internal state of the strategy.
        """
        pass
