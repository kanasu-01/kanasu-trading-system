from core.execution.trade_execution_engine import TradeExecutionEngine
from core.entities.candle_series import CandleSeries
from core.market_data.base_feed import MarketDataFeed
from core.strategies.pivotboss_swing_strategy import PivotBossSwingStrategy

"""
Live paper trading runner.

STATUS:
    Runtime modernization pending.

Current limitations:
    - Uses outdated execution flow
    - Not integrated with StrategyRunner
    - Missing reconciliation support
    - Missing session-aware runtime logging
    - Not production-ready
"""


class LivePaperTradingRunner:
    """
    Live paper trading runner.
    """

    def __init__(
        self,
        feed: MarketDataFeed,
        initial_capital: float = 1_000_000,
    ):
        self.series = CandleSeries()
        self.feed = feed

        self.strategy = PivotBossSwingStrategy()
        self.execution_engine = TradeExecutionEngine(
            strategy=self.strategy,
            account_capital=initial_capital,
        )

    def start(self) -> None:
        def on_new_candle(candle):
            self.series.add(candle)
            self.execution_engine.on_new_candle(candle, self.series)

        self.feed.subscribe(on_new_candle)
