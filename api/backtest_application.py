from api.models.backtest_models import (
    BacktestEquityPoint,
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestSummaryResponse,
    BacktestTradeResponse,
)
from core.backtest.performance_metrics import PerformanceMetrics
from core.config.app_config import AppConfig
from core.config.backtest_config import BacktestConfig
from core.config.loaders import load_app_config
from core.market_data.historical_source import HistoricalSource
from core.market_data.historical_source_factory import create_historical_source
from core.runtime.backtest_runtime import execute_backtest
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.strategies.strategy_factory import create_strategy


def execute_backtest_request(
    request: BacktestRunRequest,
    *,
    app_config: AppConfig | None = None,
    historical_source: HistoricalSource | None = None,
) -> BacktestRunResponse:
    resolved_app_config = (
        app_config
        if app_config is not None
        else load_app_config()
    )

    config = BacktestConfig(
        symbol=request.symbol,
        timeframe=request.timeframe,
        strategy_name=request.strategy_id,
        start=request.start,
        end=request.end,
        initial_capital=request.initial_capital,
        enable_replay=False,
        enable_visualization=False,
        enable_exports=False,
        strategy_params=request.strategy_params.model_dump(),
        timezone=request.timezone,
    )

    dataset_context = DatasetContext(
        symbol=request.symbol,
        timeframe=request.timeframe,
        timezone=request.timezone,
    )

    source = (
        historical_source
        if historical_source is not None
        else create_historical_source(resolved_app_config)
    )

    strategy = create_strategy(config)

    result = execute_backtest(
        historical_source=source,
        strategy=strategy,
        config=config,
        runtime_context=RuntimeContext(
            risk_per_trade_pct=(
                resolved_app_config.risk_per_trade_pct
            ),
        ),
        dataset_context=dataset_context,
    )

    summary = BacktestSummaryResponse.model_validate(
        PerformanceMetrics.summarize_backtest(result)
    )

    trades = []
    for trade in result.trades:
        if trade.exit_time is None:
            raise ValueError(
                "completed Backtest trade requires exit_time"
            )

        trades.append(
            BacktestTradeResponse(
                symbol=trade.symbol,
                entry_time=trade.entry_time,
                entry_price=trade.entry_price,
                exit_time=trade.exit_time,
                exit_price=trade.exit_price,
                stop_price=trade.stop_price,
                quantity=trade.quantity,
                direction=trade.direction,
                exit_reason=trade.exit_reason,
                net_pnl=trade.pnl,
                gross_pnl=trade.gross_pnl,
                transaction_cost=trade.transaction_cost,
                instrument_return_pct=trade.pnl_pct,
            )
        )

    return BacktestRunResponse(
        run_id=result.session_id,
        status="completed",
        symbol=request.symbol,
        timeframe=request.timeframe,
        strategy_id=request.strategy_id,
        start=request.start,
        end=request.end,
        timezone=request.timezone,
        summary=summary,
        equity_curve=[
            BacktestEquityPoint(
                timestamp=timestamp,
                equity=equity,
            )
            for timestamp, equity in result.equity_curve
        ],
        trades=trades,
    )
