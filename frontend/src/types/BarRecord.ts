export interface DecisionSnapshot {
  fast_sma?: number | null;
  slow_sma?: number | null;
  [key: string]: unknown;
}

export interface BarRecord {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;

  strategy: string;
  state: string | null;
  signal: "BUY" | "SELL" | null;

  decision_snapshot: DecisionSnapshot;
}
