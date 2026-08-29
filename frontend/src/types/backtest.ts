//
// BACKTEST CONFIG
//

export interface MarketConfig {
  id: string;

  name: string;
}

export interface SymbolConfig {
  symbol: string;

  exchange: string;
}

export interface TimeframeConfig {
  id: string;

  label: string;
}

export interface StrategyConfig {
  id: string;

  name: string;
}

export interface BacktestConfigResponse {
  markets: MarketConfig[];

  symbols: SymbolConfig[];

  timeframes: TimeframeConfig[];

  strategies: StrategyConfig[];
}

//
// BACKTEST RUN REQUEST
//

export interface BacktestRunRequest {
  market: string;

  symbol: string;

  timeframe: string;

  strategy_id: string;

  from_date: string;

  to_date: string;

  initial_capital: number;
}

//
// BACKTEST RESULT
//

export interface BacktestSummary {
  total_trades: number;

  win_rate: number;

  net_pnl: number;

  max_drawdown: number;

  expectancy: number;
}

export interface BacktestRunResponse {
  run_id: string;

  status: string;

  summary: BacktestSummary;

  equity_curve: unknown[];

  trades: unknown[];

  replay_available: boolean;
}