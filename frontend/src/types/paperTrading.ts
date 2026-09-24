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

export interface PaperTradingStartRequest {
  symbol: string;
  strategy_id: string;
}

export type PaperTradingLifecycleStatus =
  | "CREATED"
  | "RUNNING"
  | "STOPPED"
  | "FAILED";

export interface PaperPositionSnapshot {
  symbol: string;
  direction: string;
  quantity: number;
  entry_time: string;
  entry_price: number;
  stop_price: number;
}

export interface PaperTradingSnapshot {
  session_id: string;
  status: PaperTradingLifecycleStatus;
  strategy_name: string;
  symbol: string;
  started_at: string | null;
  stopped_at: string | null;
  initial_capital: number;
  cash: number | null;
  position_size: number | null;
  position_value: number | null;
  equity: number | null;
  realized_pnl: number | null;
  unrealized_pnl: number | null;
  total_pnl: number | null;
  peak_equity: number | null;
  drawdown: number | null;
  active_position: PaperPositionSnapshot | null;
  completed_trade_count: number;
  last_execution_event: string | null;
  last_execution_price: number | null;
  last_execution_quantity: number | null;
  failure_type: string | null;
  failure_message: string | null;
}

export interface PaperTradingStatusResponse {
  active: boolean;
  snapshot: PaperTradingSnapshot | null;
}

export type PaperTradingStartResponse =
  PaperTradingSnapshot;

export type PaperTradingStopResponse =
  PaperTradingSnapshot;
