from typing import List, Dict

from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.strategies.strategy_runner import StrategyRunner
from core.strategies.base_strategy import BaseStrategy


class BacktestEngine:
    """
    Runs a candle-by-candle backtest and computes basic trade metrics.
    """

    def __init__(self, strategy: BaseStrategy):
        self.strategy = strategy
        self.runner = StrategyRunner(strategy)
        self.trades: List[Dict] = []

    def run(self, candles: List[Candle]) -> List[Dict]:
        series = CandleSeries([])
        self.runner.start(series)

        current_trade = None

        for candle in candles:
            signal = self.runner.on_new_candle(candle)

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
