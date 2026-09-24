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
  timezones: string[];
}

export interface SMACrossoverParams {
  fast_period: number;
  slow_period: number;
}

export interface BacktestRunRequest {
  symbol: string;
  timeframe: string;
  strategy_id: string;
  start: string;
  end: string;
  timezone: string;
  initial_capital: number;
  strategy_params: SMACrossoverParams;
}

export interface BacktestSummary {
  completed_trade_count: number;
  net_profitable_trade_count: number;
  net_losing_trade_count: number;
  net_breakeven_trade_count: number;
  net_profitable_trade_rate_pct: number;
  mean_positive_instrument_return_pct: number;
  mean_negative_instrument_return_pct: number;
  mean_instrument_return_pct: number;
  gross_realized_pnl: number;
  net_realized_pnl: number;
  mean_net_pnl_per_completed_trade: number;
  completed_trade_transaction_cost_total: number;
  account_pnl: number;
  account_return_pct: number;
  max_equity_drawdown_pct: number;
}

export interface BacktestEquityPoint {
  timestamp: string;
  equity: number;
}

export interface BacktestTrade {
  symbol: string;
  entry_time: string;
  entry_price: number;
  exit_time: string;
  exit_price: number;
  stop_price: number;
  quantity: number;
  direction: string;
  exit_reason: string;
  net_pnl: number;
  gross_pnl: number;
  transaction_cost: number;
  instrument_return_pct: number;
}

export interface BacktestRunResponse {
  run_id: string;
  status: "completed";
  symbol: string;
  timeframe: string;
  strategy_id: string;
  start: string;
  end: string;
  timezone: string;
  summary: BacktestSummary;
  equity_curve: BacktestEquityPoint[];
  trades: BacktestTrade[];
}
