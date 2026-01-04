from dataclasses import dataclass
@dataclass(frozen=True)
class Instrument:
    symbol: str
    exchange: str = 'NSE'
    tick_size: float = 0.05
    lot_size: int = 1
    
    def __post_init__(self):
        if not self.symbol:
            raise ValueError("Symbol cannot be empty.")
        
        if self.tick_size <= 0:
            raise ValueError("Tick size must be positive.")
        
        if self.lot_size <= 0:
            raise ValueError("Lot size must be positive.")