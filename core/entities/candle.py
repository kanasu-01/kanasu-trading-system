from dataclasses import dataclass
from datetime import datetime
from math import isfinite

@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    def __post_init__(self):
        if not all(
            isfinite(value)
            for value in (self.open, self.high, self.low, self.close, self.volume)
        ):
            raise ValueError("OHLCV values must be finite.")

        if self.high < max(self.open, self.close):
            raise ValueError("High price cannot be lower than open / close")
        
        if self.low > min(self.open, self.close):
            raise ValueError("Low cannot be higher than open / close.")
        
        if self.volume < 0:
            raise ValueError("Volume cannot be negative.")
