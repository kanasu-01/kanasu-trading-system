//
// PAPER TRADING CONFIG
//

export interface SymbolConfig {
  symbol: string;

  exchange: string;
}

export interface StrategyConfig {
  id: string;

  name: string;
}

export interface PaperTradingConfigResponse {
  symbols: SymbolConfig[];

  strategies: StrategyConfig[];
}

//
// START PAPER TRADING
//

export interface PaperTradingStartRequest {
  symbol: string;

  strategy_id: string;
}

export interface PaperTradingStartResponse {
  session_id: string;

  status: string;

  symbol: string;

  strategy: string;
}

//
// STOP PAPER TRADING
//

export interface PaperTradingStopResponse {
  status: string;
}

//
// STATUS
//

export interface ActivePosition {
  side: string;

  entry_price: number;

  current_price: number;

  quantity: number;

  unrealized_pnl: number;
}

export interface SessionMetrics {
  total_trades: number;

  win_rate: number;

  net_pnl: number;

  drawdown: number;
}

export interface PaperTrade {
  time: string;

  symbol: string;

  side: string;

  price: number;

  quantity: number;
}

export interface PaperTradingStatusResponse {
  status: string;

  strategy: string;

  symbol: string;

  started_at: string;

  active_position: ActivePosition | null;

  metrics: SessionMetrics;

  trades: PaperTrade[];
}