from typing import List, Dict

from core.entities import candle
from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.strategies.strategy_runner import StrategyRunner
from core.strategies.base_strategy import BaseStrategy
from core.backtest.bar_record import BarRecorder



class BacktestEngine:
    """
    Runs a candle-by-candle backtest and computes basic trade metrics.
    """

    def __init__(self, strategy: BaseStrategy):
        self.strategy = strategy
        self.runner = StrategyRunner(strategy)
        self.trades: List[Dict] = []
        self.bar_recorder = BarRecorder()

    def run(self, candles: List[Candle]) -> List[Dict]:
        series = CandleSeries([])
        self.runner.start(series)

        current_trade = None

        for candle in candles:
            signal = self.runner.on_new_candle(candle)

            # Capture strategy intelligence
            acc_val = None
            dist_val = None
            confidence_val = None
            
            if len(self.runner.series) >= self.strategy.warmup_bars():
                acc_score = getattr(self.strategy, "acc_scorer", None)
                dist_score = getattr(self.strategy, "dist_scorer", None)

                acc_val = acc_score.score(self.runner.series) if acc_score else None
                dist_val = dist_score.score(self.runner.series) if dist_score else None
                confidence_score = getattr(self.strategy, "confidence_score", None)
                confidence_val = (
                    confidence_score.score(self.runner.series)
                    if confidence_score else None
                )

            # Record bar data and strategy state
            
            debug = {}
            if hasattr(self.strategy, "get_debug_state"):
                debug = self.strategy.get_debug_state() 
            self.bar_recorder.record(
                candle=candle,
                strategy=self.strategy,
                acc_score=debug.get("acc_score"),
                dist_score=debug.get("dist_score"),
                confidence=debug.get("confidence"),
                absorption_active=debug.get("absorption_active"),
                markup_confirmed=debug.get("markup_confirmed"),
                volatility_contracting=debug.get("volatility_contracting"),
                signal=signal,
            )


            # ENTRY
            if signal == "BUY" and current_trade is None:
                current_trade = {
                    "entry_time": candle.timestamp,
                    "entry_price": candle.close
                }

            # EXIT
            elif signal == "SELL" and current_trade is not None:
                exit_price = candle.close
                entry_price = current_trade["entry_price"]

                pnl = exit_price - entry_price
                pnl_pct = (pnl / entry_price) * 100

                current_trade.update({
                    "exit_time": candle.timestamp,
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "holding_period": (
                        candle.timestamp - current_trade["entry_time"]
                    )
                })

                self.trades.append(current_trade)
                current_trade = None

        return self.trades
