from typing import List, Dict, Optional
from dataclasses import dataclass
from core.entities.candle import Candle
from datetime import datetime

@dataclass
class BarRecord:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    state: str
    acc_score: Optional[float]
    dist_score: Optional[float]
    confidence: Optional[float]
    
    absorption_active: Optional[bool]
    markup_confirmed: Optional[bool]
    volatility_contracting: Optional[bool]

    signal: Optional[str]
    
    strategy:str

class BarRecorder:
    """
    Records bar-by-bar strategy evaluation.
    """

    def __init__(self):
        self.records: List[BarRecord] = []

    def record(
        self,
        candle: Candle,
        strategy,
        acc_score,
        dist_score,
        confidence,
        absorption_active,
        markup_confirmed,
        volatility_contracting,
        signal,
    ):
        self.records.append(
            BarRecord(
                timestamp=candle.timestamp,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
                
                state=strategy.state.value,
                acc_score=acc_score,
                dist_score=dist_score,
                confidence=confidence,
                absorption_active=absorption_active,
                markup_confirmed=markup_confirmed,
                volatility_contracting=volatility_contracting,
                
                signal=signal,
                strategy=strategy.__class__.__name__,
            )
        )
