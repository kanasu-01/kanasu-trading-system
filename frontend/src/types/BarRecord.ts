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

  decision_snapshot: Record<string, any>;
}
